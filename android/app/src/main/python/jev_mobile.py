r"""JEV ON THE PHONE -- the instant layer, numpy only.

This is the whole of Jev that a phone can run, and measurement says that is
most of it. Three facts made it possible, each established before a line of
this file was written:

  THE JUDGE IS OPTIONAL.  sweep_webrules.py over 2,406 held-out askings: the
      shipped rule (LLM judge, p>=0.60, resemblance>=0.70) commits 39.7%
      correct at 0.8% wrong; dropping the judge entirely and keeping only
      retrieval top-1 plus resemblance>=0.70 commits 46.8% correct at 1.9%
      wrong, upper bound 2.4% -- under the standing 3% bar. MORE coverage
      without the model, at a wrongness the project already accepts.

  THE EMBEDDER FITS IN NUMPY.  bge-small is a 12-layer BERT. jev_embed_np runs
      it in numpy and agrees with llama.cpp at cosine 0.9999, with identical
      tokenisation (prove_jev_embed, 15/15 against llama-server's /tokenize).

  numpy RUNS ON ANDROID.  Chaquopy publishes numpy 1.26.2 for cp312/arm64-v8a.

So the phone needs no llama.cpp, no ARM build of the decision fork, no ONNX
runtime, no LiteRT and no WebGPU. It needs 41 MB of assets and arithmetic.

WHAT IS DELIBERATELY ABSENT. literalize() restates a figurative asking and
re-routes it, and it is the only measured fix for the weak fields (spatial
22->40, musical 18->30). It is a generation step and there is no generator
here, so those askings defer on the phone as they did before. Saying that
plainly is better than pretending a 41 MB package is the whole desktop.
"""
from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# WHERE THE PACKAGE LIVES. The phone already has a convention for downloaded
# components -- tav_llm_mobile keeps its LiteRT model at $YAHBIBLE_BASE/ai --
# so Jev uses $YAHBIBLE_BASE/jev rather than inventing a second mechanism the
# Settings screen would have to learn. On the desktop, where YAHBIBLE_BASE is
# unset, it falls back to the folder build_jev_mobile.py writes.
_BASE = os.environ.get("YAHBIBLE_BASE")
ASSETS = os.environ.get(
    "JEV_MOBILE_ASSETS",
    os.path.join(_BASE, "jev") if _BASE else os.path.join(HERE, "jev_mobile"))

FILES = ("bge_small_q8.npz", "bge_small_vocab.json", "jev_index.npz")
HF_REPO = "OhBeOneKeyNoBe/YahBible-Mobile"
HF_PREFIX = "jev/"

COS_GATE = 0.60        # scope: is this even in scope
KNN_K, KNN_POWER = 10, 6

# RESEMBLANCE FLOOR -- 0.74, chosen by sweep_jev_mobile.py over 600 held-out
# askings and 10 off-scope traps, reported as a pair:
#
#   floor 0.70   52.5% correct, wrong UB 4.8%   <- over the 3.0% bar
#   floor 0.74   41.9% correct, wrong UB 2.5%   <- shipped
#   floor 0.78   30.4% correct, wrong UB 0.5%
#
# TWO THINGS THE SWEEP CORRECTED, both of which I had asserted:
#
# I blamed the wrongness on having widened this witness to the best of a
# round's base views instead of its own question. The witness choice moves the
# result by 0.2 to 0.6 points -- it is irrelevant. The FLOOR was the whole
# cause. Retrieval dominance over the runner-up adds nothing either, at any
# floor, so it is not applied.
#
# And the small embedder has a measurable price. At this same 0.70 floor the
# desktop's bge-base holds a 2.4% upper bound where bge-small gives 4.8%; to
# reach equal safety the phone needs 0.74 and pays about five points of
# coverage (41.9% against 46.8%). That is what 384 dimensions cost, and it is
# the honest reason the phone answers fewer questions than the desktop rather
# than any difference in the answers themselves.
DIRECT_FLOOR = 0.74

_W = _TOK = _IDX = None


# ------------------------------------------------------------- embedder ----
def _load_embedder():
    """Rebuild the exact q8_0 values the parity proof verified."""
    global _W, _TOK
    if _W is not None:
        return
    import jev_embed_np as JE

    z = np.load(os.path.join(ASSETS, "bge_small_q8.npz"))
    vocab = json.load(open(os.path.join(ASSETS, "bge_small_vocab.json"),
                           encoding="utf-8"))
    W = {}
    for key in z.files:
        if key.startswith("f32:"):
            W[key[4:]] = z[key]
    for key in z.files:
        if key.startswith("q8:"):
            name = key[3:]
            shape = tuple(int(x) for x in z["shape:" + name])
            W[name] = JE._dequant_q8_0(z[key], shape)
    meta = vocab["meta"]
    _W = JE.Embedder(weights=W, meta=meta, tokens=vocab["tokens"],
                     ids=vocab["ids"])
    _TOK = _W.tok


def embed(texts):
    """Same signature and same space as taviel_decide.embed."""
    _load_embedder()
    if isinstance(texts, str):
        texts = [texts]
    return _W.encode_many(texts).tolist()


