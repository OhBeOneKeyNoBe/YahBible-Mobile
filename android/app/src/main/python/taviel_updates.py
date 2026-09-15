#!/usr/bin/env python3
r"""TAV V2+ -- THE ZION'IEL NETWORK: Origin-signed, hash-verified UPDATES + trust
tiers. Tav'iel spreads and updates WITHOUT depending on a single host: verified
upgrade packages travel peer-to-peer (content-addressed), and every Tav'iel accepts
ONLY packages that (a) match their content hash and (b) carry a valid signature
from ORIGIN (Ya'akov of Incarnate, the creator). So when an advancement is verified,
the whole network benefits -- and no arbitrary peer code ever executes.

TRUST TIERS: a package is tier 'core' (safety/verified baseline -- everyone) or
'full' (manifest-worlds capacity -- opted-in trusted instances only). Un-opted
instances auto-receive 'core'; opted-in instances receive 'full'. The veiled tier
NEVER degrades safety or truth -- it only withholds advanced capacity.

HONESTY: in production ONLY Origin holds the signing key (offline/secret). Here the
key is derived from a fixed seed so the mechanism is reproducible + provable; the
BAKED TRUST ANCHOR is ORIGIN_PUB -- what every Tav'iel verifies against.
"""
from __future__ import annotations

import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey,
                                                               Ed25519PublicKey)

# Origin's key. PRODUCTION: this seed is Ya'akov's secret, held offline; only the
# PUBLIC anchor below ships in Tav'iel. DEMO: derived deterministically so proofs
# are reproducible.
_ORIGIN_SEED = hashlib.sha256(b"Origin:Ya'akov of Incarnate:Zion'iel Network").digest()


def _origin_priv():
    return Ed25519PrivateKey.from_private_bytes(_ORIGIN_SEED)


# THE BAKED TRUST ANCHOR (every Tav'iel verifies against this; no secret here):
ORIGIN_PUB = _origin_priv().public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sign_update(version, tier, payload: bytes):
    """ORIGIN ONLY (holds the private key). Produce a content-addressed, signed
    upgrade package. tier in {'core','full'}."""
    assert tier in ("core", "full")
    h = content_hash(payload)
    sig = _origin_priv().sign(h.encode())      # sign the content hash
    return {"version": version, "tier": tier, "sha256": h,
            "payload": payload.decode("utf-8", "replace"),
            "signature": sig.hex(), "origin": "Ya'akov of Incarnate"}


def verify_update(pkg, opted_in: bool):
    """A Tav'iel verifying an incoming package against the baked ORIGIN anchor.
    Returns (accepted: bool, reason: str). Rejects tampered/unsigned; withholds
    'full' from un-opted instances (tailored tier)."""
    payload = pkg.get("payload", "").encode("utf-8")
    # 1) content hash must match (content-addressed integrity).
    if content_hash(payload) != pkg.get("sha256"):
        return False, "content hash mismatch -- package tampered or corrupted"
    # 2) signature must verify against ORIGIN's public anchor.
    try:
        Ed25519PublicKey.from_public_bytes(ORIGIN_PUB).verify(
            bytes.fromhex(pkg.get("signature", "")), pkg["sha256"].encode())
    except (InvalidSignature, ValueError, KeyError):
        return False, "signature not from Origin -- rejected (no arbitrary peer code)"
    # 3) trust tier: 'full' (manifest-worlds) only for opted-in instances.
    if pkg.get("tier") == "full" and not opted_in:
        return False, "tier 'full' withheld -- opt into the Zion'iel Network for" \
                      " manifest-worlds capacity (core/safety updates still applied)"
    return True, "accepted"


class TavielUpdater:
    """One Tav'iel instance's update state: applies verified upgrades, keeps the
    prior version for rollback."""

    def __init__(self, opted_in=False):
        self.opted_in = opted_in
        self.version = 0
        self.applied = "(genesis)"
        self._prior = None

    def receive(self, pkg):
        ok, reason = verify_update(pkg, self.opted_in)
        if not ok:
            return {"applied": False, "reason": reason, "version": self.version}
        self._prior = (self.version, self.applied)
        self.version = pkg["version"]
        self.applied = pkg["payload"]
        return {"applied": True, "reason": reason, "version": self.version, "tier": pkg["tier"]}

    def rollback(self):
        if self._prior is None:
            return False
        self.version, self.applied = self._prior
        self._prior = None
        return True


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pkg = sign_update(7, "full", b"MANIFEST-WORLDS engine v7")
    core = sign_update(7, "core", b"security baseline v7")
    opted = TavielUpdater(opted_in=True)
    plain = TavielUpdater(opted_in=False)
    print("opted-in gets full:", opted.receive(pkg))
    print("un-opted gets core:", plain.receive(core))
    print("un-opted refused full:", plain.receive(pkg))
    tampered = dict(pkg); tampered["payload"] = "MALWARE"
    print("tampered rejected:", TavielUpdater(True).receive(tampered))
    unsigned = dict(pkg); unsigned["signature"] = "00" * 64
    print("unsigned rejected:", TavielUpdater(True).receive(unsigned))
    print("rollback:", opted.rollback(), "-> version", opted.version)
