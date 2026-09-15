r"""TAV_LLM — one door to the reasoning model, whichever ground Tav'iel stands on.

Desktop: gen_at_depth (torus-paged GGUF tiers through the llama-server launcher).
Phone:   tav_llm_mobile (LiteRT .task through MediaPipe, fully offline, on-device).

Both expose: open_tier(chakra, cap_mb, ctx) / generate(tier, prompt, grounding,
max_tokens, system) / close_tier(tier).
"""
from __future__ import annotations

import os


def backend():
    if os.environ.get("YAHBIBLE_ANDROID"):
        import tav_llm_mobile as B
        return B
    import gen_at_depth as B
    return B