# ---------------------------------------------------------------- index ----
def _load_index():
    global _IDX
    if _IDX is not None:
        return _IDX
    z = np.load(os.path.join(ASSETS, "jev_index.npz"))
    var = z["var_q"].astype(np.float32) * z["var_scale"][:, None]
    var /= (np.linalg.norm(var, axis=1, keepdims=True) + 1e-9)
    _IDX = {"base": z["base"], "base_owner": z["base_owner"],
            "var": var, "var_owner": z["var_owner"]}
    return _IDX


def available():
    """Is the phone package present? Cheap, no model load."""
    return all(os.path.isfile(os.path.join(ASSETS, f)) for f in FILES)


def install(progress=None):
    """Fetch the 41 MB package into $YAHBIBLE_BASE/jev. Returns True if ready.

    Downloaded rather than bundled, for the same reason the LiteRT model is:
    it would add 41 MB to every APK including the copies on devices that will
    never have the storage to spare, and Settings already knows how to offer a
    component. Once fetched it is never fetched again, so the plane test holds
    from the second launch onward -- and until then the app answers from the
    vetted set by word match, as it did before Jev existed.

    Each file is written to a .part and renamed only when whole: a half-written
    npz that numpy refuses to load, sitting where `available()` says a package
    is installed, would be worse than no package at all.
    """
    os.makedirs(ASSETS, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return False
    import shutil
    for i, f in enumerate(FILES):
        dest = os.path.join(ASSETS, f)
        if os.path.isfile(dest):
            continue
        if progress:
            progress(f, i, len(FILES))
        try:
            cached = hf_hub_download(repo_id=HF_REPO, filename=HF_PREFIX + f,
                                     repo_type="model")
            tmp = dest + ".part"
            shutil.copy2(cached, tmp)
            os.replace(tmp, dest)
        except Exception:
            return False
    return available()


# --------------------------------------------------------------- router ----
def route(question, threshold=DIRECT_FLOOR, cos_gate=COS_GATE):
    """(round|None, score, diag) -- the judge-free rule, measured.

    Retrieval ranks by the same knn vote the desktop uses (k=10, cosine^6 over
    the nearest VECTORS), and then TWO embedder-only witnesses must agree:

      the SCOPE gate   the best BASE view must reach cos_gate, which is where
                       out-of-scope is caught. Measured separation: real
                       askings 0.782/0.631/0.613 against off-topic
                       0.577/0.520/0.507/0.452.
      the RESEMBLANCE  the chosen round's own question must itself reach
          witness      `threshold` against the asking. This is the third
                       witness from the desktop, and here it is the second AND
                       last -- so it carries more weight, not less.

    No judge, so there is nothing to disagree with retrieval; the resemblance
    check is doing that job. That is why its floor is not loosened to buy
    coverage.
    """
    _load_embedder()
    idx = _load_index()
    q = np.asarray(embed(question)[0], dtype=np.float32)

    base_sims = idx["base"] @ q
    scope = float(base_sims.max()) if base_sims.size else 0.0
    if scope < cos_gate:
        return None, scope, {"blocked": "scope"}

    sims = idx["var"] @ q
    kk = min(KNN_K, sims.shape[0])
    top = np.argpartition(-sims, kk - 1)[:kk]
    acc = {}
    for j in top:
        o = int(idx["var_owner"][j])
        acc[o] = acc.get(o, 0.0) + float(sims[j]) ** KNN_POWER
    if not acc:
        return None, scope, {"blocked": "empty"}
    order = sorted(acc, key=acc.get, reverse=True)
    best = order[0]

    rows = np.where(idx["base_owner"] == best)[0]
    res = float(base_sims[rows].max()) if rows.size else 0.0
    if res < threshold:
        return None, res, {"blocked": "resemblance", "round": best,
                           "scope": scope}
    return best, res, {"scope": scope, "resemblance": res,
                       "candidates": order[:8]}


def suggest(question, k=3, exclude=None):
    """Nearest recorded questions by BASE cosine -- for the always-answer law.

    Ranked by base view, not by the router's knn vote: the vote is tuned to
    pick ONE round and its ordering below the top is not meaningful.
    """
    _load_embedder()
    idx = _load_index()
    q = np.asarray(embed(question)[0], dtype=np.float32)
    sims = idx["base"] @ q
    byround = {}
    for i, o in enumerate(idx["base_owner"].tolist()):
        s = float(sims[i])
        if s > byround.get(o, -2.0):
            byround[o] = s
    if exclude is not None:
        byround.pop(int(exclude), None)
    return sorted(byround.items(), key=lambda x: -x[1])[:k]


def diagnostics():
    """What tier is this device on, and why -- for the UI to state plainly."""
    d = {"assets": available(), "embedder": False, "index": 0, "judge": False,
         "literalize": False}
    if not d["assets"]:
        d["why"] = ("The Jev package is not installed on this device, so "
                    "answers come from the recorded set by word match only.")
        return d
    try:
        _load_embedder()
        d["embedder"] = True
        d["index"] = int(_load_index()["var"].shape[0])
        d["why"] = ("Jev is running here: questions are matched by meaning, "
                    "not just by words. Reasoning about questions with no "
                    "recorded answer needs a model this device does not have.")
    except Exception as ex:
        d["why"] = f"The Jev package is present but did not load ({ex!r})."
    return d
