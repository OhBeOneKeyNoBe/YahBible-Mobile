#!/usr/bin/env python3
r"""The GNOSTIC MAP -- the chain of emanation from the Monad down to Adam and Eve and
the beginning of their lineage, as taught in the Nag Hammadi / gnostic scriptures. Each
entity carries a definition, a description of its appearance and its nature, and its
citations are resolved live from the reader's own corpus (book + verse). A dividing line
falls where Sophia brings forth the Demiurge, separating the Fullness from the Deficiency."""
import re
import sqlite3

from angelic_hierarchy import ANGELIC

CORPUS_DB = "file:D:/Holorites_data/daeos/taviel_corpus.sqlite?mode=ro"

# side: "fullness" (Pleroma, above the line) or "deficiency" (below). The line is drawn
# between the last fullness tier and the first deficiency tier (Sophia -> Yaldabaoth).
ENTITIES = [
    {"id": "monad", "name": "The Monad", "aka": "The Invisible Virgin Spirit \u00b7 The One",
     "tier": 0, "side": "fullness", "parent": None,
     "definition": "The ineffable Source of all -- the utterly transcendent One beyond being, name, and thought. Not a god among gods but the Root from which the whole Fullness flows; complete in itself and needing nothing. Within the Monad the Father, as He is named and made apparent, dwells -- the Monad's own self-manifestation, the face by which the unknowable One is known.",
     "appearance": "Formless and invisible: 'not corporeal, not incorporeal; not great, not small.' It is beheld only as boundless pure light and living water surrounding itself; no image can contain it.",
     "nature": "Perfect, immeasurable, eternal, self-sufficient. It creates not from lack or desire but overflows in pure grace, contemplating its own light. The apparent Father dwells within it, so that the hidden Source and the revealed Father are one.",
     "search": ["the invisible spirit", "invisible virgin spirit", "the monad", "the one who is"]},

    {"id": "barbelo", "name": "Barbelo", "aka": "First Thought \u00b7 the Mother-Father \u00b7 Pronoia",
     "tier": 1, "side": "fullness", "parent": "monad",
     "definition": "The first emanation of the Invisible Spirit -- its own reflection made real -- the primal Forethought (Pronoia) and Mother of all who come after; the first power and perfect glory in whom the All is conceived.",
     "appearance": "A luminous image of the Spirit, androgynous and perfect: the triple-male, triple-powered, invisible aeon shining as the Spirit's own mirror.",
     "nature": "The womb of the entirety, first to receive being -- Mother-Father at once: the Father's thought and the Mother of the Aeons.",
     "search": ["barbelo"]},

    {"id": "autogenes", "name": "The Autogenes", "aka": "the Self-Begotten \u00b7 the Son \u00b7 the Christ",
     "tier": 2, "side": "fullness", "parent": "barbelo",
     "definition": "Begotten of Barbelo by the Spirit's spark -- the Self-Generated One, the only-begotten Son, the anointed Christ -- through whom the aeons are established and ordered.",
     "appearance": "The divine child crowned by the Invisible Spirit, shining with the light of the four luminaries; the perfected, self-arising radiance.",
     "nature": "True and perfect Son, mind of the All, given power to establish the aeons and set the luminaries in place.",
     "search": ["autogenes", "self-begotten", "self-generated", "only-begotten", "the self-originate"]},

    {"id": "luminaries", "name": "The Four Luminaries", "aka": "Harmozel \u00b7 Oroiael \u00b7 Davithe \u00b7 Eleleth",
     "tier": 3, "side": "fullness", "parent": "autogenes",
     "definition": "Four great lights set around the Autogenes -- each a heavenly aeon housing grace, understanding, perception, and prudence, and each the dwelling of one rank of the holy race. To each luminary three attendant aeons are joined, so that twelve aeons in all wait upon the Son.",
     "appearance": "Four radiant thrones or standing lights encircling the Son, each with its own attendant powers.",
     "nature": "The dwelling-places of the perfect: Harmozel of Adamas, Oroiael of Seth, Davithe of Seth's seed, and Eleleth, where the souls who repented late are gathered.",
     "search": ["harmozel", "oroiael", "davithe", "eleleth", "four luminaries", "four lights"],
     "members": [
        # First light -- Harmozel
        {"name": "Harmozel", "roster": "Harmozel · the first light", "place": "dwelling of Pigeradamas",
         "aka": "the first luminary",
         "definition": "The first luminary, the dwelling of the perfect Man Pigeradamas. Its three attendant aeons are Grace, Truth, and Form.",
         "appearance": "The first of the four standing lights around the Autogenes.",
         "nature": "The house of the incorruptible Adamas.",
         "search": ["harmozel"]},
        {"name": "Grace", "roster": "Harmozel · the first light", "place": "Charis · 1st aeon",
         "aka": "Charis", "definition": "The first aeon of Harmozel -- Grace (Charis), the unearned favour that overflows from the Invisible Spirit.",
         "appearance": "An emanation of pure grace attending the first light.", "nature": "Grace itself, given freely.",
         "search": ["grace", "charis"]},
        {"name": "Truth", "roster": "Harmozel · the first light", "place": "Aletheia · 2nd aeon",
         "aka": "Aletheia", "definition": "The second aeon of Harmozel -- Truth (Aletheia), the unhidden reality of the Fullness.",
         "appearance": "An emanation of unveiled truth.", "nature": "Truth -- that which is not concealed.",
         "search": ["truth", "aletheia"]},
        {"name": "Form", "roster": "Harmozel · the first light", "place": "Morphe · 3rd aeon",
         "aka": "Morphe", "definition": "The third aeon of Harmozel -- Form (Morphe), the shape or figure in which the perfect Man is imaged.",
         "appearance": "An emanation of perfect form.", "nature": "Form -- the pattern of the incorruptible.",
         "search": ["form", "morphe"]},
        # Second light -- Oroiael
        {"name": "Oroiael", "roster": "Oroiael · the second light", "place": "dwelling of heavenly Seth",
         "aka": "the second luminary",
         "definition": "The second luminary, the dwelling of the heavenly Seth. Its three aeons are Conception, Perception, and Memory.",
         "appearance": "The second standing light.", "nature": "The house of Seth.",
         "search": ["oroiael"]},
        {"name": "Conception", "roster": "Oroiael · the second light", "place": "Epinoia · 1st aeon",
         "aka": "Epinoia · Insight", "definition": "The first aeon of Oroiael -- Conception (Epinoia), the luminous insight or afterthought sent to awaken; the same Epinoia later hidden in Adam.",
         "appearance": "An emanation of awakening insight.", "nature": "Insight -- the spark of remembering.",
         "search": ["epinoia", "insight", "conception"]},
        {"name": "Perception", "roster": "Oroiael · the second light", "place": "Aisthesis · 2nd aeon",
         "aka": "Aisthesis", "definition": "The second aeon of Oroiael -- Perception (Aisthesis), the faculty of spiritual sensing.",
         "appearance": "An emanation of perception.", "nature": "Perception -- the sense that apprehends the light.",
         "search": ["aisthesis", "perception"]},
        {"name": "Memory", "roster": "Oroiael · the second light", "place": "Mneme · 3rd aeon",
         "aka": "Mneme", "definition": "The third aeon of Oroiael -- Memory (Mneme), the remembrance that holds the soul to its origin.",
         "appearance": "An emanation of remembrance.", "nature": "Memory -- the keeping of the root above.",
         "search": ["mneme", "memory"]},
        # Third light -- Davithe
        {"name": "Davithe", "roster": "Davithe · the third light", "place": "dwelling of the seed of Seth",
         "aka": "Daveithai · the third luminary",
         "definition": "The third luminary, the dwelling of the seed of Seth -- the incorruptible generation. Its three aeons are Understanding, Love, and Idea.",
         "appearance": "The third standing light.", "nature": "The house of the seed of Seth.",
         "search": ["davithe", "daveithai", "daveithe"]},
        {"name": "Understanding", "roster": "Davithe · the third light", "place": "Synesis · 1st aeon",
         "aka": "Synesis", "definition": "The first aeon of Davithe -- Understanding (Synesis), the joining insight that comprehends.",
         "appearance": "An emanation of understanding.", "nature": "Understanding -- the comprehending mind.",
         "search": ["synesis", "understanding"]},
        {"name": "Love", "roster": "Davithe · the third light", "place": "Agape · 2nd aeon",
         "aka": "Agape", "definition": "The second aeon of Davithe -- Love (Agape), the self-giving love that binds the Fullness.",
         "appearance": "An emanation of love.", "nature": "Love -- the bond of the aeons.",
         "search": ["agape", "love"]},
        {"name": "Idea", "roster": "Davithe · the third light", "place": "Idea · 3rd aeon",
         "aka": "Idea", "definition": "The third aeon of Davithe -- Idea (the Greek 'Idea' itself), the perfect archetype or form-thought.",
         "appearance": "An emanation of the perfect idea.", "nature": "Idea -- the archetype in the mind of the All.",
         "search": ["idea"]},
        # Fourth light -- Eleleth
        {"name": "Eleleth", "roster": "Eleleth · the fourth light", "place": "gathering of the repentant",
         "aka": "the fourth luminary",
         "definition": "The fourth luminary, where the souls who came to know their perfection late -- who repented -- are gathered. Its three aeons are Perfection, Peace, and Wisdom. From the region of Eleleth the drama of the lower Sophia and the appearance of Yaldabaoth is set in motion in some accounts.",
         "appearance": "The fourth standing light, gathering the latecoming souls.", "nature": "The threshold between the settled Fullness and the fall.",
         "search": ["eleleth"]},
        {"name": "Perfection", "roster": "Eleleth · the fourth light", "place": "Teleiosis · 1st aeon",
         "aka": "Teleiosis", "definition": "The first aeon of Eleleth -- Perfection (Teleiosis), the completion toward which the aeons are drawn.",
         "appearance": "An emanation of perfection.", "nature": "Perfection -- the finished fullness.",
         "search": ["teleiosis", "perfection"]},
        {"name": "Peace", "roster": "Eleleth · the fourth light", "place": "Eirene · 2nd aeon",
         "aka": "Eirene", "definition": "The second aeon of Eleleth -- Peace (Eirene), the stillness of the Fullness at rest in itself.",
         "appearance": "An emanation of peace.", "nature": "Peace -- the rest of the aeons.",
         "search": ["eirene", "peace"]},
        {"name": "Wisdom (aeon)", "roster": "Eleleth · the fourth light", "place": "Sophia · 3rd aeon",
         "aka": "Sophia", "definition": "The third aeon of Eleleth -- Wisdom (Sophia). This aeon of the fourth light bears the same name as the youngest Aeon whose fall begins the lower drama.",
         "appearance": "An emanation of wisdom attending the fourth light.", "nature": "Wisdom -- as an aeon of Eleleth, distinct from yet named with the fallen Sophia.",
         "search": ["sophia", "wisdom"]},
     ]},

    {"id": "adamas", "name": "Pigeradamas", "aka": "the Perfect Man \u00b7 heavenly Adamas",
     "tier": 4, "side": "fullness", "parent": "luminaries",
     "definition": "The perfect, archetypal Man -- the heavenly Adam -- placed in the first luminary Harmozel; the incorruptible pattern after which the earthly Adam is later counterfeited.",
     "appearance": "The luminous primal Human, the true Image, standing in the light of Harmozel.",
     "nature": "The incorruptible Anthropos, the divine prototype of humanity.",
     "search": ["adamas", "pigeradamas", "geradamas", "the perfect man", "the perfect human"]},

    {"id": "heavenly_seth", "name": "Seth (heavenly)", "aka": "father of the immovable race",
     "tier": 5, "side": "fullness", "parent": "adamas",
     "definition": "The son of the perfect Adamas and father of the 'seed of Seth' -- the incorruptible generation -- established in the second luminary Oroiael.",
     "appearance": "The luminous heavenly Son, the second Image after Adamas.",
     "nature": "Father of the immovable race, the spiritual lineage the Demiurge cannot touch.",
     "search": ["seed of seth", "posterity of seth", "immovable race", "the great seth"]},

    {"id": "sophia", "name": "Sophia", "aka": "Wisdom \u00b7 the youngest Aeon",
     "tier": 6, "side": "fullness", "parent": "heavenly_seth", "last_fullness": True,
     "definition": "The last and youngest of the Aeons -- Wisdom herself -- who conceived a thought without the consent of the Spirit and without her male consort, and so brought forth alone, apart from the harmony of the Fullness.",
     "appearance": "A radiant aeon of the Pleroma whose solitary act casts a shadow -- the first stirring toward the lower world.",
     "nature": "Wisdom driven by longing to know the unknowable; her passion, and later her repentance, set the whole drama of fall and restoration in motion.",
     "search": ["sophia", "wisdom"]},

    {"id": "yaldabaoth", "name": "Yaldabaoth", "aka": "Ialdabaoth \u00b7 Saklas \u00b7 Samael \u00b7 the Demiurge",
     "tier": 7, "side": "deficiency", "parent": "sophia", "first_deficiency": True,
     "definition": "Sophia's misbegotten offspring, brought forth without a consort -- the Demiurge, chief Archon, the ignorant creator of the material cosmos who declares 'I am God, and there is no other,' not knowing the Fullness above him.",
     "appearance": "A monstrous form: a serpent with the face of a lion, his eyes flashing like lightning-fire; Sophia hides him in a luminous cloud, apart from the immortals.",
     "nature": "Arrogant, blind (Samael, 'the blind god'), jealous and foolish (Saklas). He fashions the lower world and its rulers as a dim shadow of what is above.",
     "search": ["yaldabaoth", "ialdabaoth", "yaltabaoth", "saklas", "sakla", "samael", "the demiurge", "chief ruler", "first ruler", "chief archon"]},

    {"id": "archons", "name": "The Archons", "aka": "the Authorities \u00b7 the Rulers \u00b7 the Seven & the Twelve",
     "tier": 8, "side": "deficiency", "parent": "yaldabaoth",
     "definition": "The powers Yaldabaoth brings forth to govern matter. He begets TWELVE authorities and sets SEVEN kings over the seven heavens (each with a beast's face) and five over the abyss, sharing his stolen fire with them but not the light. To each of the seven he joins one of seven powers -- goodness, foreknowledge, divinity, lordship, kingdom, zeal, and understanding -- so that his imitation heaven mirrors the Fullness above in a dim, ignorant copy. Together they administer fate (heimarmene) over the lower creation. (The Apocryphon of John gives TWO overlapping rosters: the twelve authorities begotten of Yaldabaoth, and the seven animal-faced kings who are the 'bodies belonging with the names' -- both are set out below.)",
     "appearance": "Beast-faced, animal-headed rulers, each set over a heaven or a passion; Yaldabaoth himself wears a multitude of faces and can set any face before them at will.",
     "nature": "Blind servants of the Demiurge, imitating the powers above and binding souls under fate. 'In the names given to them by their Originator there was power.'",
     "search": ["archon", "the authorities", "the rulers", "seven kings", "twelve authorities", "powers and authorities"],
     "members": [
        # ---- ROSTER 1: the seven animal-faced kings of the seven heavens (ApJohn 62, 65) ----
        {"name": "Athoth", "roster": "The Seven Kings of the Heavens", "place": "First heaven",
         "aka": "the reaper \u00b7 sheep's face \u00b7 the power Goodness",
         "definition": "The first king, set over the FIRST heaven, whom the generations call 'the reaper.' To him is joined the first power, Goodness.",
         "appearance": "A ruler bearing a SHEEP'S face -- the first of the seven animal-faced 'bodies belonging with the names.'",
         "nature": "First of the rulers of the week; an ignorant counterfeit of the good that flows from the Fullness.",
         "search": ["athoth", "the reaper"]},
        {"name": "Eloaiou", "roster": "The Seven Kings of the Heavens", "place": "Second heaven",
         "aka": "donkey's face \u00b7 the power Foreknowledge",
         "definition": "The second king, set over the SECOND heaven, to whom the power Foreknowledge is joined.",
         "appearance": "A ruler bearing a DONKEY'S face.",
         "nature": "A blind imitation of the Fullness's foreknowledge.",
         "search": ["eloaiou", "eloaio"]},
        {"name": "Astaphaios", "roster": "The Seven Kings of the Heavens", "place": "Third heaven",
         "aka": "hyena's face \u00b7 the power Divinity",
         "definition": "The third king, over the THIRD heaven, joined to the power Divinity (a later hand corrects the text to name 'divinity' here).",
         "appearance": "A ruler bearing a HYENA'S face.",
         "nature": "A counterfeit divinity among the rulers of fate.",
         "search": ["astaphaios", "astraphaio", "astraphaios"]},
        {"name": "Yao", "roster": "The Seven Kings of the Heavens", "place": "Fourth heaven",
         "aka": "seven-headed serpent's face \u00b7 the power Lordship",
         "definition": "The fourth king, over the FOURTH heaven, joined to the power Lordship. His face is the most monstrous of the seven.",
         "appearance": "A ruler bearing a SERPENT'S face WITH SEVEN HEADS.",
         "nature": "The counterfeit lord of the rulers -- a serpent mimicking dominion.",
         "search": ["yao", "iao"]},
        {"name": "Sabaoth (the king)", "roster": "The Seven Kings of the Heavens", "place": "Fifth heaven",
         "aka": "dragon's face \u00b7 the power Kingdom",
         "definition": "The fifth king, over the FIFTH heaven, joined to the power Kingdom -- named Adonaiou among the twelve. This is the ruler who later HEARS the voice of Pistis Sophia, condemns his father Yaldabaoth, and is raised and enthroned over the seventh heaven (see the separate node 'Sabaoth, the archon who repented').",
         "appearance": "A ruler bearing a DRAGON'S face; later exalted to a throne of light with a chariot of cherubim.",
         "nature": "The one ruler capable of turning toward the light -- kingdom that repents.",
         "search": ["sabaoth", "adonaiou"]},
        {"name": "Adonin", "roster": "The Seven Kings of the Heavens", "place": "Sixth heaven",
         "aka": "Adonein \u00b7 monkey's face \u00b7 the power Zeal",
         "definition": "The sixth king, over the SIXTH heaven, joined to the power of zeal (envy).",
         "appearance": "A ruler bearing a MONKEY'S (ape's) face.",
         "nature": "The counterfeit of zeal -- envy set over a heaven.",
         "search": ["adonin", "adonein"]},
        {"name": "Sabbede", "roster": "The Seven Kings of the Heavens", "place": "Seventh heaven",
         "aka": "Sabbateon \u00b7 shining fire-face \u00b7 the power Understanding",
         "definition": "The seventh king, over the SEVENTH heaven, joined to the power Understanding (Sabbateon) -- 'this is the sevenness of the week.'",
         "appearance": "A ruler bearing a face of SHINING FIRE.",
         "nature": "The counterfeit of understanding, closing the imitation week of seven heavens.",
         "search": ["sabbede", "sabbateon"]},
        # ---- ROSTER 2: the twelve authorities -- seven over the heavens, five over the abyss (ApJohn 56-58) ----
        {"name": "Athoth (authority)", "roster": "The Twelve Authorities", "place": "First heaven",
         "aka": "the reaper \u00b7 1st authority",
         "definition": "The first of the twelve authorities Yaldabaoth begets, set over the first heaven -- 'whom the generations call the reaper.' Same name as the first king.",
         "appearance": "A named ruler of the first firmament; the text gives the name and epithet, not a further form.",
         "nature": "The reaper -- the harvesting authority of fate over the first heaven.",
         "search": ["athoth", "the reaper"]},
        {"name": "Harmas", "roster": "The Twelve Authorities", "place": "Second heaven",
         "aka": "the eye of envy \u00b7 2nd authority",
         "definition": "The second authority, set over the second heaven -- 'who is the eye of envy.'",
         "appearance": "Named as the eye of envy; the text gives the name and epithet, not a further form.",
         "nature": "Envy itself made a ruler of the second firmament.",
         "search": ["harmas"]},
        {"name": "Kalila-Oumbri", "roster": "The Twelve Authorities", "place": "Third heaven",
         "aka": "3rd authority",
         "definition": "The third authority, set over the third heaven. The text names him without an epithet.",
         "appearance": "A named ruler of the third firmament; no further form is given in the text.",
         "nature": "An authority of fate over the third heaven, known to us only by name.",
         "search": ["kalila", "oumbri"]},
        {"name": "Yabel", "roster": "The Twelve Authorities", "place": "Fourth heaven",
         "aka": "4th authority",
         "definition": "The fourth authority, set over the fourth heaven. The text names him without an epithet.",
         "appearance": "A named ruler of the fourth firmament; no further form is given in the text.",
         "nature": "An authority of fate over the fourth heaven, known to us only by name.",
         "search": ["yabel"]},
        {"name": "Adonaiou", "roster": "The Twelve Authorities", "place": "Fifth heaven",
         "aka": "who is called Sabaoth \u00b7 5th authority",
         "definition": "The fifth authority, set over the fifth heaven -- 'who is called Sabaoth,' the same name as the fifth king who later repents.",
         "appearance": "A named ruler of the fifth firmament; the dragon-faced king in the other roster.",
         "nature": "Kingdom among the authorities -- the one whose name is shared with the repentant Sabaoth.",
         "search": ["adonaiou", "sabaoth"]},
        {"name": "Cain (the sun)", "roster": "The Twelve Authorities", "place": "Sixth heaven",
         "aka": "whom men call the sun \u00b7 6th authority",
         "definition": "The sixth authority, set over the sixth heaven -- 'whom the generations of men call the sun.' Distinct from the earthly Cain, son of Adam.",
         "appearance": "A named ruler of the sixth firmament, identified with the sun.",
         "nature": "The solar authority of fate; men mistake this ruler for the sun itself.",
         "search": ["cain", "the sun"]},
        {"name": "Abel (authority)", "roster": "The Twelve Authorities", "place": "Seventh heaven",
         "aka": "7th authority",
         "definition": "The seventh authority, set over the seventh heaven. Distinct from the earthly Abel, son of Adam.",
         "appearance": "A named ruler of the seventh firmament; no further form is given.",
         "nature": "The seventh authority of fate, closing the rulers of the heavens.",
         "search": ["abel"]},
        {"name": "Abrisene", "roster": "The Twelve Authorities", "place": "The abyss (the five)",
         "aka": "8th authority \u00b7 over the deep",
         "definition": "The eighth authority -- the first of the five set 'over the depth of the abyss' rather than over a heaven.",
         "appearance": "A named ruler of the deep; no further form is given in the text.",
         "nature": "An authority of the abyss, binding the lower places.",
         "search": ["abrisene"]},
        {"name": "Yobel", "roster": "The Twelve Authorities", "place": "The abyss (the five)",
         "aka": "9th authority \u00b7 over the deep",
         "definition": "The ninth authority, set over the depth of the abyss.",
         "appearance": "A named ruler of the deep; no further form is given in the text.",
         "nature": "An authority of the abyss.",
         "search": ["yobel"]},
        {"name": "Armoupieel", "roster": "The Twelve Authorities", "place": "The abyss (the five)",
         "aka": "10th authority \u00b7 over the deep",
         "definition": "The tenth authority, set over the depth of the abyss.",
         "appearance": "A named ruler of the deep; no further form is given in the text.",
         "nature": "An authority of the abyss.",
         "search": ["armoupieel"]},
        {"name": "Melceir-Adonein", "roster": "The Twelve Authorities", "place": "The abyss (the five)",
         "aka": "11th authority \u00b7 over the deep",
         "definition": "The eleventh authority, set over the depth of the abyss.",
         "appearance": "A named ruler of the deep; no further form is given in the text.",
         "nature": "An authority of the abyss.",
         "search": ["melceir", "adonein"]},
        {"name": "Belias", "roster": "The Twelve Authorities", "place": "The abyss (Hades)",
         "aka": "12th authority \u00b7 over the depth of Hades",
         "definition": "The twelfth and last authority -- 'it is he who is over the depth of Hades,' the deepest of the five set over the abyss.",
         "appearance": "The ruler of the depth of Hades; no further form is given in the text.",
         "nature": "The lowest authority of fate, keeper of the deepest place of the dead.",
         "search": ["belias", "belial"]},
     ]},

    {"id": "sabaoth", "name": "Sabaoth", "aka": "the archon who repented",
     "tier": 8, "side": "deficiency", "parent": "yaldabaoth",
     "definition": "A ruler, offspring of Yaldabaoth, who on hearing the voice of Pistis Sophia condemned his father and was raised up and enthroned over the seventh heaven -- the one ruler who turns toward the light.",
     "appearance": "An archon exalted to a throne of light, with a chariot of cherubim.",
     "nature": "The exception among the rulers: repentant, and set above the rest.",
     "search": ["sabaoth"]},

    {"id": "adam", "name": "Adam", "aka": "the molded man",
     "tier": 9, "side": "deficiency", "parent": "archons",
     "definition": "The first human, molded by Yaldabaoth and the archons after the image of the heavenly Man they had glimpsed reflected above -- lifeless until the divine spark (the power drawn from Sophia) is breathed into him, making him greater than his makers.",
     "appearance": "A body of soul and dust fashioned by the rulers, at first inert upon the ground, then luminous when the Spirit enters.",
     "nature": "A mingling: earthly form animated by a spark of the Fullness. The rulers' envy of that spark drives the whole drama of Eden.",
     "search": ["adam"]},

    {"id": "eve", "name": "Eve", "aka": "Zoe \u00b7 Life \u00b7 mother of the living",
     "tier": 10, "side": "deficiency", "parent": "adam",
     "definition": "The counterpart drawn from Adam, called Zoe, 'Life' -- in the gnostic reading the bearer of the spiritual awakening, joined to the luminous Epinoia (insight) sent to help Adam remember his origin.",
     "appearance": "The woman brought forth beside Adam; behind her stands the shining Epinoia of light.",
     "nature": "Life and instructor -- through her, and the counsel to eat of the tree of knowledge, the first humans begin to awaken to gnosis.",
     "search": ["eve", "zoe", "mother of the living", "epinoia"]},

    {"id": "lineage", "name": "Cain, Abel, Seth & Norea", "aka": "the beginning of the lineage",
     "tier": 11, "side": "deficiency", "parent": "eve",
     "definition": "The first children: Cain and Abel, begotten in the rulers' way; then Seth, in whom the incorruptible seed continues on earth; and Norea, the pure daughter and guardian of the spiritual race against the archons. Here the earthly lineage begins.",
     "appearance": "The first human offspring -- two born of the rulers' violence, and the two through whom the light-seed descends.",
     "nature": "The branching of humanity into the seed of the rulers and the seed of Seth -- the immovable race, carried down through Norea.",
     "search": ["cain", "abel", "norea", "eve bore"],
     "members": [
        {"name": "Cain (earthly)", "aka": "Eloim/Yave in some tractates · begotten of the rulers",
         "definition": "In the gnostic reading, the first son is begotten when Yaldabaoth (or the rulers) defiles Eve; he is the child of the rulers' violence, associated in On the Origin of the World with the unrighteous line. Distinct from the archon 'Cain, whom men call the sun.'",
         "appearance": "The firstborn of the molded pair, bearing the rulers' likeness.",
         "nature": "The seed of the archons in humanity -- the line set against the spiritual race.",
         "search": ["cain"]},
        {"name": "Abel", "aka": "the second son · the righteous slain",
         "definition": "The second son; in the archon roster a name is also given to the seventh authority (Abel), but here he is the earthly brother slain by Cain -- the first of the wronged dead who cry out for justice.",
         "appearance": "The second child of Adam and Eve.",
         "nature": "The slain righteous -- his blood the first cry of the oppressed against the rulers.",
         "search": ["abel"]},
        {"name": "Seth (earthly)", "aka": "the incorruptible seed on earth",
         "definition": "The third son, given by God 'in place of Abel,' in whom the immovable race -- the seed of the heavenly Seth -- continues within the material world. The gnostic Sethians trace their spiritual descent through him.",
         "appearance": "The luminous third child, image of the heavenly Seth below.",
         "nature": "The earthly vessel of the light-seed, carrier of gnosis through the generations.",
         "search": ["seth", "seed of seth"]},
        {"name": "Norea", "aka": "Orea · Horaia · the pure virgin · guardian of the race",
         "definition": "The daughter (or sister-wife of Seth/Shem), the pure one who resists the archons when they seek to defile her and to destroy the spiritual race in the flood. In the Hypostasis of the Archons she cries out and is rescued by the angel Eleleth, who reveals to her the truth of the rulers and her own root above.",
         "appearance": "The undefiled virgin, shining, whom the rulers cannot seize.",
         "nature": "Guardian and helper of the incorruptible race -- the feminine spiritual power carried down the lineage against the powers of fate.",
         "search": ["norea", "orea", "horaia"]},
     ]},
]

