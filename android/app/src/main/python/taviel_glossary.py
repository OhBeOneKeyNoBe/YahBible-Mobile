#!/usr/bin/env python3
r"""Gnostic / special-terms glossary for the Nag Hammadi + Gnostic Bible reader. When
a word is clicked, its authoritative gnostic definition (if any) is shown FIRST, and
proper-name identities the lexicon lacks (e.g. Barbelo) get a definition at all."""
import json
import os

PATH = r"D:\Holorites_data\daeos\gnostic_glossary.json"
_G = None


def _load():
    global _G
    if _G is not None:
        return _G
    try:
        raw = json.load(open(PATH, encoding="utf-8"))
        _G = {k.lower().strip(): v for k, v in raw.items()}
    except Exception:
        _G = {}
    return _G


def define(w):
    """Return a glossary sense dict for a word, or None."""
    g = _load().get((w or "").lower().strip())
    if not g:
        return None
    return {"pos": (g.get("type") or "gnostic term"),
            "gloss": g.get("def") or g.get("definition") or "",
            "lang": "Gnostic"}


def count():
    return len(_load())
