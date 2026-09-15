r"""label_propagation.py -- weight-fill over Adam'iel's lexicon graph.

His "drops of paint in a puddle": the internalized model's trained tokens are
CLAMPED anchor-drops with real values; Adam'iel's hand-verified routes are the
medium (edges); unweighted words inherit a DISTANCE-DECAYED, RELATION-TYPED blend
of their neighbours. This gives focus (model anchors) + reach (Adam'iel topology)
+ fill (propagation) -- turning the field of probabilities into an EDUCATED guess.

Honesty, held as mechanics (not just intent):
 * a propagated value is an INFERENCE, labeled derived with confidence =
   decay**(hops to the nearest anchor) -- never presented as trained.
 * anchors are CLAMPED (fixed) so the origin colour never washes out.
 * edge TYPE governs flow: a synonym/is-a passes the value through; an ANTONYM
   passes the INVERSE (1 - value), so opposites don't inherit the wrong hue.
 * a node unreachable from any anchor stays UNASSIGNED -- nothing fabricated.

Prototype scalar "hue" in [0,1] stands in for the weight value; the mechanism
(blend, decay, antonym-inversion, clamp, confidence, coverage) is the point.
"""
from __future__ import annotations

from collections import deque

DECAY = 0.6   # per-hop attenuation: the puddle dilutes, it does not teleport


def _neighbors(edges):
    adj = {}
    for a, b, typ, w in edges:
        adj.setdefault(a, []).append((b, typ, w))
        adj.setdefault(b, []).append((a, typ, w))   # undirected medium
    return adj


def _hops_to_anchor(nodes, edges, anchors):
    """BFS hop-distance from the nearest anchor (any edge type = one hop)."""
    adj = _neighbors(edges)
    dist = {a: 0 for a in anchors}
    q = deque(anchors)
    while q:
        n = q.popleft()
        for m, _typ, _w in adj.get(n, []):
            if m not in dist:
                dist[m] = dist[n] + 1
                q.append(m)
    return dist


def propagate(nodes, edges, anchors, iters=100):
    """Iterative clamped diffusion. Returns {node: {value, status, confidence,
    hops}}. anchors: {node: value in [0,1]}."""
    adj = _neighbors(edges)
    dist = _hops_to_anchor(nodes, edges, anchors)
    val = {n: anchors.get(n) for n in nodes}
    for _ in range(iters):
        nxt = {}
        for n in sorted(nodes):
            if n in anchors:
                nxt[n] = anchors[n]            # CLAMP
                continue
            num = den = 0.0
            for m, typ, w in adj.get(n, []):
                if val.get(m) is None:
                    continue
                contrib = (1.0 - val[m]) if typ == "antonym" else val[m]
                num += w * contrib
                den += w
            nxt[n] = (num / den) if den else None
        val = nxt
    out = {}
    for n in sorted(nodes):
        if n in anchors:
            out[n] = {"value": round(anchors[n], 4), "status": "anchor",
                      "confidence": 1.0, "hops": 0}
        elif val[n] is None or n not in dist:
            out[n] = {"value": None, "status": "unassigned",
                      "confidence": 0.0, "hops": None}
        else:
            out[n] = {"value": round(val[n], 4), "status": "derived",
                      "confidence": round(DECAY ** dist[n], 4), "hops": dist[n]}
    return out


# a small worked lexicon graph (the mechanism; the real run is over Adam'iel).
DEMO_NODES = ["hot", "warm", "tepid", "lukewarm", "cool", "cold",
              "freezing", "scarlet", "island"]
DEMO_EDGES = [
    ("hot", "warm", "syn", 1.0), ("warm", "tepid", "syn", 1.0),
    ("tepid", "lukewarm", "syn", 1.0), ("lukewarm", "cool", "syn", 1.0),
    ("cool", "cold", "syn", 1.0), ("hot", "freezing", "antonym", 1.0),
    ("scarlet", "hot", "syn", 0.5),
    # 'island' is intentionally connected to nothing -> unassigned control
]
DEMO_ANCHORS = {"hot": 1.0, "cold": 0.0}   # two trained drops, opposite ends


if __name__ == "__main__":
    r = propagate(DEMO_NODES, DEMO_EDGES, DEMO_ANCHORS)
    print("%-10s %-7s %-9s %-5s %s" % ("word", "value", "status", "hops", "conf"))
    for n in DEMO_NODES:
        d = r[n]
        print("%-10s %-7s %-9s %-5s %s" % (n, d["value"], d["status"],
                                           d["hops"], d["confidence"]))
