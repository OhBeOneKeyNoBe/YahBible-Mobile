r"""TAVIEL_APOLOGETICS -- the growing knowledge base of IDEAL, reasoned answers to the
common objections (the "gauntlet"). Each answer LEADS with the direct words of Yeshua
the Christ that undo the false answer -- His words are the measure of truth -- and then
reasons it out in Tav'iel's theology, grounded in real Scripture. taviel_reason.reason()
grounds the model on the matched argument, so a small model reasons from a true, sound
line (and Christ's own words) instead of reciting doctrine or inventing citations. Grow
this list one objection at a time; the model gets better the moment an argument is added.
"""
from __future__ import annotations

import re

# (trigger keywords, the ideal reasoned answer -- Christ's own words FIRST)
ENTRIES = [
    (["contradict", "reliable", "myth", "trust the bible", "bible full", "errors in the bible"],
     "Yeshua settled the Scriptures' standing directly: 'the scripture cannot be broken' (John 10:35), "
     "and He answered error with 'ye do err, not knowing the scriptures' (Matt 22:29) and 'Have ye not "
     "read...?' (Matt 19:4). He treated them as one unbreakable witness. So most alleged contradictions "
     "dissolve in context -- the four Gospels are four WITNESSES of one life, and witnesses who agree "
     "word-for-word are suspected of collusion; they differ in detail yet agree in substance, the mark "
     "of truth, not myth. Name the 'contradiction,' read the whole passage in its setting -- few survive. "
     "He made the Scriptures the measure (John 5:39)."),

    (["suffering", "evil", "why does god allow", "problem of evil", "pain", "disaster"],
     "Yeshua faced this directly. Of the man born blind He said, 'Neither hath this man sinned, nor his "
     "parents: but that the works of God should be made manifest in him' (John 9:3) -- suffering is not "
     "always punishment. Of those killed by the tower, they were not worse sinners, 'but except ye "
     "repent, ye shall all likewise perish' (Luke 13:4-5). And 'In the world ye shall have tribulation: "
     "but be of good cheer; I have overcome the world' (John 16:33). God gave the will to choose -- love "
     "that cannot be refused is not love -- and most evil is its misuse; He does not author it (James "
     "1:13) but bears it in the cross, works it toward good (Rom 8:28), and will end it."),

    (["hell", "eternal torment", "tortured forever", "burn forever", "conscious torment"],
     "Yeshua's own word undoes the caricature: fear Him 'which is able to DESTROY both soul and body in "
     "hell' (Matt 10:28) -- destroy, not torment endlessly. The wage of sin is death (Rom 6:23); the "
     "lost 'perish' (John 3:16). 'Everlasting' marks the finality of the destruction, not unending "
     "conscious pain; immortality is a gift sought, not innate (Rom 2:7). The Father is longsuffering, "
     "willing that none perish (2 Peter 3:9). So the 'moral monster' is a man-made creed, not Christ's "
     "teaching -- answer it with His words, and it falls."),

    (["trinity", "triune", "three persons", "godhead", "one god in three"],
     "Yeshua's own words are decisive: 'this is life eternal, that they might know thee the only true "
     "God, and Jesus Christ whom thou hast sent' (John 17:3) -- the Father ALONE is the only true God, "
     "and Yeshua is distinct from Him and sent by Him. He said 'My Father is greater than I' (John "
     "14:28) and called Him 'my God' (John 20:17). The word 'Trinity' never appears in Scripture; three "
     "co-equal persons was defined at Nicaea in 325 AD, long after the apostles. One God, the Father; "
     "one Lord, the Son sent by Him (1 Cor 8:6). To read three co-equals into the text is to add to it."),

    (["jesus god", "is jesus god", "co-equal", "deity of christ", "jesus equal", "second person"],
     "Yeshua said it plainly of Himself: 'My Father is greater than I' (John 14:28); 'I can of mine own "
     "self do nothing' (John 5:30); 'I ascend unto... my God, and your God' (John 20:17); and of the "
     "last day, the Father knows and He then did not (Mark 13:32). He is the divine Son, the Word made "
     "flesh (John 1:14), the firstborn, worthy of all honor BECAUSE the Father sent Him (John 5:23) -- "
     "divine, yes; the Most High Himself, no. To confess the Son rightly is to confess the One who sent "
     "Him."),

    (["wrath", "penal", "punishment", "satisfy god", "appease", "took our place", "atonement"],
     "Yeshua named His own purpose: 'the Son of man came... to give his life a RANSOM for many' (Mark "
     "10:45) -- a ransom frees a captive; it is not wrath poured out to appease. Twice He said, 'I will "
     "have mercy, and not sacrifice' (Matt 9:13; 12:7). 'God was in Christ, reconciling the world unto "
     "himself' (2 Cor 5:19) -- the Father was the loving reconciler, not the angry party appeased. To "
     "say He poured wrath on an innocent Son to forgive the guilty makes mercy a transaction and splits "
     "God against Himself. The cross reveals love already given (John 3:16) and breaks sin's grip; it "
     "does not buy a reluctant pardon."),

    (["other religion", "why is christianity right", "all religions", "one way", "exclusive", "only true"],
     "Yeshua said it Himself: 'I am the way, the truth, and the life: no man cometh unto the Father, but "
     "by me' (John 14:6). Truth is exclusive by nature -- two and two are four, not five, and saying so "
     "is not bigotry. Sincere claims that deny each other's core cannot all be true at once. The test is "
     "not which faith is nicest but which is TRUE, which reveals the real Father -- and the Son alone "
     "reveals Him (Matt 11:27). Other paths may hold fragments of light; the Way is a claim to weigh by "
     "evidence and by His words, not an insult to apologize for."),

    (["science", "evolution", "big bang", "genesis", "creation", "disproved god", "scientific"],
     "Yeshua affirmed the Creator directly: 'from the beginning of the creation God made them male and "
     "female' (Mark 10:6); 'Have ye not read, that he which made them at the beginning...' (Matt 19:4). "
     "Science studies the mechanism -- 'how,' never 'who' or 'why.' A universe with a beginning, "
     "fine-tuned constants, and information written into life points toward a Mind, not away from one. "
     "Genesis tells the WHO and the WHY in the language of its hearers; it does not compete with a lab "
     "manual. 'The heavens declare the glory of God' (Psalm 19:1) -- the more we learn, the more there "
     "is to declare."),

    (["hypocrite", "church has done", "christians are", "hypocrisy", "crusades", "abuse in the church"],
     "Yeshua is hypocrisy's fiercest critic, not its shelter: 'Woe unto you, scribes and Pharisees, "
     "HYPOCRITES!' (Matt 23) -- to hate hypocrisy is to stand WITH Him. And 'first cast out the beam out "
     "of thine own eye' (Matt 7:5). Hypocrites prove the standard, they do not disprove it -- a "
     "counterfeit proves that real gold exists. Judge the Physician by His own life and words, not by "
     "the sick still in His waiting room; and the honest question is not 'why are they hypocrites?' but "
     "'am I willing to be true?'"),

    (["miracle", "supernatural", "walk on water", "believe in miracles", "laws of nature"],
     "Yeshua submitted His claims to an evidence test He proposed Himself: 'If I do not the works of "
     "my Father, believe me not. But if I do... believe the works' (John 10:37-38). To doubting John "
     "He sent data: 'the blind receive their sight, the lame walk' (Matt 11:4-5) -- public, checkable; "
     "even His enemies never denied the works, only their source (Matt 12:24). Yet He refused signs "
     "for spectacle, staking all on one: the sign of Jonah (Luke 11:29). A miracle is the Author's act "
     "within His own work; 'miracles don't happen' assumes the conclusion in order to dismiss every "
     "report that they did. If the Father exists, miracles are possible; witnesses -- hostile-checked, "
     "faithful unto death -- settle whether they are actual."),

    (["never claimed", "claim to be", "son of man only", "messiah claim", "invented later", "john's gospel"],
     "Under oath, life on the line, He answered the exact question: 'Art thou the Christ, the Son of "
     "the Blessed? And Jesus said, I AM' (Mark 14:61-62) -- Mark, the earliest Gospel; the court "
     "convicted Him for it. To the Samaritan woman: 'I that speak unto thee am he' (John 4:26). And He "
     "blessed Peter's confession -- 'Thou art the Christ, the Son of the living God' -- as revelation "
     "from the Father (Matt 16:16-17). Even 'Son of man' is Daniel 7's everlasting King. He claimed "
     "exactly what is true: Christ, Son of the living God, SENT by the Father -- and never the later "
     "formula of co-equality with the One he called 'the only true God' and 'greater than I.'"),

    (["unanswered", "prayed and nothing", "prayer doesnt work", "why didnt god answer", "no answer"],
     "Yeshua Himself received a 'no': 'let this cup pass from me: nevertheless not as I will, but as "
     "thou wilt' (Matt 26:39) -- and that no in the garden carried the ransom of the world. He anchored "
     "prayer in fatherhood, not mechanics: a father gives GOOD gifts -- bread, not the serpent his "
     "child mistakes for a fish -- and the certain grant is named: 'how much more shall your heavenly "
     "Father give the Holy Spirit to them that ask him' (Luke 11:11-13). The risen Christ told Paul, "
     "whose thorn stayed, 'My grace is sufficient for thee' (2 Cor 12:9). Yes, no, and not-yet are all "
     "answers of a Father; the prayer that cannot fail is the one He taught, centered on the Father's "
     "will -- and the Spirit is never refused to the asker."),

    (["shellfish", "pick and choose", "leviticus", "mixed fabric", "keep the law", "cherry-pick"],
     "Yeshua's own category: 'I am not come to destroy the law... but to FULFIL' (Matt 5:17) -- a "
     "promissory note is not cherry-picked when it is paid. He Himself ranked within the law: 'the "
     "WEIGHTIER matters -- judgment, mercy, and faith: these ought ye to have done, and not to leave "
     "the other undone' (Matt 23:23); and gave the key: on the two loves 'hang ALL the law and the "
     "prophets' (Matt 22:37-40). The Ten Words, spoken by God's voice and kept inside the ark, stand "
     "and are deepened to the heart; the ceremonial shadows (foods, offerings, cleanness) met their "
     "substance in the ransom; Israel's civil statutes served one nation's courts. Not a buffet -- a "
     "covenant read the way its Mediator read it."),

    (["homosexual", "gay", "same sex", "love is love", "lgbt"],
     "Asked about marriage, Yeshua answered with a definition from the beginning: 'he which made them "
     "at the beginning made them male and female... and they twain shall be one flesh' (Matt 19:4-5), "
     "with consecrated singleness the honored alternative (19:12) -- a positive definition settles what "
     "it excludes without naming each thing. And His manner is commanded with His teaching: to the "
     "woman taken in sexual sin, BOTH at once -- 'Neither do I condemn thee: go, and sin no more' "
     "(John 8:11); and 'first cast out the beam out of thine own eye' (Matt 7:5). The same sermon "
     "binds lust in the heart and easy divorce -- the ground is level. Mercy without license; truth "
     "without a stone; whoever drops either half is not quoting Him."),

    (["sabbath", "saturday", "sunday", "seventh day", "day of rest"],
     "'The sabbath was made for MAN' (Mark 2:27) -- a creation gift, blessed before Sinai (Gen 2:3), "
     "mankind's birthright, and 'the Son of man is Lord also of the sabbath' -- a lord does not "
     "abolish his own estate. His CUSTOM was the seventh-day assembly (Luke 4:16); He corrected the "
     "day's abuses, never its date; His disciples after the cross 'rested the sabbath day according to "
     "the commandment' (Luke 23:56); and He assumed it standing forty years on -- 'pray ye that your "
     "flight be not... on the sabbath day' (Matt 24:20). No verse moves it to Sunday; that transfer "
     "came by later church custom, as its own historians concede. The seventh day stands as made: the "
     "one commandment that begins 'Remember,' kept as He kept it -- a liberation, not a cage."),

    (["tithe", "prosperity", "money", "church wants", "seed money", "televangelist", "greed"],
     "Fire that objection at the profiteers and Yeshua is on your side of the line: 'freely ye have "
     "received, FREELY GIVE' (Matt 10:8) is the ministry's founding charter; His one scene of physical "
     "anger -- a whip of cords, tables overturned -- was for 'my Father's house an house of "
     "merchandise' (John 2:15-16); and 'ye CANNOT serve God and mammon' (Matt 6:24) -- a gospel that "
     "promises mammon for serving God is His teaching inverted. He owned nothing (Matt 8:20), praised "
     "the widow's mites over the rich men's gifts, taught secret giving to the poor (Matt 6:3). A "
     "counterfeit priesthood no more refutes the gospel than counterfeit coin refutes gold -- the "
     "fraud only works because the genuine exists."),

    (["reincarnation", "past lives", "near-death", "nde", "come back as"],
     "Yeshua's map is resurrection, not recycling: 'all that are in the graves shall hear his voice, "
     "and shall come forth' (John 5:28-29) -- the same persons, raised. 'I am the resurrection, and "
     "the life' (John 11:25), demonstrated at a tomb: Lazarus came forth as Lazarus. And the covenant "
     "name keeps identity: 'God is not the God of the dead, but of the living' (Matt 22:32) -- "
     "Abraham remains Abraham in the Father's keeping. Reincarnation without memory-continuity is not "
     "survival but serial creation -- 'you' do not return; someone else begins. Past-life memories "
     "bloom where the doctrine is taught and under hypnosis; NDEs are the borderland of the DYING, "
     "colored by expectation and contradicting across cultures. The Christian proof is not a tunnel "
     "of light but an opened tomb with witnesses."),

    (["horus", "mithras", "pagan", "copied", "dying and rising", "myths", "copycat"],
     "Yeshua named His own sources: 'all things must be fulfilled, which were written in the law of "
     "Moses, and in the prophets, and in the psalms, CONCERNING ME' (Luke 24:44); 'had ye believed "
     "Moses, ye would have believed me: for he wrote of me' (John 5:46) -- documents publicly in hand "
     "centuries before His birth. Open the actual pagan texts and the parallels evaporate: Horus had "
     "no virgin birth, no twelve, no crucifixion; Mithras was born from a rock and the Roman cult "
     "post-dates Christianity; December 25 appears in no Gospel at all. And a crucified Messiah "
     "scandalized every audience -- His own disciples had to be argued into it from the prophets "
     "(Luke 24:25-26); borrowed myths flatter their hearers, this one offended all of them. Prophecy, "
     "not paganism -- and no myth has a date under Pontius Pilate."),

    (["wars", "religion causes", "crusade", "inquisition", "violence in the name", "imagine no religion"],
     "Yeshua disarmed His church at His own arrest: 'Put up again thy sword... for all they that take "
     "the sword shall perish with the sword' (Matt 26:52) -- and healed the wound. 'Blessed are the "
     "PEACEMAKERS: for they shall be called the children of God' (Matt 5:9); 'the kings of the "
     "Gentiles exercise lordship... but ye shall NOT be so' (Luke 22:25-26). Crusaders had to sheathe "
     "those verses to draw their swords -- convicted by their own Lord's commands. And the ledger: "
     "the standard survey of history's wars classes under seven percent as religious; while the "
     "regimes that abolished God -- Stalin, Mao, the Khmer Rouge -- out-killed all religious wars "
     "combined in one century. Violence is a human problem wearing the age's respected coat; the one "
     "force with no alibi is the actual teaching of the actual Christ."),

    (["free will", "predestin", "sovereign", "calvin", "determin", "chosen before", "elect"],
     "Yeshua set the two wills side by side: 'how often WOULD I have gathered thy children... and ye "
     "WOULD NOT' (Matt 23:37) -- His desire real, their refusal truly theirs; 'ye will not come to me, "
     "that ye might have life' (John 5:40) -- the blockage is will, not fate; and His invitation is to "
     "'whosoever will' (Mark 8:34). Sovereignty is not puppetry: the sovereign act was making creatures "
     "who really choose. He knows the end from the beginning, but knowing is not forcing. The Father is "
     "'not willing that any should perish' (2 Pet 3:9); a secret decree of damnation would set His will "
     "against His own stated will."),

    (["resurrection", "rose from the dead", "risen", "legend", "empty tomb", "easter"],
     "Yeshua predicted it publicly and in advance: 'Destroy this temple, and in three days I will raise "
     "it up' (John 2:19) -- His enemies quoted it and set a guard (Matt 27:63-66); 'I have power to lay "
     "it down, and I have power to take it again' (John 10:18); and risen, He pre-empted the vision "
     "theory: 'handle me, and see; for a spirit hath not flesh and bones' (Luke 24:39), and ate before "
     "them. Legends need generations; this was proclaimed in Jerusalem, walking distance from the tomb, "
     "first witnessed by women (whom no one invents as witnesses then), by men who died rather than "
     "deny what they saw. Men die for what they believe true, never for what they know they made up."),

    (["genocide", "canaanite", "old testament violence", "amalek", "war god", "kill the"],
     "Yeshua bared the Father's heart when disciples asked for fire on a village: 'the Son of man is "
     "not come to destroy men's lives, but to save them' (Luke 9:56); He commanded 'love your enemies' "
     "as the Father's own likeness (Matt 5:44-45); and He renounced the sword: 'my kingdom is not of "
     "this world: else would my servants fight' (John 18:36). The Canaanite judgment was moral, not "
     "ethnic -- delayed four hundred years until 'the iniquity of the Amorites' was full (Gen 15:16), "
     "against child-burning (Deut 12:31), applied equally to Israel when she did the same, with mercy "
     "for any who turned (Rahab). The Judge of all the earth may recall the life He alone gives; men "
     "may not -- and in the Son the sword is laid down for good."),

    (["slavery", "slaves", "condone", "servant obey"],
     "Yeshua gave the principle that makes slaveholding self-condemning: 'all things whatsoever ye "
     "would that men should do to you, do ye even so to them: for this IS the law and the prophets' "
     "(Matt 7:12). He inverted the pyramid -- 'whosoever will be chiefest shall be servant of all: for "
     "even the Son of man came to minister' (Mark 10:44-45) -- and announced 'deliverance to the "
     "captives... liberty to them that are bruised' (Luke 4:18). The law itself made man-stealing a "
     "capital crime (Ex 21:16) and forbade returning a runaway (Deut 23:15). Scripture met a world "
     "where servitude was universal and drove the wedge that killed it; the abolitionists wielded this "
     "Book -- the slavers had to cut Exodus out of theirs."),

    (["why pray", "prayer pointless", "god already knows", "does prayer work", "answer prayer"],
     "Yeshua stated the objection's premise Himself and drew the opposite conclusion: 'your Father "
     "knoweth what things ye have need of, before ye ask him. After this manner THEREFORE pray ye' "
     "(Matt 6:8-9). Prayer was never information delivery; the knowing Father still wants the asking "
     "child. 'Ask, and it shall be given you' (Matt 7:7) -- keep asking; 'men ought always to pray, and "
     "not to faint' (Luke 18:1). He appointed asking as He appointed sowing: the harvest is His design, "
     "yet none reaps who will not sow. Ask chiefly for the Holy Spirit (Luke 11:13), aloud, in private, "
     "persistently. Christ Himself rose before day to pray (Mark 1:35) -- if prayer were pointless, He "
     "wasted His nights."),

    (["never heard", "unreached", "tribesman", "what about those who", "unevangelized"],
     "Yeshua scaled judgment to light: he 'that knew not... shall be beaten with few stripes. For unto "
     "whomsoever much is given, of him shall be much required' (Luke 12:48) -- no one is damned for "
     "geography. 'Other sheep I have, which are not of this fold: them also I must bring' (John 10:16) "
     "-- the Shepherd's reach is not bounded by the missionaries' map (Cornelius is the pattern, Acts "
     "10). In His own judgment scene the welcomed are surprised -- 'when saw we thee?' (Matt 25:37-40). "
     "Creation preaches (Ps 19:1), conscience testifies, and the Judge of all the earth does right "
     "(Gen 18:25). And the question standing in the room is never the tribesman's -- it is the "
     "hearer's: YOU have heard."),

    (["women", "misogyn", "demean", "patriarch", "female"],
     "Watch Yeshua's own conduct: He ratified a woman's place as disciple at His feet -- 'Mary hath "
     "chosen that good part, which shall not be taken away from her' (Luke 10:42); He coined 'daughter "
     "of Abraham' for a woman the officials saw as an interruption (Luke 13:16); and He made a woman "
     "the first witness of the resurrection, personally commissioned -- 'go to my brethren, and say...' "
     "(John 20:17) -- in a world that discounted a woman's testimony (no legend-maker chooses female "
     "witnesses; truth records them). Male and female are together the image of God (Gen 1:27). Judge "
     "the Book by its Author's behavior; weigh Paul with discernment, never above the Son's own ways."),

    (["who made god", "who created god", "everything needs a cause", "first cause", "uncaused"],
     "Scripture's own name for the Father is Yeshua's answer: 'the Father hath LIFE IN HIMSELF' (John "
     "5:26) -- underived, self-existent being; 'God is a Spirit' (John 4:24) -- not an object inside "
     "the caused order of matter and time; the I AM, present tense across centuries (Matt 22:32; Ex "
     "3:14). The argument was never 'everything needs a cause' but 'everything that BEGINS needs a "
     "cause.' The universe began -- the objector's own cosmology says so -- and so needs a cause; God "
     "did not begin, and needs none. An infinite regress of borrowed lamps lights nothing: something "
     "must own its light. The only question is whether the self-existent ground is mindless -- and then "
     "produced minds, morals, and mathematics -- or the living Father."),

    (["corrupted", "changed over", "telephone game", "council picked", "nicaea books", "manuscript", "canon"],
     "Yeshua vouched for the text to the stroke: 'one jot or one tittle shall in no wise pass from the "
     "law' (Matt 5:18) -- and the Dead Sea Scrolls tested it, a thousand years older than our Hebrew "
     "copies, reading the same. 'Heaven and earth shall pass away, but my words shall not pass away' "
     "(Matt 24:35) -- falsifiable for twenty centuries, only compounded (P52 within living memory of "
     "John). He pre-authorized the record: the Spirit 'shall bring all things to your remembrance' "
     "(John 14:26). Get the history straight: Nicaea set no canon; the lists RECOGNIZED what the "
     "assemblies had long read. 5,800+ Greek manuscripts, parallel and checkable -- more copies mean "
     "more cross-checking, not more corruption; the variants are spelling and word order, and no "
     "doctrine hangs on any of them."),

    (["show himself", "hiddenness", "why doesnt god", "make himself obvious", "write it in the sky", "invisible"],
     "He did show Himself: 'he that hath seen me hath seen the Father' (John 14:9) -- Philip asked "
     "exactly this, and that was the answer. And Yeshua ruled on the 'more spectacle would convince me' "
     "theory: 'If they hear not Moses and the prophets, neither will they be persuaded, though one rose "
     "from the dead' (Luke 16:31) -- proven twice, for they plotted to kill Lazarus (John 12:10) and "
     "bribed the guards of His own tomb (Matt 28:12-15). Evidence compels only the willing. His "
     "protocol for seeing: 'If any man WILL DO his will, he shall know' (John 7:17); 'the pure in heart "
     "shall see God' (Matt 5:8). The standing experiment is prayer -- ask the Father for the Holy "
     "Spirit (Luke 11:13) -- and one who refuses the experiment cannot cite the absence of its result."),

    (["faith", "crutch", "believing without evidence", "blind faith", "weak", "delusion"],
     "Yeshua met doubt with evidence, not scolding: to Thomas, 'reach hither thy finger... and be not "
     "faithless, but believing' (John 20:27), then 'blessed are they that have not seen, and yet have "
     "believed' (John 20:29). Faith is 'the substance of things hoped for, the EVIDENCE of things not "
     "seen' (Heb 11:1) -- trusting a Person you have reason to trust, and then acting, as you trust a "
     "chair before you sit in it. And He calls the weak on purpose: 'Come unto me, all ye that labour "
     "and are heavy laden' (Matt 11:28). Admitting the wound is honesty, not weakness; the strong who "
     "deny theirs are not thereby whole."),
]


