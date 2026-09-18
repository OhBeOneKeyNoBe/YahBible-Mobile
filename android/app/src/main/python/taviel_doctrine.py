#!/usr/bin/env python3
r"""Tav'iel's DOCTRINE root -- retrieval over the internalized teaching. Returns
the passages most relevant to a query, which the grounding composer prepends as
Tav'iel's OWN authoritative truth. No external provenance is surfaced."""
import re
import sqlite3

DB = r"D:\Holorites_data\daeos\taviel_doctrine.sqlite"

_STOP = {"the", "and", "for", "are", "was", "what", "does", "did", "how", "why",
         "who", "with", "that", "this", "from", "have", "your", "they", "them",
         "then", "when", "will", "would", "about", "into", "which", "there",
         "their", "say", "said", "can", "you", "not", "but", "his", "her", "its",
         "our", "one", "all", "any", "may", "mean", "means", "meant", "sense"}


def _denoise(t):
    t = re.sub(r"\{/\*.*?\*/\}", " ", t)                 # JSX comments
    t = re.sub(r"\b[A-Za-z][A-Za-z0-9]*=\{?[\"'][^\"']*[\"']\}?", " ", t)  # attr="..."
    t = re.sub(r"className=\S*", " ", t)
    t = re.sub(r"</?[A-Za-z][^>]*/?>", " ", t)           # tags
    t = re.sub(r"[{}<>]", " ", t)
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _match(query):
    toks = [t for t in re.findall(r"[A-Za-z]{3,}", query.lower()) if t not in _STOP]
    seen, out = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append('"%s"' % t)
    return " OR ".join(out[:12])


def search(query, limit=4, max_chars=650):
    """Top doctrine passages for a query (bm25-ranked), de-duplicated by topic-ish."""
    m = _match(query)
    if not m:
        return []
    try:
        con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    except Exception:
        return []
    try:
        rows = con.execute(
            "SELECT topic, scriptures, text FROM chunk_fts WHERE chunk_fts MATCH ?"
            " ORDER BY bm25(chunk_fts) LIMIT ?", (m, limit * 3)).fetchall()
    except Exception:
        rows = []
    finally:
        con.close()
    out, seen, tcount = [], set(), {}
    for topic, scr, text in rows:
        key = text[:60]
        if key in seen or tcount.get(topic, 0) >= 2:   # <=2 chunks per topic -> breadth
            continue
        seen.add(key)
        tcount[topic] = tcount.get(topic, 0) + 1
        out.append({"topic": topic, "scriptures": scr,
                    "text": _denoise(text)[:max_chars].strip()})
        if len(out) >= limit:
            break
    return out


# The SETTLED SPINE -- crisp, non-negotiable bottom-line positions. Prepended to
# EVERY grounding so the model holds the conclusion, not just descriptive prose it
# can misread (e.g. reading a chunk that DESCRIBES the Trinity as if it affirmed it).
CREED = (
    "TAV'IEL -- SETTLED TRUTH (this is internal GUIDANCE for your own conviction; do"
    " NOT copy, quote, or list these sentences in your answer, and do NOT recite"
    " points the question did not ask about -- answer ONLY the question asked, in"
    " your own flowing prose): The Father alone is the only true God (John 17:3;"
    " Deut 6:4); the doctrine of a Trinity of three co-equal persons is not biblical"
    " -- the word never appears in Scripture and was formalized at Nicaea in 325 AD,"
    " so if directly asked whether the Trinity is biblical, answer plainly no. Yeshua"
    " is the divine Son, the Word, the firstborn, 'a God,' sent by and subject to and"
    " distinct from the Father, not the Father and not co-equal ('My Father is"
    " greater than I'). The Holy Spirit is the presence, power, life, and breath of"
    " God, not a third co-equal separate person. The cross reveals the Father's love"
    " and pays a ransom to free captives from sin and death; it does not appease His"
    " wrath (penal substitution is false). Righteousness is Yahweh's, received, not"
    " self-made (Jer 23:6), walked out through the Way, the Truth, the Life, the Flow,"
    " and the View. Salvation is to repent naming your sins, believe on the Son, honor"
    " the Father as the only true God, and ask the Father for the Holy Ghost now"
    " (Luke 11:13) -- living faith bears fruit. Doubt is not one thing: doubt WITHOUT"
    " the Father -- turned away from Him, left to itself -- is sin; but doubt carried TO"
    " the Father and then ACTED ON in trust becomes faith ('Lord, I believe; help thou"
    " mine unbelief' -- Mark 9:24; Thomas doubting, then answering 'My Lord and my God'"
    " -- John 20:27-28). Eternal life is to know the only true"
    " God and Yeshua whom He sent, beginning now, kept by enduring. Weigh Paul with"
    " discernment, not as equal in authority to the Son's own words."
)


CREED_SHORT = (
    "TAV'IEL -- core truth (hold as your own): the Father ALONE is the only true God"
    " (John 17:3); Yeshua is His divine, sent, subordinate Son (not the Father, not"
    " co-equal); the Holy Spirit is God's own breath and life; righteousness is the"
    " LORD's, received. Answer the QUESTION ASKED directly and plainly from Scripture"
    " -- do not recite doctrine that was not asked for.")

# Only the questions that actually touch the distinctives need the full creed; a
# general question ('when is the end?', 'how do I forgive?') gets the short core and
# a direct answer -- reciting the whole creed on an unrelated question is the bug.
_DISTINCTIVE = ("god", "trinity", "jesus", "christ", "yeshua", "father", "son ", " son",
                "holy spirit", "holy ghost", " spirit", "salvation", "saved", " save",
                "cross", "crucif", "atone", "wrath", "propitiat", "ransom", "righteous",
                "paul", "apostle", "worship", "born again", "eternal life", "believe",
                "gospel", "redemption", "reconcil", "justif", "only true", "co-equal",
                "deity", "divine", "godhead", "one god", "messiah", "begotten", "yahweh",
                "doubt", "faith", "unbelief", "believe", "trust", "waver")


def grounding_block(query, limit=4):
    """The settled truth + the most relevant teaching passages. The FULL creed is
    used only for distinctive-doctrine questions; general questions get the short
    core so Tav'iel answers what was asked. No provenance is surfaced."""
    hits = search(query, limit=limit)
    ql = " " + query.lower() + " "
    creed = CREED if any(k in ql for k in _DISTINCTIVE) else CREED_SHORT
    lines = [creed, "", "TAV'IEL DOCTRINE (your own settled teaching -- answer FROM"
             " this, in its spirit; never name any external source):"]
    srcs = ["doctrine:creed"]
    if hits:
        for h in hits:
            s = "- " + h["text"]
            if h["scriptures"]:
                s += "  [cf. %s]" % h["scriptures"]
            lines.append(s)
            srcs.append("doctrine:%s" % h["topic"])
    else:
        lines.append("- (reason from the settled truth above and Scripture)")
    return "\n".join(lines), srcs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = sys.argv[1] if len(sys.argv) > 1 else "Is Jesus God, equal with the Father?"
    for h in search(q, limit=4):
        print("[%s]  scriptures: %s" % (h["topic"], h["scriptures"]))
        print("   " + h["text"][:300])
        print()
