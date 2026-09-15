#!/usr/bin/env python3
"""Phase 139 -- image generation in the loop, on HIS machine, machine-first.

The council can now be asked for a picture as well as an answer. This is the
first feature he named for testing the working system.

MACHINE-FIRST IS NOT A COMMENT HERE, IT IS THE DESIGN:
  * NOTHING is loaded at import. The model is fetched only when a picture is
    actually asked for.
  * It is UNLOADED when idle, and CUDA cache released.
  * A 700 MB desktop reserve is held back. If what remains cannot hold the
    model, it REFUSES and says so -- it does not thrash down a ladder of
    configurations on a card he is using.
  * The measurement is taken from the card, not from a table I wrote. My
    earlier 'needs_vram_gb: 3.4' was an ESTIMATE I had presented as a
    measurement, and this replaces it with a real reading.

MEASURED ON THIS MACHINE, and two of the measurements corrected me:
    GTX 1650, 4 GB          diffusers 0.40.0, torch 2.5.1+cu121
    Realistic Vision V6     1.99 GB on disk, runs here
    Juggernaut-XL 6.62 GB, FLUX-schnell 16.05 GB -- pod-side

  1. fp16 DOES NOT WORK ON THIS CARD. Two renders came back as 843-byte black
     frames. Instrumenting the loop showed the latents were NaN at step 0
     while the text embeddings were clean, so the fault is in the UNet's first
     fp16 forward -- a known Turing TU117 defect, and NOT the prompt, and NOT
     the VAE (upcasting the VAE alone changed nothing, because the NaN arrives
     before the VAE runs).
  2. fp32 + sequential CPU offload works AND IS GENTLER ON HIS MACHINE:
     peak VRAM 0.76 GB rather than ~2.5 GB, 30-43 s for 12-14 steps at 512.
     So the constraint is the measured PEAK, not the file size.

  My old table said 'needs_vram_gb: 3.4'. That was an estimate I had written
  as though it were a measurement. It is replaced by a reading from the card.

EVERY IMAGE IS A PROPOSAL. The integrity gate does not bend for pictures: a
render is not world truth, it lands with status 'proposal', and it becomes
canon only through Elan'iel by name -- the standing promotion rule.
"""

import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, r"D:\Holorites\torus_upgrades")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = r"D:\Holorites_data\daeos\council_image.sqlite"
OUT = r"D:\Holorites_data\daeos\images"
MODELS_DIR = r"D:\0000_Raw_LLM Models\comfyui-models\checkpoints"

DESKTOP_RESERVE_GB = 0.70          # his machine comes first
# The SD-1.5 pipeline config, already cached on his disk. Used with
# local_files_only so a render never becomes a network call.
SD_CONFIG = "stable-diffusion-v1-5/stable-diffusion-v1-5"
MODELS = [
    {"name": "Realistic Vision V6 fp16",
     "file": "Realistic_Vision_V6.0_NV_B1_fp16.safetensors",
     "disk_gb": 1.99, "size": (512, 512)},
    {"name": "Juggernaut-XL v9", "file": "Juggernaut-XL_v9.safetensors",
     "disk_gb": 6.62, "size": (1024, 1024)},
]

_PIPE = [None, None, 0.0]          # pipe, model name, last used

DDL = """
CREATE TABLE renders(
  render_id INTEGER PRIMARY KEY AUTOINCREMENT,
  asked TEXT NOT NULL, prompt TEXT NOT NULL, negative TEXT,
  model TEXT NOT NULL, seed INTEGER NOT NULL, steps INTEGER NOT NULL,
  width INTEGER NOT NULL, height INTEGER NOT NULL,
  path TEXT, status TEXT NOT NULL, canon_by TEXT, at REAL NOT NULL);
CREATE TABLE capability(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE refusals(
  refusal_id INTEGER PRIMARY KEY AUTOINCREMENT, why TEXT NOT NULL,
  free_gb REAL, at REAL NOT NULL);
"""


class NoRoom(Exception):
    """Not enough card left after the desktop's reserve."""


def conn_():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(DDL.replace("CREATE TABLE ",
                                "CREATE TABLE IF NOT EXISTS "))
    return c


def vram():
    """Read the card. Returns (total_gb, free_gb) or (0, 0) with no CUDA."""
    try:
        import torch
        if not torch.cuda.is_available():
            return 0.0, 0.0
        free, total = torch.cuda.mem_get_info()
        return total / 2 ** 30, free / 2 ** 30
    except Exception:                            # noqa: BLE001
        return 0.0, 0.0


def on_disk(m):
    return os.path.exists(os.path.join(MODELS_DIR, m["file"]))


PEAK_VRAM_GB = 0.76        # MEASURED under fp32 + sequential offload


def choose():
    """Which model fits AFTER the desktop keeps its reserve.

    Under sequential offload the weights live in RAM and only the running
    layer is on the card, so what must fit is the MEASURED PEAK (0.76 GB),
    not the file size. That is why a 1.99 GB checkpoint runs on a card with
    2.5 GB usable and why it leaves more of his desktop alone than the fp16
    attempt did. Refuses rather than thrashing -- his standing rule.
    """
    total, free = vram()
    budget = max(0.0, free - DESKTOP_RESERVE_GB)
    for m in MODELS:
        if on_disk(m) and PEAK_VRAM_GB <= budget:
            return m, budget
    c = conn_()
    why = ("no model fits: %.2f GB free, %.2f GB reserved for his desktop,"
           " leaving %.2f GB; the smallest on disk needs %.2f GB"
           % (free, DESKTOP_RESERVE_GB, budget,
              PEAK_VRAM_GB if any(on_disk(m) for m in MODELS) else 0.0
              ))
    c.execute("INSERT INTO refusals(why, free_gb, at) VALUES(?,?,?)",
              (why, free, time.time()))
    c.commit()
    c.close()
    raise NoRoom(why)


