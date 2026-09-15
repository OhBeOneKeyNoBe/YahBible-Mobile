#!/usr/bin/env python3
r"""The biblical bloodline that CONTINUES the Gnostic Lineage past Seth/Norea -- read from the
'The Family of Adam' artifact's own genealogy (bible_lineage.json: 989 people from D:\watchman).
Serves the MAIN bloodline as a spine (Adam -> ... -> Joseph) plus, beside each spine node, the
off-line children (branches) that leave the main line. All keyed to real KJV citations."""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(_HERE, "bible_lineage.json")
_BIOS_JSON = os.path.join(_HERE, "bible_lineage_bios.json")
_P = None
_TREE = None
_BIOS = None


def _load():
    global _P
    if _P is None:
        try:
            _P = json.load(open(_JSON, encoding="utf-8"))
        except Exception:
            _P = {}
    return _P


def _bios():
    global _BIOS
    if _BIOS is None:
        try:
            _BIOS = json.load(open(_BIOS_JSON, encoding="utf-8"))
        except Exception:
            _BIOS = {}
    return _BIOS


def _deepest(pid, memo, P):
    """Max generation reachable from pid (for choosing the main-line child at a fork)."""
    if pid in memo:
        return memo[pid]
    p = P.get(pid)
    if not p:
        memo[pid] = 0
        return 0
    best = p.get("gen") or 0
    for c in p.get("children", []):
        best = max(best, _deepest(c, memo, P))
    memo[pid] = best
    return best


def _person(p):
    return {"id": p["id"], "name": p["name"], "gen": p.get("gen"),
            "ref": p.get("first_ref") or p.get("source") or "",
            "meaning": p.get("meaning") or "", "father": p.get("father"),
            "mother": p.get("mother"), "age_beget": p.get("age_beget"),
            "age_death": p.get("age_death"), "disambig": p.get("disambig") or "",
            "stub": bool(p.get("stub")), "source": p.get("source") or "",
            "bio": (_bios().get(p["id"]) or {}).get("bio", "") if isinstance(_bios().get(p["id"]), dict) else (_bios().get(p["id"]) or ""),
            "nchildren": len(p.get("children", []))}


_MAXD = 9          # max depth of a branch / family sub-tree we emit
_MAXNODES = 4000   # safety cap on total emitted sub-tree nodes


def _subtree(pid, P, emitted, depth, counter, allow_refs=False):
    """A person + their descendants as nested {..., kids:[...]} nodes, so an off-line
    branch (e.g. Ham/Japheth and the whole Table of Nations under them) or a disconnected
    family renders as real clickable nodes -- not just a '+N' badge. `emitted` prevents a
    person appearing twice; depth/counter bound the tree. With allow_refs (families), a
    child already placed elsewhere (e.g. Jesus, on the main line) is shown as a LEAF
    reference so a household like Mary->Jesus still renders."""
    if pid not in P or depth > _MAXD or counter[0] >= _MAXNODES:
        return None
    if pid in emitted:
        if allow_refs and depth > 0:
            n = _person(P[pid])
            n["kids"] = []
            n["ref_only"] = True
            return n
        return None
    emitted.add(pid)
    counter[0] += 1
    node = _person(P[pid])
    kids = []
    for c in P[pid].get("children", []):
        st = _subtree(c, P, emitted, depth + 1, counter, allow_refs)
        if st:
            kids.append(st)
    node["kids"] = kids
    return node


def build():
    global _TREE
    if _TREE is not None:
        return _TREE
    P = _load()
    memo = {}
    # start at Adam
    adam = next((pid for pid, p in P.items() if p["name"] == "Adam" and p.get("gen") == 1), None)
    # 1) the main bloodline spine = follow the deepest-reaching child at each fork
    spine_ids, seen = [], set()
    cur = adam
    while cur and cur not in seen:
        seen.add(cur)
        spine_ids.append(cur)
        p = P.get(cur)
        if not p:
            break
        kids = [P[c] for c in p.get("children", []) if c in P]
        if not kids:
            break
        cur = max(kids, key=lambda c: _deepest(c["id"], memo, P))["id"]
    spine = [_person(P[pid]) for pid in spine_ids]
    spine_succ = {spine_ids[i]: spine_ids[i + 1] for i in range(len(spine_ids) - 1)}
    # 2) branches: at each spine node, every OFF-line child rendered as a full sub-tree
    #    (so Ham's & Japheth's Genesis-10 descendants become real nodes, not a +N badge)
    emitted, counter = set(spine_ids), [0]
    branches = {}
    for pid in spine_ids:
        succ = spine_succ.get(pid)
        offs = []
        for c in P[pid].get("children", []):
            if c == succ or c not in P:
                continue
            st = _subtree(c, P, emitted, 1, counter)
            if st:
                offs.append(st)
        if offs:
            branches[pid] = offs
    # 3) connected count + the disconnected FAMILIES forest (fragment clusters with children,
    #    e.g. Mary->Jesus's household, the disciples' families -- shown beside the main line)
    connected = set()

    def mark(pid):
        if pid in connected or pid not in P:
            return
        connected.add(pid)
        for c in P[pid].get("children", []):
            mark(c)
    if adam:
        mark(adam)
    frag_ids = set(pid for pid in P if pid not in connected)

    def _is_family_root(pid):
        f, m = P[pid].get("father"), P[pid].get("mother")
        return (f not in frag_ids) and (m not in frag_ids)   # no parent inside the fragment set
    family_roots = [pid for pid in frag_ids
                    if P[pid].get("children") and _is_family_root(pid)]
    family_roots.sort(key=lambda x: -_deepest(x, memo, P))
    families = []
    for pid in family_roots:
        st = _subtree(pid, P, emitted, 0, counter, allow_refs=True)
        if st and st.get("kids"):
            families.append(st)
    frag = len(frag_ids)
    _TREE = {"spine": spine, "branches": branches, "families": families,
             "total": len(P), "connected": len(connected), "fragments": frag}
    return _TREE


def person(pid):
    p = _load().get(pid)
    return _person(p) if p else None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t = build()
    print("people:", t["total"], "| connected:", t["connected"], "| fragments:", t["fragments"])
    print("spine length:", len(t["spine"]))
    print("spine:", " -> ".join("%s(%s)" % (s["name"], s["gen"]) for s in t["spine"]))
    print("\nbranch counts at first spine nodes:")
    for s in t["spine"][:12]:
        b = t["branches"].get(s["id"], [])
        if b:
            print("  %-12s branches: %s" % (s["name"], ", ".join(x["name"] for x in b)))
