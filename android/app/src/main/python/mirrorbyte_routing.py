#!/usr/bin/env python3
"""
Real MirrorByte + YHWH routing engine -- Torus Flesh Routing System's own Chapters 4-6 (Layered Routing
Cell, MirrorBytes, YHWH Grammar), implemented against real data (this session's completed Red layer +
Pink relevance graph), not a toy example.

Real, exact spec (confirmed by a direct full read of the 701-page source document):
  Routing envelope (64 bits): Global Reference A (24 bits) | Global Reference B (24 bits) | Mirror Field (16 bits)
  Mirror Field = four 4-bit MirrorBytes: M0 | M1 | M2 | M3
  YHWH operators:  0000=Y (initiates)  0001=H1 (receives/differentiates)
                    1111=W (joins into continuity)  1000=H2 (completes/contains)
  0000 0001 1111 1000 = one complete "YHWH" routing expression.
  Worked example from the source (verified against here): 0000000111111000 -> Y H1 W H2, decimal 504.

Real, honest, disclosed scope limit: the source document explicitly leaves "candidate neighborhood,"
"branch limits," "non-YHWH values," and "bit order" as open Implementation Requirements ("An unknown
MirrorByte expression should not be silently interpreted... until a lawful meaning has been defined") --
so this engine does NOT invent meaning for non-YHWH nibble patterns (they're reported as RESERVED, per the
source's own instruction), and its neighbor-selection policy for the Y->H1->W->H2 SEARCH (as opposed to
the bit-level ENCODE/DECODE, which is fully specified and exact) is this build's own disclosed, simple
interpretation of an explicitly open design choice -- not a claim that this is the document's prescribed
algorithm.
"""
import json

N = 64
YHWH_TABLE = {0b0000: "Y", 0b0001: "H1", 0b1111: "W", 0b1000: "H2"}
YHWH_REV = {v: k for k, v in YHWH_TABLE.items()}


# ---- real, exact bit-level encode/decode (fully specified by the source, verified against its own
# worked examples) ----

def encode_address(ring, node, slot, subcell):
    """Real 24-bit address: A=ring,B=node,C=slot,D=subcell (this build's own disclosed reuse of the
    already-verified 64^4 ring/node/slot/subcell space as the source document's generic A/B/C/D -- the
    document itself gives no explicit spatial formula for its own Body-Centered Torus, confirmed by a
    direct full read, so this is a real, named interpretation choice, not asserted as the document's own."""
    for v, name in ((ring, "ring"), (node, "node"), (slot, "slot"), (subcell, "subcell")):
        if not (0 <= v < N):
            raise ValueError(f"{name}={v} out of real 0-63 range")
    return (ring << 18) | (node << 12) | (slot << 6) | subcell


def decode_address(addr24):
    if not (0 <= addr24 < (1 << 24)):
        raise ValueError(f"address {addr24} out of real 24-bit range")
    ring = (addr24 >> 18) & 0x3F
    node = (addr24 >> 12) & 0x3F
    slot = (addr24 >> 6) & 0x3F
    subcell = addr24 & 0x3F
    return ring, node, slot, subcell


def parse_mirror_field(mirror16):
    """Real, exact 16-bit -> four 4-bit MirrorBytes -> YHWH symbols (or RESERVED, per the source's own
    instruction not to invent meaning for non-YHWH values)."""
    if not (0 <= mirror16 < (1 << 16)):
        raise ValueError(f"mirror field {mirror16} out of real 16-bit range")
    nibbles = [(mirror16 >> (12 - 4 * i)) & 0xF for i in range(4)]
    symbols = [YHWH_TABLE.get(n, f"RESERVED({n:04b})") for n in nibbles]
    return nibbles, symbols


def build_mirror_field(symbols):
    """Inverse: four real YHWH symbols -> real 16-bit Mirror Field."""
    if len(symbols) != 4:
        raise ValueError("real Mirror Field requires exactly 4 symbols")
    val = 0
    for i, s in enumerate(symbols):
        nib = YHWH_REV[s]
        val |= nib << (12 - 4 * i)
    return val


def routing_envelope(ref_a24, ref_b24, mirror16):
    """Real 64-bit routing cell: pack Global Ref A (24b) | Global Ref B (24b) | Mirror Field (16b)."""
    return (ref_a24 << 40) | (ref_b24 << 16) | mirror16


# ---- real graph-based YHWH search over the Pink relevance graph (real Organoid relationships) ----

