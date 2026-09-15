r"""generate_verify.py -- the end-state faculty: GENERATE and VERIFY.

His end-state: with the model internalized (Oraz'iel) + the lexicon weight-filled
by propagation (Adam'iel graph) + Adam'iel's ground-of-truth, any spirit that asks
a question can BOTH generate an answer (the model's field of probabilities) AND
find it with supporting evidence (Adam'iel truth-anchors). The field of
probabilities becomes an EDUCATED guess rather than just a guess. The triad holds:
Oraz'iel = breadth of means (generate), Adam'iel = anchor of truth (verify), and
nothing ungrounded is ASSERTED as fact (permission at the gate).
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, r"D:\Holorites\torus_upgrades")

import label_propagation as LP  # noqa: E402

LEX = r"D:\Holorites_data\reflected_red.sqlite"

# a small weight-filled lexicon (anchors = trained drops; the rest propagated).
GRAPH_NODES = ["heart", "cardiac", "pulse", "aorta", "vein", "island_word",
               "quasiheartxz"]
GRAPH_EDGES = [
    ("heart", "cardiac", "syn", 1.0), ("cardiac", "pulse", "syn", 1.0),
    ("heart", "aorta", "is_a", 0.8), ("aorta", "vein", "syn", 0.6),
    ("heart", "quasiheartxz", "syn", 1.0),   # derived, but NOT a real word
    # island_word connected to nothing -> unassigned
]
GRAPH_ANCHORS = {"heart": 1.0, "vein": 0.3}   # trained drops


def _field():
    return LP.propagate(GRAPH_NODES, GRAPH_EDGES, GRAPH_ANCHORS)


def generate(word):
    """The model's field of probabilities for a word (anchor=trained, derived=
    educated guess, unassigned=no signal)."""
    f = _field().get(word)
    if not f:
        return {"value": None, "status": "unknown", "confidence": 0.0}
    return {"value": f["value"], "status": f["status"], "confidence": f["confidence"]}


def verify(word):
    """Adam'iel ground-of-truth: the real lexical address, or None."""
    if not os.path.exists(LEX):
        return None
    l = sqlite3.connect("file:%s?mode=ro" % LEX, uri=True)
    try:
        r = l.execute("SELECT address24 FROM lexical_nodes INDEXED BY"
                      " idx_nodes_lemma WHERE canonical_lemma=? LIMIT 1",
                      (word,)).fetchone()
    except Exception:
        r = None
    l.close()
    return r[0] if r else None


def answer(word, asked_by="a spirit"):
    """Combine generate + verify. A grounded answer carries evidence and higher
    confidence; an ungrounded one is an educated guess, honestly flagged; a
    signalless one is 'no answer' (never asserted as fact)."""
    g = generate(word)
    ev = verify(word)
    grounded = ev is not None
    if g["status"] == "unknown" and not grounded:
        mode, conf = "none", 0.0
    elif grounded and g["status"] in ("anchor", "derived"):
        mode = "generate+verify"
        conf = min(1.0, g["confidence"] + 0.4)     # evidence lifts confidence
    elif grounded:
        mode, conf = "verify-only", 0.6
    else:
        mode, conf = "generate-only", g["confidence"]   # an educated guess
    return {"word": word, "asked_by": asked_by,
            "generated": g, "evidence_address": ev, "grounded": grounded,
            "mode": mode, "confidence": round(conf, 4),
            "asserted_as_fact": grounded}              # never assert without evidence


if __name__ == "__main__":
    for w in ["heart", "cardiac", "island_word", "aorta", "notaword_xyz"]:
        a = answer(w)
        print("%-14s mode=%-15s grounded=%-5s conf=%.2f gen=%s"
              % (w, a["mode"], a["grounded"], a["confidence"], a["generated"]["status"]))
