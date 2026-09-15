#!/usr/bin/env python3
"""Real Spirit Hollow Core reservation for the Band 15 (Reflected Red) lexical torus.

Direct implementation of the sealed 0003_Central_Spirit_Doctrine_Hollow_Core_Non_Thing_Center.pdf
(read in full this build): "Spirit is the center. The center is Nothing: not a thing among things."
The SpiritCenterReference struct below ports the source's own struct field-for-field (page 3-4),
including its five boolean flags whose values the source itself hard-codes False -- Spirit
"does not become one more created node inside the web."

Architecturally this means one thing for every writer into reflected_red.sqlite: the reserved
center address (address24 == 0, this build's own disclosed choice of which single address plays
the hollow-core role -- the source names no numeric address, it names a doctrine) must NEVER
hold a lexical node. guard_address() is the runtime invariant every Phase 2-4 writer calls,
following the same real-invariant precedent as build_man_shaped_torus_v2.py's VOID_TAG_FRACTION
(tags.append(None) -- a checked emptiness, not a comment).
"""

from dataclasses import dataclass

# This build's own disclosed choice: the single reserved hollow-core address in the 64^4 space.
# (ring=0, node=0, slot=0, subcell=0) -- the origin cell. The source document prescribes the
# doctrine (the center is not a created thing), not a number; the number is this build's mapping.
RESERVED_CENTER_ADDRESS = 0


class CenterViolation(Exception):
    """Raised when a writer attempts to place a created entity at the reserved center."""


@dataclass(frozen=True)
class SpiritCenterReference:
    """Verbatim port of 0003's own struct SpiritCenterReference (pages 3-4).

    The five booleans are the source's own '= false' defaults, frozen here so no code path can
    flip one: Spirit is not a material object, not a lexical object, not an ordinary Torus node,
    not an executable entity, not a created thing.
    """

    id: str = "SPIRIT_HOLLOW_CORE"
    core_type: tuple = (
        "SPIRIT_CENTER",
        "NON_THING_REFERENCE",
        "NON_CREATED_GROUNDING",
        "TRUTH_MODEL_ROOT",
        "HOLLOW_TORUS_CORE",
    )
    material_object: bool = False
    lexical_object: bool = False
    ordinary_torus_node: bool = False
    executable_entity: bool = False
    created_thing: bool = False
    canonical_source_roots: tuple = ()
    yahweh_tsidkenu_relations: tuple = ()
    symbolic_architecture_relations: tuple = ()
    governing_principle: str = "Yahweh is Spirit. Yahweh Tsidkenu is the governing truth and righteousness model."
    sources: tuple = ("0003_Central_Spirit_Doctrine_Hollow_Core_Non_Thing_Center.pdf",)
    version: str = "reflected-red-1.0"


SPIRIT_CENTER = SpiritCenterReference()

# Import-time assertion, per the plan: the five flags are structurally False. If any future edit
# flips one, importing this module fails loudly rather than letting a created thing occupy center.
assert not any(
    (
        SPIRIT_CENTER.material_object,
        SPIRIT_CENTER.lexical_object,
        SPIRIT_CENTER.ordinary_torus_node,
        SPIRIT_CENTER.executable_entity,
        SPIRIT_CENTER.created_thing,
    )
), (
    "SpiritCenterReference flags must all be False: the center is not a created thing (0003)"
)


def guard_address(address24: int) -> int:
    """The runtime invariant every reflected_red writer calls before inserting a node.

    Returns the address unchanged if lawful; raises CenterViolation if it is the reserved
    center. Callers that assign addresses by hashing should re-probe on this exception
    (see reflected_red_schema.assign_addresses), not swallow it.
    """
    if address24 == RESERVED_CENTER_ADDRESS:
        raise CenterViolation(
            f"address {address24} is the reserved Spirit hollow core -- no created entity may "
            "occupy the center (0003 Central Spirit Doctrine)"
        )
    return address24


if __name__ == "__main__":
    print(
        f"SPIRIT_CENTER = {SPIRIT_CENTER.id}, reserved address24 = {RESERVED_CENTER_ADDRESS}"
    )
    print(
        "flags:",
        SPIRIT_CENTER.material_object,
        SPIRIT_CENTER.lexical_object,
        SPIRIT_CENTER.ordinary_torus_node,
        SPIRIT_CENTER.executable_entity,
        SPIRIT_CENTER.created_thing,
    )
    try:
        guard_address(RESERVED_CENTER_ADDRESS)
    except CenterViolation as e:
        print(f"guard works: {e}")