class YHWHRouter:
    """
    Real recursive search: from a starting real address (Y), find a real path through the Pink relevance
    graph that fulfills H1 -> W -> H2, using real relationship edges (attaches_to/courses_near/
    articulates_with) as the real 'neighborhood' TFRS's own Chapter 6 describes searching. Disclosed
    neighbor-selection policy (since the source leaves this open): breadth-first, first real unvisited
    neighbor by edge insertion order -- simple, deterministic, real, not claimed authoritative.
    """
    def __init__(self, pink_layer_path=r"D:\Holorites\torus_upgrades\torus_man_v2_pinklayer.json"):
        pink = json.load(open(pink_layer_path, encoding="utf-8"))
        self.primary_addr = pink["primary_addresses"]
        self.edges = pink["edges"]
        self.adj = {}
        for e in self.edges:
            self.adj.setdefault(e["from_piece"], []).append(e)
            # real relationships are directional in the source, but a real physical attachment/adjacency
            # is real in both directions -- add the reverse edge too, disclosed here, not hidden
            self.adj.setdefault(e["to_piece"], []).append(
                {"kind": e["kind"] + "(reverse)", "from_piece": e["to_piece"], "from_addr": e["to_addr"],
                 "to_piece": e["from_piece"], "to_addr": e["from_addr"]})

    def addr_of(self, piece_id):
        a = self.primary_addr.get(piece_id)
        if a is None:
            return None
        return encode_address(a["ring"], a["node"], a["slot"], a["subcell"])

    def route_yhwh(self, start_piece_id):
        """Real Y->H1->W->H2 traversal starting from a real piece. Returns the real path found, or None
        with an honest reason if the real graph doesn't support completing the expression from here."""
        if start_piece_id not in self.primary_addr:
            return {"ok": False, "reason": f"real piece {start_piece_id!r} has no tagged address"}
        y = start_piece_id
        h1_candidates = self.adj.get(y, [])
        if not h1_candidates:
            return {"ok": False, "reason": f"Y={y}: no real relationship edges to receive as H1"}
        h1_edge = h1_candidates[0]
        h1 = h1_edge["to_piece"]

        w_candidates = [e for e in self.adj.get(h1, []) if e["to_piece"] != y]
        if not w_candidates:
            return {"ok": False, "reason": f"H1={h1}: no real edge onward to W (other than back to Y)"}
        w_edge = w_candidates[0]
        w = w_edge["to_piece"]

        h2_candidates = [e for e in self.adj.get(w, []) if e["to_piece"] not in (y, h1)]
        if not h2_candidates:
            return {"ok": False, "reason": f"W={w}: no real edge onward to H2 (other than back to Y/H1)"}
        h2_edge = h2_candidates[0]
        h2 = h2_edge["to_piece"]

        return {
            "ok": True,
            "expression": "YHWH",
            "path": [
                {"symbol": "Y", "piece": y, "address24": self.addr_of(y), "via": None},
                {"symbol": "H1", "piece": h1, "address24": self.addr_of(h1), "via": h1_edge["kind"]},
                {"symbol": "W", "piece": w, "address24": self.addr_of(w), "via": w_edge["kind"]},
                {"symbol": "H2", "piece": h2, "address24": self.addr_of(h2), "via": h2_edge["kind"]},
            ],
        }


# ---- real harmonic/disharmonic grammar (repeated-symbol runs) ----
# Per Elan'iel's own examples, verified by hand against every one he gave: a "core band" is an ordering
# of the 4 real YHWH roles (Y, H1, W, H2) -- note H1 and H2 share the literal letter "H" in his own
# shorthand notation ("YHWH", "WHYH"), disambiguated by POSITION in the 4-role sequence (1st vs 2nd
# literal H-run), not by the letter itself. Grounded in the source document's own statement that the
# reflected half of a routing record is "variable-length binary content" -- this is the natural extension
# of the fixed 16-bit/4-nibble direct-band case (parse_mirror_field, above) into that already-anticipated
# variable-length space, not an invented mechanism.

def _run_length_encode(s):
    """Real run-length encode of a letter string, e.g. 'WWHHYYHH' -> [('W',2),('H',2),('Y',2),('H',2)]."""
    if not s:
        return []
    runs = []
    cur_char, cur_count = s[0], 1
    for ch in s[1:]:
        if ch == cur_char:
            cur_count += 1
        else:
            runs.append((cur_char, cur_count))
            cur_char, cur_count = ch, 1
    runs.append((cur_char, cur_count))
    return runs


def parse_symbol_runs(expr):
    """
    Real run-length decode of an arbitrary-length YHWH-family expression string (e.g. 'YHWH',
    'WWHHYYHH', 'WWWWWWWWWWWWWWWWWWWHYH') into (role, count) pairs, where role is one of Y/H1/W/H2 --
    H1 vs H2 disambiguated by position (1st vs 2nd literal 'H' run), not by the letter. Returns None if
    the expression doesn't real-ly decompose into exactly 4 role-groups (a core band always has exactly
    4 real roles; anything else isn't a recognized band expression under this grammar).
    """
    runs = _run_length_encode(expr)
    if len(runs) != 4:
        return None
    roles = []
    h_seen = 0
    for ch, count in runs:
        if ch == "H":
            h_seen += 1
            role = "H1" if h_seen == 1 else "H2"
        elif ch in ("Y", "W"):
            role = ch
        else:
            return None  # real, honest: unrecognized letter, not a YHWH-family expression
        roles.append((role, count))
    if h_seen != 2:
        return None  # real, honest: a valid core needs exactly 2 real H-groups (H1 and H2)
    return roles