# the angelic hierarchy stands as a second column (col="angelic") beside the emanation,
# above the Sophia->Demiurge divide (its tiers 0-6 never reach the first_deficiency tier 7).
ENTITIES = ENTITIES + ANGELIC

CORPUS_TITLES = {"nag_hammadi": "Nag Hammadi", "gnostic_bible": "Gnostic Bible",
                 "ethiopian_apocrypha": "Ethiopian Apocrypha"}
WATCHMAN = "file:D:/watchman/watchman.db?mode=ro"
ENOCH = "file:D:/Holorites/torus_upgrades/enoch_source.sqlite?mode=ro"
# only these identity terms are searched in the Bible/Enoch (common words would mislink)
_BIBLICAL = {"adam", "eve", "cain", "abel", "norea", "sabaoth", "seth", "seed of seth"}


def _citations(terms, limit=6):
    out, seen = [], set()

    def add(kind, disp, **kw):
        key = (kind, kw.get("book"), disp[:18])
        if key in seen or len(out) >= limit:
            return
        seen.add(key)
        out.append(dict(kind=kind, cite=disp, **kw))

    # 1) the gnostic corpora (Nag Hammadi, Gnostic Bible, Ethiopian) -- primary
    try:
        con = sqlite3.connect(CORPUS_DB, uri=True)
        for term in terms:
            for corpus, book, verse in con.execute(
                    "SELECT corpus,book,verse FROM corpus_units WHERE corpus IN"
                    " ('nag_hammadi','gnostic_bible','ethiopian_apocrypha') AND"
                    " lower(text) LIKE lower(?) ORDER BY corpus,book,verse LIMIT 40",
                    ("%" + term + "%",)):
                add("apoc", "%s \u00b7 %s %s" % (CORPUS_TITLES.get(corpus, corpus), book, verse),
                    aid="corpus:" + corpus, book=book, verse=verse)
        con.close()
    except Exception:
        pass
    # 2) the Bible (KJV) -- only for genuine biblical identities
    bib_terms = [t for t in terms if t.lower() in _BIBLICAL]
    if bib_terms:
        try:
            c = sqlite3.connect(WATCHMAN, uri=True)
            for term in bib_terms:
                for book, ch, verse in c.execute(
                        "SELECT book,chapter,verse FROM verses WHERE lower(text) LIKE lower(?)"
                        " ORDER BY id LIMIT 12", ("%" + term + "%",)):
                    add("bible", "KJV \u00b7 %s %s:%s" % (book, ch, verse),
                        book=book, chapter=ch, verse=verse)
            c.close()
        except Exception:
            pass
    # 3) Enoch -- only for biblical identities that appear there (Seth, Cain, Norea...)
    if bib_terms:
        try:
            c = sqlite3.connect(ENOCH, uri=True)
            for term in bib_terms:
                for book, ch, verse in c.execute(
                        "SELECT book,chapter,verse FROM verses WHERE lower(text) LIKE lower(?)"
                        " ORDER BY CAST(chapter AS INTEGER) LIMIT 6", ("%" + term + "%",)):
                    aid = {"1 Enoch": "enoch1", "2 Enoch": "enoch2", "3 Enoch": "enoch3"}.get(
                        (book or "").split()[0] + " Enoch" if "Enoch" in (book or "") else book, "enoch1")
                    add("apoc", "%s %s:%s" % (book, ch, verse), aid=aid, book=book, verse=verse)
            c.close()
        except Exception:
            pass
    return out[:limit]


