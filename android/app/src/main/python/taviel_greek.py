"""Greek letter-by-letter dissection + isopsephy (Greek gematria), the parallel of
taviel_hebrew for the Greek side of a word study. Given a Greek glyph (the lemma the
KJV/Strong's records for a word) it returns each letter with its NAME, a short sense,
and its numeric value, plus the isopsephy total.

No pictographic 'meaning' is invented for Greek letters (unlike the Semitic aleph-bet,
Greek letters are phonetic, most borrowed from Phoenician). Each entry gives the
letter's name, transliteration, numeric value, and — where it is real — a genuine
scriptural or historical note (Alpha/Omega of Revelation; the 666 of chi-xi-stigma)."""

import unicodedata

# glyph -> (name, translit, value, note)
GREEK = {
    "α": ("Alpha", "a", 1, "the first letter; 'I am Alpha and Omega, the beginning' (Rev 1:8)."),
    "β": ("Beta", "b", 2, "from Phoenician bet (house); the second letter."),
    "γ": ("Gamma", "g", 3, "from Phoenician gimel (camel/throw)."),
    "δ": ("Delta", "d", 4, "from Phoenician dalet (door); the triangular fourth letter."),
    "ε": ("Epsilon", "e", 5, "'e psilon' = plain E; the short e-vowel."),
    "ζ": ("Zeta", "z", 7, "from Phoenician zayin; note it skips 6 (the digamma/stigma)."),
    "η": ("Eta", "e", 8, "the long e-vowel (eta), from Phoenician heth."),
    "θ": ("Theta", "th", 9, "from Phoenician teth; anciently marked on a ballot for death (thanatos)."),
    "ι": ("Iota", "i", 10, "the smallest letter — 'one jot' (iota) shall not pass (Mt 5:18)."),
    "κ": ("Kappa", "k", 20, "from Phoenician kaph (palm of the hand)."),
    "λ": ("Lambda", "l", 30, "from Phoenician lamed (ox-goad)."),
    "μ": ("Mu", "m", 40, "from Phoenician mem (water)."),
    "ν": ("Nu", "n", 50, "from Phoenician nun (fish/serpent)."),
    "ξ": ("Xi", "x", 60, "the double consonant ks; from Phoenician samekh."),
    "ο": ("Omicron", "o", 70, "'o mikron' = small O; the short o-vowel."),
    "π": ("Pi", "p", 80, "from Phoenician pe (mouth)."),
    "ρ": ("Rho", "r", 100, "from Phoenician resh (head)."),
    "σ": ("Sigma", "s", 200, "from Phoenician shin (tooth); written σ within a word."),
    "ς": ("Sigma (final)", "s", 200, "the final form of sigma, written ς at a word's end."),
    "τ": ("Tau", "t", 300, "from Phoenician taw (mark) — the cross-shaped last consonant, the sign of Ezek 9:4."),
    "υ": ("Upsilon", "y", 400, "'u psilon' = plain U; the Pythagorean 'letter of life' forking two ways."),
    "φ": ("Phi", "ph", 500, "the aspirate p; also the symbol of the golden ratio."),
    "χ": ("Chi", "ch", 600, "the X-letter; the monogram of Christ (ΧΡ, Chi-Rho)."),
    "ψ": ("Psi", "ps", 700, "the double consonant ps."),
    "ω": ("Omega", "o", 800, "'o mega' = great O, the long o and LAST letter — 'I am... Omega, the end' (Rev 1:8)."),
    # archaic numeral-letters (rare, but real — they carry values in isopsephy)
    "ϝ": ("Digamma/Stigma", "w", 6, "the archaic 6; with chi (600) and xi (60) spells 666 (Rev 13:18)."),
    "ϛ": ("Stigma", "st", 6, "the archaic numeral 6 (ligature of sigma-tau)."),
    "ϙ": ("Koppa", "q", 90, "the archaic numeral 90."),
    "ϟ": ("Koppa", "q", 90, "the archaic numeral 90."),
    "ϡ": ("Sampi", "ss", 900, "the archaic numeral 900."),
}

# fold accents/breathing marks so ἀ, ά, ᾳ ... all resolve to the base letter
_FOLD = {}


def _base(ch):
    """Strip Greek diacritics (accents, breathings, iota-subscript, dialytika) -> base letter."""
    if ch in GREEK:
        return ch
    d = unicodedata.normalize("NFD", ch)
    for c in d:
        if unicodedata.combining(c):
            continue
        lc = c.lower()
        if lc in GREEK:
            return lc
    return ""


def dissect(word):
    """Letter-by-letter dissection of a Greek string, with an isopsephy total."""
    letters, total = [], 0
    for ch in (word or ""):
        if ch.isspace() or ch in "().,·;:-—[]{}0123456789":
            continue
        b = _base(ch)
        if not b:
            continue
        name, tr, val, note = GREEK[b]
        letters.append({"glyph": ch, "name": name, "translit": tr,
                        "meaning": note, "value": val})
        total += val
    return letters, total


def _romanize(word):
    out = []
    prev = ""
    for ch in (word or ""):
        b = _base(ch)
        if not b:
            continue
        tr = GREEK[b][1]
        # gamma before a velar is 'n' (ang-, ", eg-): keep simple, use base translit
        out.append(tr)
        prev = b
    return "".join(out)


def study(word):
    """Given a Greek glyph, return its letter dissection + isopsephy. Returns None
    if the string carries no Greek letters (so the caller can hide the Greek panel)."""
    if not word:
        return None
    letters, total = dissect(word)
    if not letters:
        return None
    return {"greek": word, "translit": _romanize(word),
            "letters": letters, "isopsephy": total,
            "note": "Greek letters are phonetic; their numeric values give the isopsephy "
                    "(the Greek counterpart of gematria)."}