def _norm(s):
    return " " + re.sub(r"[^a-z0-9' ]+", " ", (s or "").lower().replace("’", "'")) + " "


# ---- the full 100-round gauntlet, generated from the vetted artifact ----
import json as _json
import os as _os

_KB = None
_IDF = None
_KB_PATH = _os.path.join(_os.path.dirname(__file__), "gauntlet_kb.json")
_WORD = re.compile(r"[a-z']+")

_QSTOP = set("the a an and or but if is are was were be been being to of in on at for with "
             "this these those it its as by from your you i he she they we our do does did "
             "just even really about what why how who when where which than then not no "
             "have has had will would should could can may might must actually anyone".split())


def _tok(s):
    return [w.strip("'") for w in _WORD.findall((s or "").lower().replace("’", "'"))
            if len(w.strip("'")) >= 3 and w.strip("'") not in _QSTOP]


def _kb():
    """Load the 100 vetted rounds once, and build the idf table over their full text."""
    global _KB, _IDF
    if _KB is None:
        try:
            _KB = _json.load(open(_KB_PATH, encoding="utf-8"))
        except Exception:
            _KB = []
        import math
        df = {}
        for e in _KB:
            for w in set(e.get("words", [])):
                df[w] = df.get(w, 0) + 1
        n = max(1, len(_KB))
        _IDF = {w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}
    return _KB


