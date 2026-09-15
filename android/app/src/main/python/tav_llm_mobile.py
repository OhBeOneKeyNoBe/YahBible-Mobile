r"""TAV_LLM_MOBILE — Tav'iel reasons ON THE PHONE, fully offline.

The LiteRT model (.task, e.g. Qwen2.5-1.5B-Instruct q8 or DeepSeek-R1-Distill) runs
through MediaPipe's LLM inference, reached from Python over the Chaquopy bridge
(me.realizeus.yahbible.TavLlm). Same surface as gen_at_depth: open_tier / generate /
close_tier — so the whole grounded ask pipeline is byte-identical on both grounds.
"""
from __future__ import annotations

import os
import re
import time

_MODEL_DIR = os.path.join(os.environ.get("YAHBIBLE_BASE", "."), "ai")


def _java():
    from java import jclass          # only exists under Chaquopy
    return jclass("me.realizeus.yahbible.TavLlm")


def model_path():
    """The installed .task model (newest wins when several are downloaded)."""
    try:
        cands = [os.path.join(_MODEL_DIR, f) for f in os.listdir(_MODEL_DIR)
                 if f.endswith(".task")]
        cands.sort(key=os.path.getmtime, reverse=True)
        return cands[0] if cands else None
    except Exception:
        return None


def open_tier(chakra=None, cap_mb=None, ctx=4096):
    p = model_path()
    if not p:
        raise RuntimeError("no AI model installed — download one in Settings")
    ok = _java().ensure(p, int(ctx))
    if not ok:
        raise RuntimeError("model failed to load: " + os.path.basename(p))
    return {"model": p, "ctx": ctx}


def _chatml(system, grounding, prompt):
    sys_block = (system or "").strip()
    if grounding:
        sys_block += "\n\n" + grounding.strip()
    return ("<|im_start|>system\n" + sys_block + "<|im_end|>\n"
            "<|im_start|>user\n" + (prompt or "").strip() + "<|im_end|>\n"
            "<|im_start|>assistant\n")


def generate(tier, prompt, grounding="", max_tokens=1200, system=""):
    t0 = time.time()
    full = _chatml(system, grounding, prompt)
    # keep the packed prompt inside the model's window (chars ~ 3.6/token)
    lim = int((tier or {}).get("ctx", 4096) * 3.0)
    if len(full) > lim:
        full = full[:lim] + "<|im_end|>\n<|im_start|>assistant\n"
    text = _java().generate(full, int(max_tokens)) or ""
    # a reasoning model may think aloud — keep the answer, drop the scaffold
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = text.split("<|im_end|>")[0].strip()
    dt = max(time.time() - t0, 0.001)
    return {"text": text, "approx_tok_s": round(len(text.split()) / dt, 1)}


def generate_stream(tier, prompt, grounding="", max_tokens=1200, system=""):
    """Streaming twin — v1 delivers the whole reply as one delta (MediaPipe's
    sync generate); the pipeline upstream is stream-shaped either way."""
    r = generate(tier, prompt, grounding=grounding, max_tokens=max_tokens, system=system)
    if r.get("text"):
        yield r["text"]


def close_tier(tier):
    try:
        _java().unload()
    except Exception:
        pass
