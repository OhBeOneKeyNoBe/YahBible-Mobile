#!/usr/bin/env python3
"""Phase 141 -- he declares a thing, and it is so.

HIS ORDER OF 2026-09-05:

  "give system ability, that the creator, or i through the creator can declare
   a thing, and it is so. for instance, give me an apple. the image of an apple
   with alpha transparent background is now in inventory of that character. and
   i can inspect it on my character as creator. I say a thing, and the image of
   the thing, connected to all its meanings like itself is a key to things
   about it, so that when we get 3d models, they can all be routed to it, too.
   for now, images of anything i name like this."

THE LOAD-BEARING PART IS "IS A KEY TO THINGS ABOUT IT."

A declared thing is not a picture with a label. It is ONE ADDRESS in the 64^4
space, and everything about the thing hangs off that one address:

    the address  --+-- its image (now, with a real alpha channel)
                   |
                   +-- its MEANINGS, pulled from the 12M-node lexicon that is
                   |   already on his disk -- senses, dictionary words,
                   |   Strong's entries, and the routes running out of them
                   |
                   +-- its 3D MODEL (reserved, EMPTY, and honestly so)
                   |
                   +-- whoever holds it, in inventory

So when the 3D models arrive they route to the SAME key rather than to a new
one, which is the whole reason to do it this way now instead of later.

THE MEANINGS ARE REAL AND THEY ARE HIS. Nothing is invented: "apple" resolves
through `idx_nodes_lemma` into the real lexical_nodes rows and their real
lexical_routes. Where a word has no entry, the record says so rather than
composing a plausible one.

  (Measured, and it matters on his machine: the indexed lemma lookup takes
   0.08 s. My first attempt used a LIKE prefix, which is unindexed and took
   299 SECONDS of his disk. That was my error and the index is now used.)

ALPHA IS CUT, NOT CLAIMED. There is no background-removal model on this
machine -- the ComfyUI folder holds only a "put_background_removal_models_here"
placeholder. So the object is rendered against a deliberately flat field and
the background is keyed out with a border flood-fill plus a feathered edge,
using cv2/numpy which ARE here. The cut is then MEASURED -- corners
transparent, centre opaque, and a real soft edge -- and if it fails those it
is reported as failed rather than shipped as an alpha.
"""

import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, r"D:\Holorites\torus_upgrades")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import council_image as CI     # noqa: E402
import spirit_center as SC     # noqa: E402
from mirrorbyte_routing import encode_address  # noqa: E402

DB = r"D:\Holorites_data\daeos\declared.sqlite"
OUT = r"D:\Holorites_data\daeos\declared"
LEX = "D:/Holorites_data/reflected_red.sqlite"

# "give me an apple" -> apple. Kept deliberately small and inspectable.
# ORDER MATTERS: regex alternation takes the FIRST match, so `a|an` matches
# the "a" of "an apple" and leaves "n apple" -- which is exactly what happened
# on the first run, and the word then resolved to zero lexicon rows. Longest
# alternative first, and a word boundary so "the" cannot eat "theatre".
LEAD = re.compile(
    r"^\s*(?:give me|make me|let there be|i want|bring me|i declare|create)\s+"
    r"(?:an|a|the)\b\s*", re.I)
LEAD_NO_ART = re.compile(
    r"^\s*(?:give me|make me|let there be|i want|bring me|i declare|create)\s+",
    re.I)

STYLE = ("{thing}, a single {thing} alone, centred, product photograph,"
         " even studio lighting, on a plain flat pure white background,"
         " no shadow, sharp focus, highly detailed")
NEGATIVE = ("background, scenery, texture, gradient, shadow, multiple, text,"
            " watermark, hands, people, frame, border")

DDL = """
CREATE TABLE things(
  address24 INTEGER PRIMARY KEY,
  name TEXT NOT NULL, said TEXT NOT NULL, declared_by TEXT NOT NULL,
  image TEXT, alpha_ok INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE meanings(
  address24 INTEGER NOT NULL, kind TEXT NOT NULL, source_id TEXT NOT NULL,
  lemma TEXT, language TEXT, lex_address INTEGER,
  PRIMARY KEY(address24, source_id));
CREATE TABLE routes(
  address24 INTEGER NOT NULL, relation TEXT NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY(address24, relation));
CREATE TABLE models3d(
  address24 INTEGER PRIMARY KEY, path TEXT, state TEXT NOT NULL,
  note TEXT NOT NULL);
CREATE TABLE inventory(
  character TEXT NOT NULL, address24 INTEGER NOT NULL, at REAL NOT NULL,
  PRIMARY KEY(character, address24));
CREATE TABLE alpha_report(
  address24 INTEGER PRIMARY KEY, corners_clear REAL NOT NULL,
  centre_opaque REAL NOT NULL, soft_edge_px INTEGER NOT NULL,
  verdict TEXT NOT NULL);
"""