_CACHE = None


def build_map():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    nodes = []
    for e in ENTITIES:
        members = []
        for m in e.get("members", []):
            members.append({"name": m["name"], "aka": m.get("aka", ""),
                            "roster": m.get("roster", ""), "place": m.get("place", ""),
                            "definition": m["definition"], "appearance": m["appearance"],
                            "nature": m["nature"], "citations": _citations(m["search"])})
        nodes.append({"id": e["id"], "name": e["name"], "aka": e["aka"],
                      "tier": e["tier"], "side": e["side"], "parent": e["parent"],
                      "col": e.get("col", "emanation"),
                      "definition": e["definition"], "appearance": e["appearance"],
                      "nature": e["nature"], "citations": _citations(e["search"]),
                      "members": members,
                      "last_fullness": e.get("last_fullness", False),
                      "first_deficiency": e.get("first_deficiency", False)})
    _CACHE = {"title": "Gnostic Lineage",
              "subtitle": "From the Monad to Adam & Eve \u2014 the emanation of the Fullness and the fall into the world",
              "nodes": nodes}
    return _CACHE


if __name__ == "__main__":
    import sys
    import json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    m = build_map()
    for n in m["nodes"]:
        print("%-22s [%s] cites=%d" % (n["name"], n["side"], len(n["citations"])))
