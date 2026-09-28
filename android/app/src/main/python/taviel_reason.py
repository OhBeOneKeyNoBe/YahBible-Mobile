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
# The decision server (taviel_decide) keeps ONE model resident that already
# serves /v1/chat/completions. Since the two-witness commit rule made
# deferral the common path -- and deferral means "answer by reasoning" -- the
# prose path must not depend on a tier server nobody started: an unreachable
# 8090 now falls back to the resident model rather than raising, which used
# to abort a whole proof run with a bare URLError.
FALLBACK_URL = "http://127.0.0.1:8110/v1/chat/completions"


def _post(url, body, timeout=180):
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _default_gen(system, prompt, max_tokens=340, temperature=0.4):
    body = json.dumps({"messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    try:
        d = _post(GPU_URL, body)
    except Exception:
        d = _post(FALLBACK_URL, body)
    a = d["choices"][0]["message"]["content"]
    if "</think>" in a:                     # a reasoning model may think aloud; keep the answer
        a = a.split("</think>", 1)[1]
    return a.strip()


_GEN_AVAIL = {"at": 0.0, "ok": False}


def _gen_available(timeout=0.4, ttl=20.0):
    """Is ANY generator reachable? Probed before the grounding is built.

    Discovered by the install proof: with no server running, the offline
    fallback still took 4.1 seconds, and none of it was the failing request --
    a refused connection on localhost returns at once. The time went into
    _grounding(), which reads scripture and the truth roots to assemble a
    prompt for a model that was never going to be asked.

    Building the meal before checking whether anyone is home is the whole
    cost. So: probe first, cheaply, and if nothing answers, skip straight to
    the offline reply.
    """
    import time as _t
    now = _t.time()
    if now - _GEN_AVAIL["at"] < ttl:
        return _GEN_AVAIL["ok"]
    ok = False
    for url in (GPU_URL, FALLBACK_URL):
        try:
            base = url.rsplit("/v1/", 1)[0]
            urllib.request.urlopen(base + "/health", timeout=timeout)
            ok = True
            break
        except Exception:
            continue
    _GEN_AVAIL.update(at=now, ok=ok)
    return ok


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


def serve(query, gen=None, system=None, seed=None, profile=None,
          instant_only=False):
    """THE ONE DOOR both YahBible and O'Tav'iel answer through.

    Three tiers, best first, each falling through to the next:

      JEV       the decision front door, when the decision server and the
                embedder are both reachable. Routes by the measured rules and
                returns identity, vetted, verse, clarify or decline answers
                with ZERO generated tokens (661ms committed, ~90ms declined).
      VETTED    the verbatim gauntlet lookup. No server, no GPU, no embedder.
                This is the floor and it is never removed.
      REASONED  grounded generation with mechanical citation checking.

    `profile` {sex, age_band, affiliation, ...} tailors the identity answers
    and overrides the register inferred from wording. Pass profile=False to
    force the pre-Jev path -- the proofs use it as a control arm.
    """
    if seed is None:
        seed = _rand.randint(1, 2_000_000_000)

    # ---- JEV, WHEN JEV IS HERE ------------------------------------------
    # The front door routes with the measured rules -- retrieval and the judge
    # must independently name the same round, the asking must resemble the
    # round it lands on, and a deferral may be restated once and only onto a
    # round the original already had in view. Off-topic 1.8% at n=600, and a
    # committed answer costs 661ms with ZERO generated tokens.
    #
    # It is tried FIRST and gated on a cheap probe. The gate matters more than
    # the speedup: without it, a machine lacking the fork binary would spend
    # minutes inside serve_up()'s retry before falling back. With it, absence
    # costs one refused connection every twenty seconds and nothing else, so
    # this path is safe to ship to end users who have no fork at all.
    #
    # The old verbatim lookup below is NOT deleted. It is the floor: it needs
    # no server, no GPU and no embedder, and it still answers the objections it
    # recognises. Jev raises that floor; it does not replace it.
    if profile is not False:
        try:
            import taviel_decide as TD
            if TD.available():
                import taviel_frontdoor as FD
                r = FD.answer(query, profile if isinstance(profile, dict) else None,
                              instant_only=instant_only)
                if r is None:
                    # instant_only and the door deferred: the caller wants to
                    # reason with its own, better model. Say so plainly.
                    return {"answer": "", "source": "defer", "stripped": []}
                if r and r.get("answer"):
                    r.setdefault("stripped", [])
                    r["seed"] = seed
                    return r
        except Exception:
            # A decision that fails mid-turn must not cost the next question a
            # second doomed round-trip.
            try:
                import taviel_decide as TD
                TD.unavailable()
            except Exception:
                pass

    try:
        import taviel_apologetics as AP
        e = AP.gauntlet_entry(query)
        if e:
            return {"answer": AP.present(e, seed=seed), "source": "vetted",
                    "round": e.get("n"), "seed": seed, "stripped": []}
    except Exception:
        pass
    # Only short-circuit the DEFAULT generator: a caller who passed their own
    # gen (the phone's on-device LiteRT, a cloud endpoint) is not described by
    # a probe of these two local ports.
    if gen is None and not _gen_available():
        return {"answer": _offline_answer(query), "source": "offline",
                "stripped": []}
    try:
        r = reason(query, gen=gen, system=system)
        r["source"] = "reasoned"
        return r
    except Exception:
        # NOTHING REACHABLE -- and the law still holds: "not answering is poor
        # answering... it should always answer." Before this, a machine with
        # no model server at all raised URLError out of serve() for any
        # question the verbatim gauntlet did not recognise, which is exactly
        # the machine most end users are on. The proof's control arm caught
        # it.
        #
        # So: say plainly what is not available, and offer the nearest
        # questions that DO have vetted answers sitting on disk. That needs no
        # server, no embedder and no GPU -- it is idf over a local JSON.
        return {"answer": _offline_answer(query), "source": "offline",
                "stripped": []}


def _offline_answer(query):
    txt = ("I cannot reason on that right now -- the model that thinks it "
           "through is not running on this machine.")
    try:
        import taviel_apologetics as AP
        near = AP.nearest_questions(query, k=3)
    except Exception:
        near = []
    if near:
        txt += ("\n\nThese are near what you asked, and I can answer them "
                "fully right now, offline:\n"
                + "\n".join("  • " + q for q in near))
    else:
        txt += ("\n\nAsk me about a verse by its reference and I will read it "
                "to you from the text itself, which needs nothing running.")
    return txt


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

    # verse support at 100 percent, mechanically (prove_taviel_verify: every
    # category 20/20): the checker validates existence, grounding-membership,
    # and word-for-word faithfulness against watchman.db. A CLEAN draft ships
    # as-is -- the whole second generation is saved. A draft with violations
    # gets ONE targeted rewrite naming exactly what the checker caught.
    try:
        import taviel_verify as TV
        checked = TV.check_draft(draft, allowed or None)
        bad = sorted({c["ref"] for c in checked if not c["ok"]})
    except Exception:
        used = []
        try:
            import tav_scripture as TS
            used = [r if isinstance(r, str) else r.get("ref", "")
                    for r in (TS.find_refs(draft) or [])]
        except Exception:
            pass
        bad = sorted({r for r in used if r and r not in allowed})
    if not bad:
        return {"answer": draft, "draft": draft, "stripped": []}

    refined = gen(system, grounding + "\n\nA first draft answer to \"" + query + "\" was:\n\"" +
                  draft[:1000] + "\"\n\nRewrite it into a FINAL answer that answers ONLY this "
                  "question, directly, in plain flowing prose a skeptic could follow; drops any "
                  "sentence that merely recites doctrine not asked; REMOVES these unverifiable "
                  "references entirely -> " + ", ".join(bad) + "; and cites "
                  "a verse only if it truly says what you claim.\nFINAL: /no_think", 360)
    # the rewrite is itself a generation, so it faces the same checker; any
    # reference still failing is stripped mechanically -- code has the last word.
    try:
        import taviel_verify as TV
        refined, still = TV.enforce(refined, allowed or None)
        bad = sorted(set(bad) | {c["ref"] for c in still})
    except Exception:
        pass
    return {"answer": refined, "draft": draft, "stripped": bad}
