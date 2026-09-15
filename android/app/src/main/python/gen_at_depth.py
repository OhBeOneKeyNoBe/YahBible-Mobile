#!/usr/bin/env python3
r"""Phase G -- GEN-AT-DEPTH: actually RUN a servable chakra-tier (a real GGUF) via
the existing llama-server launcher and GENERATE tokens at a chosen depth (the
"deep slow stream"). Machine-first: ONE tier resident at a time; his VRAM_CAP_MB
(683, "one third") is respected first -- the auto-fit ladder settles at ngl=0
(all weights CPU/mmap) for the big models, which still runs; only if a tier
REFUSES under the third do we disclose and offer a raised cap. Unload after.

TAV chakra -> Adelic tier (grades 1-5). GGUF tiers run direct; the safetensors
tiers (Third Eye 1B / Throat 8B) take the torus-retrofit path (later) or an
on-disk GGUF proxy -- disclosed.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, r"D:\Holorites\torus_upgrades")
import phase30_model as PM  # noqa: E402

# chakra -> (port, gguf path, adelic tier note). One resident at a time on 4 GB.
TIERS = {
    "heart":  (8103, r"D:\sneedjak_models\Adelic-Gemma-4-12B-GGUF\adelic-gemma4-12b-Q6_K.gguf",
               "grade 3 / 12B / relation-continuity"),
    "solar":  (8104, r"D:\sneedjak_models\Adelic-Qwen3.6-27B-Topology\adelic-qwen-27b-q8_0.gguf",
               "grade 4 / 27B / verify-contradiction"),
    "sacral": (8105, r"D:\sneedjak_models\Adelic-Gemma-4-31B-it\adelic-gemma4-31b-Q4_K_M.gguf",
               "grade 5 / 31B / deep synthesis"),
    # fast tiers are safetensors -> on-disk GGUF proxies until the retrofit path:
    "throat":    (8102, r"D:\0000_Raw_LLM Models\Qwen3-8B-abliterated.Q4_K_M.gguf",
                  "grade 2 / 8B proxy / language"),
    # the PHONE'S OWN MIND, resident on the desktop for 1:1 evaluation of mobile Tav'iel
    "root":      (8106, r"D:\0000_Raw_LLM Models\Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
                  "grade 0 / 1.5B / the mobile tier"),
    "third_eye": (8101, r"D:\0000_Raw_LLM Models\Qwen3-0.6B-Q8_0.gguf",
                  "grade 1 / 0.6B proxy / recognition-routing"),
}


def open_tier(chakra, cap_mb=683, total_mb=4096, ctx=2048):
    """Start one chakra-tier's llama-server, auto-fitting under the VRAM cap.
    Returns a live LlamaModel (its own __enter__ already run) or raises VramRefusal.
    Respects his 683 'third' by default; raise cap_mb only when a tier needs it."""
    if chakra not in TIERS:
        raise KeyError("unknown chakra %r; have %s" % (chakra, list(TIERS)))
    port, path, note = TIERS[chakra]
    PM.VRAM_CAP_MB = cap_mb                    # runtime override (this process only)
    print("[gen] opening %s tier (%s) on port %d, cap %d MB ..." % (chakra, note, port, cap_mb),
          flush=True)
    # start the ladder at ngl=0 (all CPU/mmap) so a big GGUF with no MEASURED entry
    # does NOT try to load all layers onto the 4 GB card and time out. MEASURED
    # tiers (0.6B/8B) ignore this and use their tuned ladder.
    #
    # RESOURCE-BOUNDED STREAMING for the big tiers: heart 12B / solar 27B / sacral 31B are the
    # disk-streamed voices. They are GUARANTEED never to overload the box -- they run at IDLE OS
    # priority (only spare CPU cycles), on just a few threads (cores stay free for the RAM voice
    # + other apps), with a small batch and a bounded context (bounded KV memory), and mmap keeps
    # the weights paging from disk instead of all in RAM. That is the trickle: they still flow
    # and contribute, but they physically cannot starve the system.
    BIG = {"heart", "solar", "sacral"}
    if chakra in BIG:
        # below-normal priority (yields to the RAM voice + his foreground apps, so it can never
        # overload) but NOT dead-idle, so it still progresses to an answer -- a real trickle that
        # reaches B. Capped threads + small batch + bounded ctx + mmap keep it bounded.
        m = PM.LlamaModel(path, gpu_layers=0, ctx=min(ctx, 2048), port=port, total_mb=total_mb,
                          threads=4, priority="belownormal", batch=128)
    else:
        m = PM.LlamaModel(path, gpu_layers=0, ctx=ctx, port=port, total_mb=total_mb)
    m.__enter__()                             # auto-fit ladder -> ngl; VramRefusal if none
    m._chakra = chakra
    return m


def generate(m, prompt, grounding="", max_tokens=160, temperature=0.7, system=None):
    """Generate at this tier's depth. `grounding` (lexicon/Bible/etc) is prepended
    to the user prompt; `system` (an identity/instruction) goes to the system role
    -- the model carries language, the grounding carries the truth."""
    full = (grounding.rstrip() + "\n\n" + prompt) if grounding else prompt
    t0 = time.time()
    text = m.complete(full, max_tokens=max_tokens, temperature=temperature, system=system)
    dt = time.time() - t0
    # truncate at any chat-template turn marker OR special/multimodal token the model
    # echoed past its answer (Gemma-4 is multimodal -- its <image|> token can loop
    # at ngl=0; the coherent text prefix before it is the answer).
    for mark in ("<|im_end|>", "<|im_start|>", "<end_of_turn>", "<start_of_turn>",
                 "<image", "<unused", "<pad>", "<eos>"):
        i = text.find(mark)
        if i != -1:
            text = text[:i]
    text = text.strip()
    ntok = max(1, len(text.split()))
    return {"text": text, "seconds": round(dt, 1),
            "approx_tok_s": round(ntok / dt, 2) if dt else None,
            "ngl": m.gpu_layers, "chakra": m._chakra}


def generate_stream(m, prompt, grounding="", max_tokens=768, temperature=0.7, system=None):
    """Stream generation at this tier's depth -- yields text deltas as they arrive."""
    full = (grounding.rstrip() + "\n\n" + prompt) if grounding else prompt
    MARKS = ("<|im_end|>", "<|im_start|>", "<end_of_turn>", "<start_of_turn>",
             "<image", "<unused", "<pad>", "<eos>")
    for delta in m.complete_stream(full, max_tokens=max_tokens, temperature=temperature,
                                   system=system):
        for mark in MARKS:                 # stop at any turn/special marker the model echoes
            if mark in delta:
                delta = delta.split(mark)[0]
        if delta:
            yield delta


def close_tier(m):
    try:
        m.stop()
    except Exception:
        pass


def run_one(chakra, prompt, cap_mb=683):
    """Open a tier, generate once, unload -- the full machine-first cycle."""
    m = None
    try:
        m = open_tier(chakra, cap_mb=cap_mb)
        r = generate(m, prompt)
        print("[gen] %s: ngl=%s  %.1fs  ~%.2f tok/s" % (chakra, r["ngl"], r["seconds"],
                                                        r["approx_tok_s"] or 0), flush=True)
        print("[gen] OUTPUT:\n" + r["text"], flush=True)
        return r
    finally:
        if m is not None:
            close_tier(m)
            print("[gen] %s unloaded (nothing left resident)." % chakra, flush=True)


if __name__ == "__main__":
    chakra = sys.argv[1] if len(sys.argv) > 1 else "heart"
    prompt = sys.argv[2] if len(sys.argv) > 2 else \
        "In one sentence, what is the purpose of a vessel that remembers?"
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 683
    run_one(chakra, prompt, cap_mb=cap)