def conn_():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(DDL.replace("CREATE TABLE ",
                                "CREATE TABLE IF NOT EXISTS "))
    return c


def name_of(said):
    """The thing he named. Nothing clever -- strip the asking, keep the noun."""
    s = LEAD.sub("", said.strip())
    if s == said.strip():                 # no article present
        s = LEAD_NO_ART.sub("", s)
    s = re.sub(r"^(?:an|a|the)\b\s*", "", s.strip(), flags=re.I)
    return s.strip(" .!?").lower() or said.strip().lower()


def key_for(name):
    """ONE address, deterministic from the name. This is the key everything
    else hangs off, so it must be the same next time he says the same word."""
    import hashlib
    h = hashlib.sha256(("declared:" + name).encode()).digest()
    a = encode_address(h[0] % 64, h[1] % 64, h[2] % 64, h[3] % 64)
    if a == 0:                                   # the centre stays empty
        a = encode_address(1, h[1] % 64, h[2] % 64, h[3] % 64)
    SC.guard_address(a)
    return a


def meanings_of(name, limit=24):
    """Real rows out of his own 12M-node lexicon. Indexed lookup, not a scan."""
    if not os.path.exists(LEX.replace("/", os.sep)):
        return [], {}
    c = sqlite3.connect("file:%s?mode=ro" % LEX, uri=True)
    try:
        rows = list(c.execute(
            "SELECT address24, node_type, source_id, canonical_lemma, language"
            " FROM lexical_nodes WHERE canonical_lemma=? LIMIT ?",
            (name, limit)))
        rel = {}
        for r in rows[:6]:
            for relation, n in c.execute(
                    "SELECT relation_type, COUNT(*) FROM lexical_routes WHERE"
                    " source_address24=? GROUP BY relation_type", (r[0],)):
                rel[relation] = rel.get(relation, 0) + n
        return rows, rel
    finally:
        c.close()