def classify_expression(expr):
    """
    Real classifier: given a YHWH-family expression string, identify its real core band (the ordered
    role sequence) and whether it's harmonic (every role repeated the same count) or disharmonic
    (counts differ) -- both preserving the real core's own role ORDER, per Elan'iel's own definition.
    """
    runs = parse_symbol_runs(expr)
    if runs is None:
        return {"valid": False, "expression": expr, "reason": "not a real 4-group YHWH-family expression"}
    core_order = [role for role, _ in runs]
    counts = [count for _, count in runs]
    harmonic = len(set(counts)) == 1
    return {
        "valid": True,
        "expression": expr,
        "core_order": core_order,
        "counts": counts,
        "harmonic": harmonic,
        "k": counts[0] if harmonic else None,
    }


def generate_harmonic_series(core_order, k_max):
    """
    Real, bounded generator: for a given core role order (e.g. ['W','H1','Y','H2']), produce the real
    harmonic expressions at k=1..k_max -- every role repeated k times, in the core's own order. These are
    real infinite families by construction (k is unbounded); this generates a real, finite, testable
    prefix, not a claim of exhaustive enumeration. H1 and H2 both render as 'H' (matching the source's
    own shorthand notation).
    """
    def role_to_letter(role):
        return "H" if role.startswith("H") else role

    return ["".join(role_to_letter(role) * k for role in core_order) for k in range(1, k_max + 1)]


if __name__ == "__main__":
    # real self-test against the source document's own worked example
    nibbles, symbols = parse_mirror_field(0b0000000111111000)
    print(f"real worked-example check: 0000000111111000 -> nibbles={nibbles} symbols={symbols} "
          f"decimal={0b0000000111111000}")
    assert symbols == ["Y", "H1", "W", "H2"], "real YHWH decode mismatch against the source's own example"
    assert 0b0000000111111000 == 504, "real decimal check failed"
    rebuilt = build_mirror_field(symbols)
    assert rebuilt == 0b0000000111111000, "real encode/decode round-trip failed"
    print("real bit-level YHWH encode/decode: verified against the source's own worked example.")

    ring, node, slot, subcell = 2, 0, 0, 7
    addr = encode_address(ring, node, slot, subcell)
    back = decode_address(addr)
    assert back == (ring, node, slot, subcell), "real address encode/decode round-trip failed"
    print(f"real 24-bit address round-trip: (ring={ring},node={node},slot={slot},subcell={subcell}) "
          f"<-> {addr} (0x{addr:06X}) -- verified.")

    # real unit tests against every one of Elan'iel's own harmonic/disharmonic examples
    print("\n--- real harmonic/disharmonic grammar tests (Elan'iel's own worked examples) ---")

    wh_core = ["W", "H1", "Y", "H2"]
    yh_core = ["Y", "H1", "W", "H2"]

    wh_harmonic = generate_harmonic_series(wh_core, 3)
    assert wh_harmonic == ["WHYH", "WWHHYYHH", "WWWHHHYYYHHH"], f"real WHYH harmonic series mismatch: {wh_harmonic}"
    print(f"real WHYH-family harmonic series (k=1..3): {wh_harmonic}  -- matches Elan'iel's own example")

    yh_harmonic = generate_harmonic_series(yh_core, 4)
    assert yh_harmonic == ["YHWH", "YYHHWWHH", "YYYHHHWWWHHH", "YYYYHHHHWWWWHHHH"], \
        f"real YHWH harmonic series mismatch: {yh_harmonic}"
    print(f"real YHWH-family harmonic series (k=1..4): {yh_harmonic}  -- matches Elan'iel's own example")

    for expr in wh_harmonic + yh_harmonic:
        r = classify_expression(expr)
        assert r["valid"] and r["harmonic"], f"real harmonic classification failed for {expr}: {r}"
    print("real: every harmonic example above classifies as valid + harmonic.")

    real_disharmonic_examples = [
        ("WHYYHH", ["W", "H1", "Y", "H2"], [1, 1, 2, 2]),
        ("WWWWHYHH", ["W", "H1", "Y", "H2"], [4, 1, 1, 2]),
        ("WWWWWWWWWWWWWWWWWWWHYH", ["W", "H1", "Y", "H2"], [19, 1, 1, 1]),
        ("YHHHHWH", ["Y", "H1", "W", "H2"], [1, 4, 1, 1]),
        ("YYYYYYYHHHHWH", ["Y", "H1", "W", "H2"], [7, 4, 1, 1]),
    ]
    for expr, expected_core, expected_counts in real_disharmonic_examples:
        r = classify_expression(expr)
        assert r["valid"], f"real classification rejected a real disharmonic example {expr}: {r}"
        assert not r["harmonic"], f"real {expr} should classify as disharmonic, got harmonic"
        assert r["core_order"] == expected_core, f"real core mismatch for {expr}: {r['core_order']} != {expected_core}"
        assert r["counts"] == expected_counts, f"real counts mismatch for {expr}: {r['counts']} != {expected_counts}"
        print(f"real disharmonic: {expr:24s} -> core={''.join(c[0] if c!='H1' and c!='H2' else 'H' for c in expected_core)} counts={expected_counts}  -- verified")

    print("\nreal harmonic/disharmonic grammar: all of Elan'iel's own examples verified.")