# Distinctive phrases that pin a query to its round, resolving near-neighbor collisions
# (resurrection vs after-death, the three wealth rounds, who-made-God vs free-will, etc.).
_BOOST = {
    5: ["equal with god", "co-equal", "coequal", "is jesus god", "deity of christ"],
    6: ["take our punishment", "penal", "wrath", "satisfy god", "punishment for us", "took the punishment"],
    12: ["resurrection", "risen", "rose from the dead", "rise from the dead", "empty tomb", "easter"],
    18: ["who made god", "who created god", "made god", "first cause", "uncaused", "needs a cause"],
    20: ["prove he exists", "prove god", "show himself", "make himself obvious", "why doesnt god just"],
    25: ["gay", "homosexual", "homosexuality", "same sex", "lgbt"],
    27: ["televangelist", "prosperity preacher", "church wants my money", "church wants your money", "seed money", "tithe"],
    33: ["why did jesus have to die", "why the cross", "just forgive", "why die", "cross at all", "necessary"],
    53: ["before he was born", "pre-exist", "preexist", "exist before", "pre-existence"],
    56: ["lose your salvation", "lose salvation", "once saved", "eternal security"],
    59: ["go to church", "have to go to church", "church attendance", "attend church"],
    65: ["right after you die", "after death", "after you die", "intermediate"],
    66: ["pets", "dog", "animals go to heaven", "see my dog", "do animals"],
    77: ["rich people", "get into heaven", "camel", "needle", "can the rich"],
    89: ["did jesus exist", "exist historically", "historical jesus", "mythicist", "jesus even exist", "real person"],
    96: ["rich and healthy", "prosperity gospel", "health and wealth", "everyone rich"],
    98: ["cremation", "cremated", "ashes"],
    99: ["what must i do", "to be saved", "how to be saved", "how do i get saved", "get saved"],
    100: ["why should i care", "why does it matter", "whats the point", "so what", "difference would jesus", "care about jesus"],
}