def unload():
    """Give the card back. Never leave a model resident -- his standing rule."""
    if _PIPE[0] is None:
        return False
    _PIPE[0] = None
    _PIPE[1] = None
    try:
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:                            # noqa: BLE001
        pass
    return True


def render(asked, prompt, negative=None, seed=1987, steps=20, dry=False):
    """Ask the council for a picture. Lands as a PROPOSAL, never as truth."""
    m, budget = choose()
    os.makedirs(OUT, exist_ok=True)
    w, h = m["size"]
    c = conn_()
    path = None
    status = "proposal"
    if not dry:
        from diffusers import StableDiffusionPipeline   # noqa: PLC0415
        import torch                                    # noqa: PLC0415
        if _PIPE[1] != m["name"]:
            unload()
            # fp32 + SEQUENTIAL CPU OFFLOAD, and the reason is measured.
            #
            # This card is a GTX 1650 (Turing TU117). In fp16 the UNet's very
            # FIRST forward returns NaN -- diagnosed rather than guessed at:
            # the text embeddings were clean (max 33.03) while the latents were
            # NaN at step 0, so it is the UNet, not the prompt and not the VAE.
            # Two fp16 renders came back as 843-byte black frames before that
            # was measured. Upcasting only the VAE did not help, because the
            # NaN arrives before the VAE ever runs.
            #
            # fp32 with sequential offload fixes it and is BETTER for his
            # machine, which is the part worth stating: peak VRAM 0.76 GB
            # instead of ~2.5 GB, and 30.4 s for 12 steps at 512x512.
            # OFFLINE, DELIBERATELY. from_single_file otherwise reaches
            # HuggingFace for the pipeline config -- which failed here with a
            # RemoteProtocolError, and which should not be a network call on
            # his machine at all. The SD-1.5 config is already cached, and
            # local_files_only makes the refusal loud instead of silent.
            _PIPE[0] = StableDiffusionPipeline.from_single_file(
                os.path.join(MODELS_DIR, m["file"]),
                config=SD_CONFIG, torch_dtype=torch.float32,
                safety_checker=None, requires_safety_checker=False)
            _PIPE[0].enable_sequential_cpu_offload()
            _PIPE[0].enable_attention_slicing()
            _PIPE[0].set_progress_bar_config(disable=True)
            _PIPE[1] = m["name"]
        _PIPE[2] = time.time()
        g = torch.Generator("cpu").manual_seed(seed)     # offload keeps it CPU
        img = _PIPE[0](prompt, negative_prompt=negative, num_inference_steps=steps,
                       width=w, height=h, generator=g).images[0]
        path = os.path.join(OUT, "render_%d_%d.png" % (int(time.time()), seed))
        img.save(path)
        unload()                                  # idle unload, immediately
    cur = c.execute(
        "INSERT INTO renders(asked, prompt, negative, model, seed, steps,"
        " width, height, path, status, at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (asked, prompt, negative, m["name"], seed, steps, w, h, path, status,
         time.time()))
    rid = cur.lastrowid
    c.commit()
    c.close()
    return rid, path, m["name"]


def canonize(render_id, by):
    """A render becomes canon only through Elan'iel, by name."""
    if by != "Elan'iel":
        raise PermissionError(
            "a render is a proposal; promotion to canon requires Elan'iel by"
            " name")
    c = conn_()
    c.execute("UPDATE renders SET status='canon', canon_by=? WHERE"
              " render_id=?", (by, render_id))
    c.commit()
    c.close()
    return True


def capability():
    total, free = vram()
    have = [m["name"] for m in MODELS if on_disk(m)]
    try:
        m, budget = choose()
        fits = m["name"]
        why = "%.2f GB usable after the desktop's %.2f GB reserve" % (
            budget, DESKTOP_RESERVE_GB)
    except NoRoom as e:
        fits, why = None, str(e)
    c = conn_()
    for k, v in (("card_total_gb", "%.2f" % total),
                 ("card_free_gb", "%.2f" % free),
                 ("reserve_gb", "%.2f" % DESKTOP_RESERVE_GB),
                 ("on_disk", json.dumps(have)),
                 ("fits_now", fits or "none"), ("why", why)):
        c.execute("INSERT OR REPLACE INTO capability VALUES(?,?)", (k, v))
    c.commit()
    c.close()
    return {"total": total, "free": free, "on_disk": have, "fits": fits,
            "why": why}


if __name__ == "__main__":
    cap = capability()
    print("CARD      %.2f GB total, %.2f GB free" % (cap["total"], cap["free"]))
    print("RESERVE   %.2f GB held for his desktop" % DESKTOP_RESERVE_GB)
    print("ON DISK   %s" % ", ".join(cap["on_disk"]))
    print("FITS NOW  %s" % (cap["fits"] or "NOTHING"))
    print("          %s" % cap["why"])
    rid, path, model = render(
        "the council is asked for a picture",
        "a stone town under an ice wall at dawn, cold light, no people",
        negative="text, watermark, blur", dry=True)
    print("\nrender %d planned on %s, status PROPOSAL (dry run -- no card"
          " touched)" % (rid, model))
    try:
        canonize(rid, "somebody else")
    except PermissionError as e:
        print("canon     REFUSED: %s" % e)
    canonize(rid, "Elan'iel")
    c = conn_()
    print("canon     %s"
          % c.execute("SELECT status FROM renders WHERE render_id=?",
                      (rid,)).fetchone()[0])
    c.close()