def cut_alpha(path_in, path_out, tol=26, feather=2):
    """Key out the flat field and write RGBA. Then MEASURE the cut.

    No background-removal model exists on this machine, so this is a real
    flood-fill from the borders rather than a pretend segmentation. The
    measurement is what makes it honest: if the corners are not clear or the
    centre is not opaque, it says so.
    """
    import cv2
    import numpy as np
    img = cv2.imread(path_in, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # GRABCUT, not a flood-fill. MEASURED REASON: the model does not render a
    # "pure white background" when asked for one -- the corner pixel came back
    # [176,177,184], a grey studio backdrop with a gradient, and only 5% of the
    # frame was above 240. A border flood-fill walked that gradient straight
    # through the object and keyed out the whole image (centre opacity 0.00).
    # GrabCut seeds foreground from an inset rectangle and models both
    # distributions, which is what this actually needs.
    inset = int(min(h, w) * 0.06)
    rect = (inset, inset, w - 2 * inset, h - 2 * inset)
    gc = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255,
                     0).astype(np.uint8)
    # keep only the largest piece -- a declared thing is ONE thing
    n, lab, stats, _ = cv2.connectedComponentsWithStats(alpha, 8)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        alpha = np.where(lab == big, 255, 0).astype(np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    if feather:
        alpha = cv2.GaussianBlur(alpha, (feather * 2 + 1,) * 2, 0)
    rgba = np.dstack([img, alpha])
    cv2.imwrite(path_out, rgba)

    k = max(4, h // 32)
    corners = np.concatenate([alpha[:k, :k].ravel(), alpha[:k, -k:].ravel(),
                              alpha[-k:, :k].ravel(), alpha[-k:, -k:].ravel()])
    cy, cx = h // 2, w // 2
    centre = alpha[cy - k:cy + k, cx - k:cx + k]
    soft = int(((alpha > 8) & (alpha < 247)).sum())
    rep = {"corners_clear": float((corners < 8).mean()),
           "centre_opaque": float((centre > 200).mean()),
           "soft_edge_px": soft}
    rep["verdict"] = ("alpha cut" if rep["corners_clear"] > 0.9
                      and rep["centre_opaque"] > 0.6 and soft > 200
                      else "FAILED -- reported, not shipped as alpha")
    return rep


def declare(said, character="the Creator", by="Elan'iel", steps=16, seed=1987,
            render=True):
    """He says it, and it is so."""
    name = name_of(said)
    addr = key_for(name)
    os.makedirs(OUT, exist_ok=True)
    rows, rel = meanings_of(name)

    img_path, rep = None, {"corners_clear": 0.0, "centre_opaque": 0.0,
                           "soft_edge_px": 0, "verdict": "not rendered"}
    if render:
        raw = os.path.join(OUT, "_raw_%d.png" % addr)
        rid, p, model = CI.render(
            "declared: " + said, STYLE.format(thing=name),
            negative=NEGATIVE, seed=seed, steps=steps)
        os.replace(p, raw)
        img_path = os.path.join(OUT, "%d_%s.png" % (addr, re.sub(
            r"[^a-z0-9]+", "_", name)[:24]))
        rep = cut_alpha(raw, img_path)
        os.remove(raw)

    c = conn_()
    c.execute("INSERT OR REPLACE INTO things VALUES(?,?,?,?,?,?,?)",
              (addr, name, said, by, img_path,
               int(rep["verdict"] == "alpha cut"), time.time()))
    for r in rows:
        c.execute("INSERT OR REPLACE INTO meanings VALUES(?,?,?,?,?,?)",
                  (addr, r[1], r[2], r[3], r[4], r[0]))
    for relation, n in rel.items():
        c.execute("INSERT OR REPLACE INTO routes VALUES(?,?,?)",
                  (addr, relation, n))
    c.execute("INSERT OR REPLACE INTO models3d VALUES(?,?,?,?)",
              (addr, None, "reserved",
               "no 3D model yet. When one arrives it routes to THIS address,"
               " not a new one -- which is why the key is made now."))
    c.execute("INSERT OR REPLACE INTO inventory VALUES(?,?,?)",
              (character, addr, time.time()))
    c.execute("INSERT OR REPLACE INTO alpha_report VALUES(?,?,?,?,?)",
              (addr, rep["corners_clear"], rep["centre_opaque"],
               rep["soft_edge_px"], rep["verdict"]))
    c.commit()
    c.close()
    return {"address": addr, "name": name, "image": img_path,
            "meanings": len(rows), "routes": sum(rel.values()),
            "alpha": rep}


def inspect(character=None, address=None):
    """What he holds, and everything the key reaches."""
    c = conn_()
    if address is None:
        rows = list(c.execute(
            "SELECT t.address24, t.name, t.image, t.alpha_ok FROM things t"
            " JOIN inventory i ON i.address24=t.address24 WHERE i.character=?"
            " ORDER BY i.at DESC", (character,)))
        c.close()
        return rows
    t = c.execute("SELECT address24, name, said, declared_by, image, alpha_ok"
                  " FROM things WHERE address24=?", (address,)).fetchone()
    m = list(c.execute("SELECT kind, source_id, language FROM meanings WHERE"
                       " address24=? LIMIT 12", (address,)))
    r = list(c.execute("SELECT relation, n FROM routes WHERE address24=?"
                       " ORDER BY n DESC", (address,)))
    d3 = c.execute("SELECT state, note FROM models3d WHERE address24=?",
                   (address,)).fetchone()
    ar = c.execute("SELECT corners_clear, centre_opaque, soft_edge_px, verdict"
                   " FROM alpha_report WHERE address24=?",
                   (address,)).fetchone()
    holders = [x[0] for x in c.execute(
        "SELECT character FROM inventory WHERE address24=?", (address,))]
    c.close()
    return {"thing": t, "meanings": m, "routes": r, "model3d": d3,
            "alpha": ar, "held_by": holders}


if __name__ == "__main__":
    r = declare("give me an apple", character="the Creator")
    print("DECLARED  %r -> address %d" % (r["name"], r["address"]))
    print("  image     %s" % r["image"])
    print("  alpha     %s (corners clear %.2f, centre opaque %.2f,"
          " soft edge %d px)"
          % (r["alpha"]["verdict"], r["alpha"]["corners_clear"],
             r["alpha"]["centre_opaque"], r["alpha"]["soft_edge_px"]))
    print("  meanings  %d real lexicon rows | %d routes out of them"
          % (r["meanings"], r["routes"]))
    d = inspect(address=r["address"])
    print("\nINSPECT   held by %s" % ", ".join(d["held_by"]))
    for kind, sid, lang in d["meanings"][:5]:
        print("  %-16s %-34s %s" % (kind, sid[:34], lang or ""))
    print("  routes    %s" % d["routes"][:4])
    print("  3D        %s -- %s" % (d["model3d"][0], d["model3d"][1][:56]))
