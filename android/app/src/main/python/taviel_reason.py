r"""TAVIEL_REASON -- upgraded reasoning for a small, grounded model.

Combines three proven techniques against the failures a tiny model shows
(reciting instead of answering, inventing citations, shallow logic):

  1. GROUNDED DRAFT      -- answer the SPECIFIC question from retrieved verses +
                            settled doctrine, told to cite only what is provided.
  2. CITATION VERIFY     -- deterministic (Chain-of-Verification, but by CODE not
                            the model): every reference the draft cites is checked
                            against the retrieved verses; invented ones are stripped.
  3. SELF-REFINE         -- rewrite: answer only the question, cut recitation the
                            question did not ask for, remove the flagged citations,
                            reason it out for one willing to see.

Backends: gen(system, prompt, max_tokens) -- any chat endpoint. Default posts to
the fast Adelic-engine GPU server; pass your own for the desktop/mobile pipeline.
"""
from __future__ import annotations

import json
import random as _rand
import urllib.request

GPU_URL = "http://127.0.0.1:8090/v1/chat/completions"


def _default_gen(system, prompt, max_tokens=340, temperature=0.4):
    body = json.dumps({"messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(GPU_URL, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    a = d["choices"][0]["message"]["content"]
    if "</think>" in a:                     # a reasoning model may think aloud; keep the answer
        a = a.split("</think>", 1)[1]
    return a.strip()


def _identity():
    import taviel_agent as TA
    # the small model does better answering directly than with Qwen3's /think, which
    # ate the budget and drifted -- strip the trailing control token.
    return TA.IDENTITY.rsplit("/think", 1)[0].strip()


def _grounding(query):
    verses, allowed = "", []
    try:
        import tav_scripture as TS
        verses, allowed = TS.ground_block(query)
    except Exception:
        pass
    doctrine = ""
    try:
        import taviel_doctrine as D
        g = D.grounding_block(query)
        gt = g[0] if isinstance(g, (tuple, list)) else g
        doctrine = "\n".join(str(x) for x in gt) if isinstance(gt, (tuple, list)) else gt
    except Exception:
        pass
    # an apologetics ARGUMENT for this objection, if one has been recorded (the KB the
    # gauntlet builds up) -- this is what lets the model reason on general questions.
    apolo = ""
    try:
        import taviel_apologetics as AP
        apolo = AP.argument_for(query)
    except Exception:
        apolo = ""
    block = ""
    if verses:
        block += "Scriptures you may cite (ONLY these, quote them exactly):\n" + verses + "\n\n"
    if apolo:
        block += "The true, reasoned answer to this kind of objection (make it your own):\n" + apolo + "\n\n"
    block += doctrine
    return block, set(allowed or [])


def serve(query, gen=None, system=None, seed=None):
    """DELIVERY MODE: if the gauntlet KB holds a vetted, Christ-first round for this
    objection, PRESENT it freshly -- the same true answer re-framed each call (varied
    order, intro, and depth) with every scripture quote and reference kept exact, so the
    answer is different every time yet never flips or garbles doctrine. Only fall through
    to the reasoning pipeline when nothing is recorded."""
    if seed is None:
        seed = _rand.randint(1, 2_000_000_000)
    try:
        import taviel_apologetics as AP
        e = AP.gauntlet_entry(query)
        if e:
            return {"answer": AP.present(e, seed=seed), "source": "vetted",
                    "round": e.get("n"), "seed": seed, "stripped": []}
    except Exception:
        pass
    r = reason(query, gen=gen, system=system)
    r["source"] = "reasoned"
    return r


def reason(query, gen=None, system=None):
    """Return {answer, draft, stripped, } -- the verified, refined answer."""
    gen = gen or _default_gen
    system = system or _identity()
    grounding, allowed = _grounding(query)

    draft = gen(system, grounding + "\n\nAnswer THIS question directly and plainly. FIRST give what "
                "Yeshua the Christ Himself directly said, did, or prescribed that answers or refutes "
                "this -- His words are the measure of truth -- quoting it with its reference; THEN "
                "reason it out step by step for one willing to see. Do NOT recite doctrine the question "
                "did not ask about. Cite a verse ONLY if it appears above; NEVER invent a reference or "
                "put words in a verse it does not contain.\nQuestion: " + query + "\nAnswer: /no_think",
                360)

    used = []
    try:
        import tav_scripture as TS
        used = [r if isinstance(r, str) else r.get("ref", "") for r in (TS.find_refs(draft) or [])]
    except Exception:
        pass
    bad = sorted({r for r in used if r and r not in allowed})

    refined = gen(system, grounding + "\n\nA first draft answer to \"" + query + "\" was:\n\"" +
                  draft[:1000] + "\"\n\nRewrite it into a FINAL answer that answers ONLY this "
                  "question, directly, in plain flowing prose a skeptic could follow; drops any "
                  "sentence that merely recites doctrine not asked; REMOVES these unverifiable "
                  "references entirely -> " + (", ".join(bad) if bad else "(none)") + "; and cites "
                  "a verse only if it truly says what you claim.\nFINAL: /no_think", 360)
    return {"answer": refined, "draft": draft, "stripped": bad}