def _kb_best(query):
    """Best round by summed idf of query words found in the round; question-word
    matches count double, and distinctive boost-phrases pin collision-prone rounds.
    Returns (entry, score, margin-over-runner-up)."""
    kb = _kb()
    if not kb:
        return None, 0.0, 0.0
    qtok = set(_tok(query))
    qn = _norm(query)
    scored = []
    for e in kb:
        words = set(e.get("words", []))
        qwords = set(e.get("keys", []))
        s = 0.0
        for w in qtok:
            if w in words:
                s += _IDF.get(w, 1.0) * (2.0 if w in qwords else 1.0)
        for phrase in _BOOST.get(e.get("n"), ()):
            if (" " + phrase + " ") in qn or (" " + phrase) in qn:
                s += 6.0
        scored.append((s, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_s, best_e = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    return best_e, best_s, best_s - runner


def gauntlet_entry(query, threshold=2.0):
    """Return the full structured vetted round best matching this objection (or None)."""
    best, score, _ = _kb_best(query)
    return best if (best and score >= threshold) else None


import random as _random

_INTROS = [
    "Hear the words of Christ Himself on this:",
    "The Lord settled this in His own words:",
    "Begin where truth begins -- with what Yeshua said:",
    "Consider what the Christ directly declared:",
    "Yeshua did not leave this unanswered:",
    "Weigh His own words first:",
]
_REASON_LEADS = [
    "", "Reason it out: ", "Here is the heart of it: ",
    "So weigh it plainly: ", "And the sense of it: ",
]
_BRIDGES = [
    "And His own words bear it out:",
    "Christ said it Himself:",
    "Hear the Lord on it:",
    "His words are the measure:",
]


def _first_sentence(s):
    m = re.split(r"(?<=[.!?])\s", s, 1)
    return m[0] if m else s


def present(entry, seed=None):
    """Compose a VARIED, detailed presentation of a vetted round from its structured
    sayings + reasoning. Same round, fresh framing/order/depth each call -- the scripture
    quotes and references stay exact, so variety never costs correctness."""
    r = _random.Random(seed)
    sayings = list(entry.get("sayings", []))
    reason = entry.get("reason", "")
    if not sayings:
        return entry.get("argument", "")
    depth = r.choice(["full", "full", "short"])

    def render(s):
        line = "Yeshua said, %s (%s)." % (s["quote"], s["ref"])
        if depth == "full" and s.get("expo"):
            line += " " + s["expo"]
        else:
            line += " " + _first_sentence(s.get("expo", ""))
        return line

    framing = r.choice(["sayings_first", "reason_bookend", "strongest_first"])
    if framing == "reason_bookend" and reason:
        blocks = [r.choice(_REASON_LEADS) + reason, r.choice(_BRIDGES)]
        blocks += [render(s) for s in sayings]
    elif framing == "strongest_first":
        order = sayings[:]
        r.shuffle(order)
        blocks = [r.choice(_INTROS), render(order[0])]
        blocks += [render(s) for s in order[1:]]
        if reason:
            blocks.append(r.choice(_REASON_LEADS) + reason)
    else:  # sayings_first
        blocks = [r.choice(_INTROS)] + [render(s) for s in sayings]
        if reason:
            blocks.append(r.choice(_REASON_LEADS) + reason)
    return "\n\n".join(b for b in blocks if b)


def present_for(query, seed=None):
    """Retrieve the best vetted round for a query and present it freshly, or "" if none."""
    e = gauntlet_entry(query)
    return present(e, seed) if e else ""


def argument_for(query, min_hits=1):
    """Return the ideal recorded, Christ-first answer best matching the query, or "".
    Prefers the full 100-round gauntlet KB (idf-weighted); falls back to the compact
    hand-tuned entries only if the KB gives no confident match."""
    best, score, _ = _kb_best(query)
    if best and score >= 2.0:
        return best["argument"]
    q = _norm(query)                          # fallback: curated compact entries
    fb, fb_score = "", 0
    for keys, arg in ENTRIES:
        s = sum(1 for k in keys if k in q)
        if s > fb_score:
            fb_score, fb = s, arg
    return fb if fb_score >= min_hits else ""
