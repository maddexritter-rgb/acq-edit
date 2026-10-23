#!/usr/bin/env python3
"""
oliver_format.py — Oliver Albert's Acquisition.com caption-text formatter.

Pure-Python (stdlib only), deterministic text normalizer that implements Part 1
(text formatting) of the v2 spec (Oliver Albert, received 2026-07-06) at:
    caption-clips/references/oliver_caption_formatting_spec.md

Public API:
    format_caption_text(text: str) -> str

CLI:
    python3 oliver_format.py        # reads stdin, writes formatted stdout

Processing order (per spec "Processing Order", v2):
    0. Fragment cleanup (dangling trailing dashes; 1-2 letter half-word fragments dropped)
    1. Common words dictionary (FIRST + authoritative — locks tokens)
    2. Number words -> digits (incl. compound numbers; "a/an" consumed before a scale word)
    3. "one" vs "1" + ordinals ("third" -> 3rd; first/second only before an ordinal noun)
    4. Listicle & sequence labels  ("number N" -> "#N"; "step one"/"step 1" -> "step #1" / "day 1")
    5. Money formatting  (comma band $1,000-$1,999 ONLY; $2K+; lowercase billion/trillion;
       "$"-literal renormalization; grand noun-guard; bucks; bare NK/NM; implied money >= $1M)
    6. Symbol & multiplier rule  (dollars/percent -> $/% ; times/x -> X; plus -> +;
       double/triple/quadruple -> 2X/3X/4X; percentage ranges)
    7. Large non-money numbers  (money scale structure WITHOUT "$": 300K never 300,000;
       comma form only 1,000-1,999; 4-digit years untouched)
    8. Capitalization  (incl. places/languages lists + ALL-CAPS token preservation)
    9. Punctuation cleanup

NOTE — "one" vs "1" deliberately diverges from the spec's convert-by-default rule:
the LOCKED 2026-06-12 lesson (shipped "no 1 will care" / "judgment is 1") keeps "one"
as the WORD unless a positive signal (money / adjacent number / listicle label) fires.
The spec's trigger-word list would re-ship those bugs ("judgment is one" has no trigger).

Idempotency: tokens already in correct output form ($1K, ROI, 1-on-1, AI, 10X, 1,000)
are not re-processed.

Implementation strategy
------------------------
The text is tokenized into a list of Token objects. Each token carries its surface
text plus a `locked` flag. Once the dictionary (or a later rule that produces a final
form, e.g. money) locks a token, subsequent rules skip it. This makes the dictionary
authoritative and gives us idempotency for free (already-correct inputs match the
dictionary / lock patterns and are left alone).
"""

import re
import sys
from decimal import Decimal


# ---------------------------------------------------------------------------
# Token model
# ---------------------------------------------------------------------------

class Token:
    """A single token: word text + leading/trailing punctuation captured separately."""

    __slots__ = ("text", "lead", "trail", "locked", "space_before", "spoken", "src")

    def __init__(self, text, lead="", trail="", space_before=True, spoken=False, src=None):
        self.text = text          # the "word" core (may itself contain $ , . etc once formatted)
        self.lead = lead          # leading punctuation attached in source
        self.trail = trail        # trailing punctuation attached in source
        self.locked = False       # if True, no further rule touches .text
        self.space_before = space_before
        # True if this digit token was produced by number-WORD expansion (e.g.
        # "two thousand"->2000). Rule 8 thousands separators + the year guard apply
        # to SPOKEN values only; a pre-existing digit literal ("5000", "2024") is left
        # untouched (provenance per Rule 8: "Spoken-number values ONLY").
        self.spoken = spoken
        # Source-word index provenance (additive metadata — NEVER affects text output).
        # Set by format_words to the list of input-word indices this token was built from;
        # merged forward whenever a rule creates a new token from existing tokens, so the
        # final token can recover the start/end timestamps of its constituent words.
        self.src = list(src) if src else []

    def __repr__(self):
        return f"Token({self.lead!r}+{self.text!r}+{self.trail!r}, locked={self.locked}, spoken={self.spoken})"


# A token's core may legitimately contain these chars after processing.
_WORD_RE = re.compile(r"\S+")


def _merge_src(*toks):
    """Concatenate the .src lists of every source token consumed to build a new one.
    Additive provenance only — has zero effect on text output."""
    out = []
    [out.extend(getattr(t, "src", []) or []) for t in toks]
    return out


def _peel_token(raw):
    """Peel one raw chunk into (core, lead, trail) using the same logic tokenize uses.

    Abbreviations / initialisms / domains keep their internal+trailing periods; other
    trailing sentence punctuation (, . ? !) and leading quotes/parens are peeled off so
    rule logic sees a clean core. Shared by tokenize() (text mode) and format_words()
    (per-word mode) so both peel identically.
    """
    lead = ""
    trail = ""
    core = raw

    # Abbreviations / initialisms / domains keep their internal+trailing periods.
    # Detect them up front so we don't peel a meaningful trailing period.
    low = core.lower().rstrip(",?!")
    is_protected = (
        low in ("etc.", "e.g.", "i.e.", "u.s.")
        or re.fullmatch(r"(?:[a-z]\.){2,}", low)          # initialism like u.s. / a.b.c.
        or re.search(r"[a-z0-9]\.[a-z]{2,}$", low)         # domain like acquisition.com
    )

    if is_protected:
        # Peel trailing ? ! and COMMAS that come AFTER the abbreviation/domain's
        # final period — these are sentence punctuation (dropped in Rule 2) and must
        # NOT break the dictionary key match. The meaningful closing period of
        # "etc." / "e.g." / "U.S." stays in the core; "e.g.," -> core "e.g." + ",".
        mt = re.search(r"[,\?\!]+$", core)
        if mt:
            trail = mt.group(0)
            core = core[: mt.start()]
    else:
        # Peel trailing sentence punctuation we manage: , . ? ! (and combos).
        mt = re.search(r"[\,\.\?\!]+$", core)
        if mt:
            trail = mt.group(0)
            core = core[: mt.start()]
    ml = re.match(r"^[\"'\(\[]+", core)
    if ml:
        lead = ml.group(0)
        core = core[ml.end():]
    return core, lead, trail


def tokenize(text):
    """Split into tokens, peeling leading/trailing punctuation we may need to manage.

    We keep apostrophes, internal characters intact. Leading/trailing punctuation
    that we may need to strip in Rule 9 (commas, periods that aren't part of a
    number/abbrev/domain) are peeled into lead/trail so rule logic sees clean cores.
    """
    tokens = []
    for i, m in enumerate(text.split(" ")):
        # We split on single spaces to preserve word boundaries simply; the spec
        # examples are space-separated. Empty strings (from double spaces) become
        # empty cores we drop later.
        raw = m
        if raw == "":
            continue
        core, lead, trail = _peel_token(raw)
        tokens.append(Token(core, lead=lead, trail=trail, space_before=(i != 0)))
    return tokens


# ---------------------------------------------------------------------------
# Rule 9 (dictionary) data
# ---------------------------------------------------------------------------

# Multi-word dictionary phrases -> locked output. Matched on lowercased core sequence.
# Exact-sequence rule (spec Rule 9): multi-word names whose parts are common words
# capitalize ONLY when the full sequence appears ("gym launch" -> "Gym Launch" but a
# bare "launch" stays lowercase).
DICT_PHRASES = [
    (["one", "on", "one"], ["1-on-1"]),
    (["one", "shot"], ["one", "shot"]),  # locks "one" as a word; outputs unchanged
    (["alex", "hormozi"], ["Alex", "Hormozi"]),
    (["leila", "hormozi"], ["Leila", "Hormozi"]),
    (["sharran", "srivatsaa"], ["Sharran", "Srivatsaa"]),
    (["gym", "launch"], ["Gym", "Launch"]),
    (["steve", "jobs"], ["Steve", "Jobs"]),       # v2: "he created jobs" stays lowercase
    # v2: casual contractions ONLY before the verb "be" — "going to the gym" untouched.
    (["going", "to", "be"], ["gonna", "be"]),
    (["want", "to", "be"], ["wanna", "be"]),
    # v2 places — multi-word exact sequences (curated, freely extensible).
    (["las", "vegas"], ["Las", "Vegas"]),
    (["new", "york"], ["New", "York"]),
    (["san", "francisco"], ["San", "Francisco"]),
    (["los", "angeles"], ["Los", "Angeles"]),
    (["san", "diego"], ["San", "Diego"]),
    (["san", "antonio"], ["San", "Antonio"]),
    (["new", "orleans"], ["New", "Orleans"]),
    (["kansas", "city"], ["Kansas", "City"]),
    (["salt", "lake", "city"], ["Salt", "Lake", "City"]),
    (["north", "carolina"], ["North", "Carolina"]),
    (["south", "carolina"], ["South", "Carolina"]),
    (["north", "dakota"], ["North", "Dakota"]),
    (["south", "dakota"], ["South", "Dakota"]),
    (["new", "jersey"], ["New", "Jersey"]),
    (["new", "mexico"], ["New", "Mexico"]),
    (["new", "hampshire"], ["New", "Hampshire"]),
    (["west", "virginia"], ["West", "Virginia"]),
    (["rhode", "island"], ["Rhode", "Island"]),
    (["united", "states"], ["United", "States"]),
    (["united", "kingdom"], ["United", "Kingdom"]),
    (["new", "zealand"], ["New", "Zealand"]),
    (["puerto", "rico"], ["Puerto", "Rico"]),
    (["costa", "rica"], ["Costa", "Rica"]),
    (["saudi", "arabia"], ["Saudi", "Arabia"]),
    (["hong", "kong"], ["Hong", "Kong"]),
    (["south", "africa"], ["South", "Africa"]),
]

# Single-token dictionary entries: lowercased core -> locked output text.
DICT_SINGLE = {
    "acquisition.com": "Acquisition.com",
    "ai": "AI",
    "roi": "ROI",
    "cac": "CAC",
    "ltv": "LTV",
    "ebitda": "EBITDA",
    "kpi": "KPI",
    "kpis": "KPIs",
    "cta": "CTA",
    "ctas": "CTAs",
    "b2b": "B2B",
    "b2c": "B2C",
    "ceo": "CEO",
    "cfo": "CFO",
    "sop": "SOP",        # spec Rule 1 acronym list (was missing -> 'sop' left lowercase)
    "sops": "SOPs",
    "u.s.": "U.S.",      # spec Rule 1 initialism; lowercase input must capitalize
    # camelCase brands — simple capitalization can't produce the right form
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "alan": "ALAN",      # Alex's software company — Maddex wants ALL CAPS (Frame.io L3 notes 2026-06-17)
    "allen": "ALAN",     # Whisper hears the company name as "Allen"
    # v2 spec additions (2026-07-06):
    "versus": "vs",      # house spelling
    "qr": "QR",
    "skool": "Skool",    # the community platform (the "school" homophone is handled contextually)
    "mm": "mmh",         # standalone backchannel token only
}

# Acronyms / proper output forms already-correct, used by capitalization + idempotency.
ACRONYMS = {
    "AI", "ROI", "CEO", "CFO", "SOP", "CAC", "LTV", "EBITDA", "KPI", "KPIs",
    "CTA", "CTAs", "B2B", "B2C", "CRM", "MRR", "ARR",   # CRM/MRR added 2026-06-16 (Maddex L3 notes)
    "AOV",                                              # Average Order Value — added 2026-06-16 (Maddex L3 notes)
    "QR",                                               # v2 spec 2026-07-06
}

# Proper-noun words (capitalized forms) — for capitalization rule.
PROPER_WORDS = {
    # NB "Gym"/"Launch" are NOT here — v2 exact-sequence rule: they capitalize ONLY as
    # the full phrase "Gym Launch" (DICT_PHRASES); bare "gym"/"launch" stay lowercase.
    "Alex", "Hormozi", "Leila", "Sharran", "Srivatsaa",
    "Acquisition.com", "U.S.", "Gandhi",
    # From Alex corpus (29K clip analysis, 2026-06-11):
    "Elon", "Musk",                          # Elon Musk (21 clips)
    "Warren", "Buffett",                     # Warren Buffett (20 clips)
    "Vegas",                                 # Las Vegas (30 clips)
    "Amazon", "Netflix", "Google",           # brand names (27/18 clips)
    "Tik", "Tok",                            # "Tik Tok" house style (Maddex Frame.io note 2026-06-17) — keeps both words capitalized
    "Mozi",                                  # Alex's brand/nickname
    "MoreMozi",                              # the Hormozi highlights channel (ASR writes it "More Mosey")
    "Maddex",                                # team editor's name (ASR writes it Maddox/Maddux)
    # NOTE: "Alan" (the company) is now ALL CAPS "ALAN" via DICT_SINGLE — Maddex Frame.io note 2026-06-17
    # StudioL Frame.io review caps misses (2026-06-16) — spice lowercases; these must stay capitalized:
    "Mr", "MrBeast", "Beast",                # "Mr. Beast" (creator) — was rendering "mr beast"
    "Roy", "Sutherland",                     # Roy Sutherland (marketer Alex cites)
    "IRL", "UK",                             # acronyms — were rendering "irl"/"uk"
    "I",                                     # the pronoun must always be capital (was rendering lowercase "i")
    # days of week (always proper nouns) — L3 StageQA 2026-06-19 burned "mondays/wednesdays" lowercase
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays",
}


# STT misspellings -> canonical LOWERCASE (processed before apply_dictionary so the
# corrected token still flows through phrase-dict matching, e.g.
# "layla hormozi" -> "leila hormozi" -> DICT_PHRASES ["leila","hormozi"] -> "Leila Hormozi").
# Values are lowercase so the capitalization rule handles casing consistently.
# Confirmed from Alex corpus (29K clips, 2026-06-11).
MISSPELLINGS = {
    # Values are the CANONICAL (correctly-cased) form. apply_misspellings produces the
    # canonical form; the phrase dict still matches because apply_dictionary does lc() on
    # token.text — so "Leila" -> lc -> "leila" still hits ["leila","hormozi"].
    "layla": "Leila",   # Whisper writes Leila Hormozi as "Layla" in 33 of 38 clips (17% error rate)
    "maddox": "Maddex",  # Whisper writes the team editor's name Maddex as "Maddox" (Leila/Jay Shetty pod, 2026-06-12)
    "maddux": "Maddex",  # alternate Whisper spelling of the same name
}

# v2 spec Rule 1: curated PLACES + LANGUAGES/NATIONALITIES capitalization lists.
# Deliberate exclusions — words that are ALSO common English stay lowercase to avoid
# miscapitalizing: "polish" (verb), "turkey" (food), "nice", "mobile", "china" (dishes
# is capital-C anyway), "cook". Multi-word places live in DICT_PHRASES (exact sequence).
PLACES_LANGS = {
    # US states (single-word; multi-word ones are DICT_PHRASES)
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "ohio", "oklahoma", "oregon",
    "pennsylvania", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "wisconsin", "wyoming",
    # cities
    "vegas", "miami", "chicago", "boston", "austin", "dallas", "houston",
    "phoenix", "seattle", "denver", "atlanta", "nashville", "orlando",
    "philadelphia", "detroit", "portland", "london", "paris", "tokyo", "dubai",
    "toronto", "vancouver", "sydney", "singapore",
    # countries / continents
    "america", "mexico", "canada", "england", "france", "germany", "spain",
    "italy", "japan", "india", "brazil", "australia", "russia", "ukraine",
    "israel", "ireland", "scotland", "portugal", "greece", "egypt", "thailand",
    "vietnam", "korea", "argentina", "colombia", "europe", "africa", "asia",
    "antarctica",
    # languages / nationalities
    "spanish", "english", "french", "german", "italian", "chinese", "japanese",
    "danish", "dutch", "portuguese", "korean", "vietnamese", "arabic", "russian",
    "hindi", "american", "mexican", "canadian", "british", "australian",
    "indian", "brazilian", "european",
}

# SHARED VOCAB (2026-08-03): one correction file feeds BOTH normalizers so review-note
# fixes can never land in only one path again (the 'legion'/08-01 drift bug — the fixes
# lived only in spice_normalize.py and this path kept re-shipping them). New vocab fixes
# go in vocab/shared_vocab.json — not in the tables above.
def _load_shared_vocab():
    import json as _json
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parent.parent / "vocab" / "shared_vocab.json"
    if not p.exists():
        return
    try:
        sv = _json.loads(p.read_text())
    except Exception as _e:
        import sys as _sys
        print(f"oliver_format: WARN could not read shared_vocab.json: {_e}", file=_sys.stderr)
        return
    # 🛑 GATE (2026-08-27): a common noun here capitalises EVERY generic use. This exact
    # regression ("Gym"/"Launch") shipped 4 review notes before it was caught. Fail loud.
    _never = {w.lower() for w in sv.get("never_proper", [])}
    _bad = sorted({w for w in sv.get("proper_words", []) if w.lower() in _never})
    if _bad:
        raise SystemExit(
            f"oliver_format: shared_vocab.json proper_words contains common noun(s) {_bad} — "
            "these capitalise every generic use. Put the multi-word brand in phrase_fixes instead.")
    for w in sv.get("proper_words", []):
        PROPER_WORDS.add(w)
    for k, v in sv.get("misspellings", {}).items():
        MISSPELLINGS[k.lower()] = v
    for k, v in sv.get("phrase_fixes", {}).items():
        DICT_PHRASES.append((k.lower().split(), v.split()))
_load_shared_vocab()

# Case-insensitive lookup table built from PROPER_WORDS + the places/languages lists.
# Used by apply_capitalization so "elon" -> "Elon", "vegas" -> "Vegas", "utah" -> "Utah".
# (The dict check `core in PROPER_WORDS` is case-sensitive and misses lowercase inputs.)
_PROPER_LOWER = {w.lower(): w for w in PROPER_WORDS}
_PROPER_LOWER.update({w: w.capitalize() for w in PLACES_LANGS})

# Lowercase-locked abbreviations.
LOWER_ABBREV = {"etc.", "e.g.", "i.e.", "etc", "e.g", "i.e"}


# ---------------------------------------------------------------------------
# Number-word vocabulary
# ---------------------------------------------------------------------------

ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
SCALES = {
    "hundred": 100,
    "thousand": 1000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}

MONEY_WORDS = {"dollar", "dollars", "grand"}

# Spoken-money SHORTHAND scale units: a numeric quantity spoken immediately before one
# of these slang/abbreviated units is money written compactly with a symbol + suffix
# (e.g. "50 k" -> "$50K", "3 mil" -> "$3M", "1.5 grand" -> "$1.5K"). These are distinct
# from the full number-words "thousand"/"million", which keep their plain digit-expansion
# semantics (e.g. "two million" -> "2,000,000") unless an explicit "dollars" / money
# trigger is present. Mapping unit-word -> compact suffix.
MONEY_UNIT_SUFFIX = {
    "k": "K",
    "grand": "K",
    "mil": "M",
    "m": "M",
}

# Rate units (Rule 5 implied-money rate phrase).
RATE_UNITS = {"hour", "day", "week", "month", "quarter", "year"}

# Counting nouns that block money (Rule 5 guard #2). Stored singular; plurals handled.
COUNTING_NOUNS = {
    "year", "years", "month", "months", "week", "weeks", "day", "days",
    "hour", "hours", "minute", "minutes", "point", "points", "people",
    "person", "customer", "customers", "client", "clients", "editor",
    "editors", "employee", "employees", "rep", "reps", "user", "users",
    "member", "members",
}

# Reliable money trigger words (Rule 5 #4). Stored as a set of lemma-ish strings;
# we match by prefix for charge/charging/charged.
MONEY_TRIGGERS = {
    "money", "cash", "cashflow", "revenue", "profit", "ebitda", "pricing",
    "price", "cost", "costs", "salary", "fee", "fees", "charge", "charges",
    "charging", "charged", "budget", "expense", "expenses", "income",
    "earnings", "wage", "wages", "raise", "rate", "rates",
}

# Context-neutral words that do NOT trigger money alone.
NEUTRAL_WORDS = {"deal", "deals", "sale", "sales", "payment", "payments",
                 "invoice", "invoices", "quote", "quotes", "bonus", "bonuses"}

# Sequence list-item words -> "#N" (v2 expanded list).
SEQ_HASH = {
    "step", "tip", "rule", "law", "point", "reason", "principle", "habit",
    "mistake", "tactic", "strategy", "lesson", "factor", "secret", "key",
    "thing", "part", "phase", "option", "pillar", "trait", "example",
    "chapter", "myth", "hack", "takeaway",
}
# Sequence time/stage words -> plain "N". NB the v2 spec lists "level" in BOTH sets;
# we keep it PLAIN ("level 2" reads natural for games/tiers) — v1 behavior.
SEQ_PLAIN = {"day", "week", "month", "round", "level", "season"}

# ---- v2 spec Rule 4b: ordinals -------------------------------------------------
# "third" and above ALWAYS convert; "first"/"second" only before an ordinal-signaling
# noun (avoids the time unit "a second" and idioms "second nature" / "first of all").
ORDINAL_WORDS = {
    "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th",
    "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th",
    "eleventh": "11th", "twelfth": "12th", "thirteenth": "13th",
    "fourteenth": "14th", "fifteenth": "15th", "sixteenth": "16th",
    "seventeenth": "17th", "eighteenth": "18th", "nineteenth": "19th",
    "twentieth": "20th", "thirtieth": "30th", "fortieth": "40th",
    "fiftieth": "50th", "sixtieth": "60th", "seventieth": "70th",
    "eightieth": "80th", "ninetieth": "90th", "hundredth": "100th",
}
ORDINAL_NOUNS = {
    "thing", "things", "option", "options", "step", "steps", "reason", "reasons",
    "point", "points", "way", "ways", "place", "time", "lesson", "lessons",
    "rule", "rules", "principle", "principles", "mistake", "mistakes",
    "tip", "tips", "day", "week", "month", "year", "quarter", "round",
    "attempt", "attempts", "choice", "version", "draft", "chapter", "phase",
    "stage", "half", "part", "example", "priority", "pick", "question",
    "idea", "level",
}

# ---- v2 spec Rule 6: "grand" adjective guard -----------------------------------
# When a NOUN follows "grand" it's an adjective, not $1,000 ("a grand opening").
# Curated, freely extensible.
GRAND_NOUN_GUARD = {
    "opening", "openings", "slam", "slams", "total", "totals", "vision",
    "visions", "plan", "plans", "prize", "prizes", "scheme", "schemes",
    "gesture", "gestures", "finale", "piano", "pianos", "canyon", "jury",
    "entrance", "entrances", "strategy", "strategies", "idea", "ideas",
    "adventure", "adventures", "staircase", "ballroom", "hotel", "tour",
    "story", "stories", "house", "wedding", "event", "celebration",
    "reveal", "experiment", "unveiling", "prix",
}

# ---- v2 spec Rule 6: bare NK/NM quantity guard ----------------------------------
# A bare "250K"/"2.5M" token reads as money UNLESS a counting noun follows
# ("100K followers" stays). Superset of COUNTING_NOUNS + audience/metric nouns.
KM_QUANTITY_NOUNS = {
    "followers", "subscribers", "subs", "views", "downloads", "likes",
    "comments", "impressions", "visitors", "leads", "emails", "calls",
    "clips", "videos", "units", "steps", "feet", "miles", "words",
    "race", "races", "runs", "marathon",
}

# A magnitude is only MONEY if it isn't counting something else. "nine billion views" is a
# view count, not an amount — but a <number>+<magnitude> phrase used to be stamped with a
# "$" regardless ("$9B views", "$1K times more"). When the token right AFTER the magnitude
# names a countable thing, keep the compact magnitude and DROP the symbol -> "9B views".
# An explicit dollar word ("three million dollars") still wins: it is folded by Pass A
# before the count guard ever runs.
# ⚠️ KEEP IN SYNC with spice_normalize.py's NON_MONEY_AFTER (the standalone caption path
# uses oliver_format; the qa path uses spice_normalize — same SOP, two files).
NON_MONEY_AFTER = COUNTING_NOUNS | KM_QUANTITY_NOUNS | {
    "times", "x", "humans", "post", "posts", "reels", "shorts", "clip", "view",
    "messages", "pounds", "lbs", "second", "seconds", "minute", "minutes",
}

# ---- v2 spec Rule 7: multiplier words -> NX -------------------------------------
MULTIPLIER_WORDS = {"double": "2X", "triple": "3X", "quadruple": "4X"}
# Guards: don't convert idioms/compounds ("double down", "triple threat") or noun
# usages ("a double"). Curated, extensible.
MULT_NEXT_BLOCK = {
    "down", "check", "checked", "checking", "click", "cross", "take", "back",
    "date", "dip", "standard", "standards", "digit", "digits", "whammy",
    "trouble", "threat", "play", "or", "vision", "life", "agent", "agents",
    "major", "espresso", "shot", "shots", "bed", "room", "digits",
}
MULT_PREV_BLOCK = {"a", "the", "on", "body", "stunt"}

# v2 Rule 7: shapes "plus" may fold onto as "+" — a number, money, percent, or
# multiplier token ("$5M", "50%", "10X", "1,000", "$2 billion").
_PLUSABLE_RE = re.compile(
    r"^\$?\d[\d,]*(?:\.\d+)?(?:K|M|X|%)?$|^\$?\d+(?:\.\d+)? (?:[Bb]illion|[Tt]rillion)$"
)

# ---- v2 spec Rule 9: "school" -> "Skool" education-context guard -----------------
# The brand homophone converts EXCEPT in a real education context.
SCHOOL_EDU_MODIFIERS = {
    "high", "business", "grad", "graduate", "law", "med", "medical", "middle",
    "elementary", "trade", "public", "private", "old", "sunday", "charter",
    "boarding", "night", "summer", "film", "art", "driving", "flight",
    "primary", "secondary", "prep", "catholic", "christian", "military",
}
SCHOOL_EDU_NOUNS = {
    "district", "districts", "year", "years", "teacher", "teachers", "bus",
    "buses", "project", "projects", "kids", "kid", "day", "days", "dance",
    "lunch", "uniform", "uniforms", "work", "system", "systems", "board",
    "fees", "curriculum", "counselor", "principal", "shooting", "shootings",
}

# m-h-m affirmative family (mm-hmm, mmhmm, mhmm, mm-hm...) -> "mhm".
# Pattern m+ h+ m+ with hyphens ignored. Deliberately does NOT match "mmh" (no
# trailing m), "mm" (no h — handled by DICT_SINGLE -> "mmh"), or "hmm" (starts with h).
_MHM_RE = re.compile(r"^m+-?h+-?m+$")

# Rule-4 trigger words that KEEP "one" as a word.
KEEP_ONE_PREV = {
    "and", "but", "or", "so", "yet", "nor", "if", "when", "while", "because",
    "although", "though", "since", "unless", "after", "before", "until", "as",
    "once", "whereas", "whether", "the", "a", "an", "well", "now", "look", "okay",
    # pronoun/idiom formers — "one" here is NEVER a count ("no one will care",
    # "every one of them", "which one", "the wrong one"). Shipped "no 1 will care"
    # on a delivered clip 2026-06-12 — user: "don't make this mistake again".
    "no", "every", "any", "some", "each", "which", "this", "that", "only",
    "wrong", "right", "loved", "another",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def lc(s):
    return s.lower()


def is_pure_int_digits(s):
    """True if s is an integer token of digits, optionally with thousands commas."""
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", s))


def parse_int_token(s):
    """Return int value of a digit token (commas allowed), else None."""
    if re.fullmatch(r"\d{1,3}(,\d{3})*", s) or re.fullmatch(r"\d+", s):
        return int(s.replace(",", ""))
    return None


def add_thousands(n):
    """Format integer with thousands separators."""
    return f"{n:,}"


def _num_for_suffix(value, prev_tok):
    """Render the numeric part that precedes a % or X suffix, applying Rule-8 thousands
    separators when the value was SPOKEN as words and is >= 1,000 (the suffix is about
    to lock the token, so Rule 8 can't run on it afterward)."""
    if getattr(prev_tok, "spoken", False) and value >= 1000:
        return add_thousands(value)
    return str(value)


# Patterns for tokens already in correct OUTPUT form (idempotency — leave untouched).
_FMT_PATTERNS = [
    re.compile(r"^\$\d{1,3}(,\d{3})*$"),                 # $0 / $500 / $1,000 / $5,000
    re.compile(r"^\$\d+(\.\d+)?[KM]$"),                  # $1K / $50K / $1.2M / $100M
    re.compile(r"^\$\d+(\.\d+)?(?: [Bb]illion| [Tt]rillion)$"),  # $2 billion (v2 lowercase; old caps accepted)
    re.compile(r"^\$\d+(\.\d+)?$"),                      # $100
    re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?X('?\w*)?$"),  # 10X / 10X'ing / 2X / 2,000X
    re.compile(r"^\d+%$"),                               # 50% / 0%
    re.compile(r"^#\d+$"),                               # #1 / #2
    re.compile(r"^\d+(?:st|nd|rd|th)$"),                 # 3rd / 21st (v2 ordinals)
    re.compile(r"^\d+(\.\d+)?(?: billion| trillion)$"),  # 2 billion (v2 large non-money)
    re.compile(r"^etc\.$|^e\.g\.$|^i\.e\.$"),            # lowercase abbreviations
    re.compile(r"^(?:[A-Z]\.){2,}$"),                    # U.S.
]
# "$N Billion" / "$N Trillion" handled specially (two tokens) below.


def _is_already_formatted(text):
    for pat in _FMT_PATTERNS:
        if pat.fullmatch(text):
            return True
    return False


# v2: an already-"$" WHOLE-dollar literal >= $2,000 must re-format to the money table
# ("$100,000" -> $100K, "$2,000" -> $2K, "$1,000,000" -> $1M). Cents amounts ("$19.99")
# and K/M forms are left as-is; "$1,500" stays in the comma band.
_DOLLAR_WHOLE_RE = re.compile(r"^\$(\d{1,3}(?:,\d{3})+|\d+)$")


def _needs_money_renorm(text):
    m = _DOLLAR_WHOLE_RE.match(text)
    if not m:
        return False
    return int(m.group(1).replace(",", "")) >= 2000


# A "$N" / "$N.N" money amount, optionally with one leading word/article fused onto it by
# the STT tokenizer ("a $400", "the $5", "an $8") — Whisper frequently glues the article
# onto the money word as a single token. The amount must sit at the token start or right
# after a space, so we never pull a "$N" out of the middle of a malformed fragment.
_MONEY_SCALE_BASE_RE = re.compile(r"^(\S+\s+)?\$(\d+(?:\.\d+)?)$")

# A money token already in TERMINAL form (suffix K/M, or spelled-out Billion/Trillion) with
# one leading word/article glued on ("a $400M", "an $8 Billion") — the exact shape produced
# when an article-glued "$N" amount folds with a scale word. Re-locking it on a second pass
# stops capitalization from lowercasing the suffix ("$400M"->"$400m"), preserving idempotency.
_GLUED_TERMINAL_MONEY_RE = re.compile(r"^\S+\s+\$\d+(?:\.\d+)?(?:[KM]| [Bb]illion| [Tt]rillion)$")


def _money_scale_base(text):
    """If `text` is a '$N' / '$N.N' money amount (optionally with one leading word/article
    glued on, e.g. 'a $400'), return (prefix, num_str); otherwise None.

    The three rules that fold a money amount into a following scale word
    ("$400 million" -> "$400M") use this so the fold still fires when the STT glued an
    article onto the amount ("a $400") or the amount carries a decimal ("$1.5"). Without
    it the scale word falls through to number-word expansion and becomes "1,000,000".
    """
    m = _MONEY_SCALE_BASE_RE.match(text)
    if not m:
        return None
    return (m.group(1) or ""), m.group(2)


# ---------------------------------------------------------------------------
# Step 0a: fragment / dangling-dash cleanup (v2 spec Rule 2)
# ---------------------------------------------------------------------------

_DANGLING_DASH_RE = re.compile(r"[-–—]+$")


def apply_fragments(tokens):
    """v2 Rule 2: a hyphen/dash at the END of a token with nothing after it is a broken
    compound or cut-off word.

      - 1-2 letter stem + dash = half-word fragment -> DROP entirely ("s-", "va-").
        Exceptions: "a-" -> "a" (kept), "i-" -> "I".
      - longer stems keep the word, dash stripped ("short-" -> "short").
      - internal hyphens in compounds are untouched ("short-term", "1-on-1").

    A dropped fragment's sentence-final ?/! migrates to the previous token so the
    punctuation survives.
    """
    out = []
    for tok in tokens:
        if tok.locked or not _DANGLING_DASH_RE.search(tok.text):
            out.append(tok)
            continue
        stem = _DANGLING_DASH_RE.sub("", tok.text)
        if len(stem) <= 2 and lc(stem) not in ("a", "i"):
            # half-word fragment: drop, but keep any ?/! for the sentence
            keep = "".join(ch for ch in tok.trail if ch in "?!")
            if keep and out:
                out[-1].trail += keep
            continue
        tok.text = "I" if lc(stem) == "i" else stem
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Step 0: STT misspelling correction (runs BEFORE apply_dictionary)
# ---------------------------------------------------------------------------

def apply_misspellings(tokens):
    """Correct confirmed STT misspellings before dictionary/rule processing.

    Does NOT lock tokens — corrected text flows through all downstream rules
    normally. Specifically: "layla" -> "leila" (unlocked) so the phrase dict
    can still match ["leila", "hormozi"] -> "Leila Hormozi".
    """
    for tok in tokens:
        if not tok.locked:
            w = lc(tok.text)
            if w in MISSPELLINGS:
                tok.text = MISSPELLINGS[w]
    return tokens


# ---------------------------------------------------------------------------
# Rule 1: Dictionary (FIRST, authoritative)
# ---------------------------------------------------------------------------

def apply_dictionary(tokens):
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        matched = False
        # Try multi-word phrases (longest first by list order; check all, prefer longest)
        # Sort phrases by length desc to prefer 3-word over 2-word.
        for phrase, repl in sorted(DICT_PHRASES, key=lambda p: -len(p[0])):
            plen = len(phrase)
            if i + plen <= n:
                seq = [lc(tokens[i + k].text) for k in range(plen)]
                if seq == phrase and all(not tokens[i + k].locked for k in range(plen)):
                    # Build replacement tokens. Preserve lead of first, trail of last.
                    lead = tokens[i].lead
                    trail = tokens[i + plen - 1].trail
                    space_before = tokens[i].space_before
                    merged_src = _merge_src(*[tokens[i + k] for k in range(plen)])
                    for j, w in enumerate(repl):
                        t = Token(w,
                                  lead=lead if j == 0 else "",
                                  trail=trail if j == len(repl) - 1 else "",
                                  space_before=space_before if j == 0 else True,
                                  src=merged_src)
                        t.locked = True
                        out.append(t)
                    i += plen
                    matched = True
                    break
        if matched:
            continue
        tok = tokens[i]
        # Single-token dictionary
        key = lc(tok.text)
        # v2: "'cause" (straight or curly leading apostrophe) -> "cus'". A bare
        # "cause"/"because" is left alone.
        if not tok.locked and (key == "’cause" or (key == "cause" and tok.lead.endswith(("'", "’")))):
            tok.text = "cus'"
            if tok.lead.endswith(("'", "’")):
                tok.lead = tok.lead[:-1]
            tok.locked = True
        # v2: m-h-m affirmative family -> "mhm" ("mm" alone -> "mmh" via DICT_SINGLE;
        # "hmm" never touched).
        elif not tok.locked and _MHM_RE.fullmatch(key):
            tok.text = "mhm"
            tok.locked = True
        # v2: "school" -> "Skool" EXCEPT in an education context (modifier before or
        # education noun after). Singular token only; "schools" is left alone.
        elif not tok.locked and key == "school":
            prev_w = lc(tokens[i - 1].text) if i > 0 else ""
            nxt_w = lc(tokens[i + 1].text) if i + 1 < n else ""
            if prev_w not in SCHOOL_EDU_MODIFIERS and nxt_w not in SCHOOL_EDU_NOUNS:
                tok.text = "Skool"
                tok.locked = True
        elif key in DICT_SINGLE and not tok.locked:
            tok.text = DICT_SINGLE[key]
            tok.locked = True
        # Idempotency: already-correct acronym/format tokens lock themselves.
        elif tok.text in ACRONYMS:
            tok.locked = True
        elif tok.text == "1-on-1":
            tok.locked = True
        elif tok.text == "Acquisition.com":
            tok.locked = True
        elif _is_already_formatted(tok.text):
            # Don't lock a "$N" amount if a scale word follows — it must recombine
            # ("$100 million" -> $100M, "$1.5 billion" -> $1.5 billion) in the money pass
            # first. _money_scale_base also accepts a decimal amount ("$1.5").
            # v2: also don't lock a whole-dollar literal >= $2,000 ("$100,000") — the
            # money pass renormalizes it to the table ($100K).
            nxt_w = lc(tokens[i + 1].text) if i + 1 < n else ""
            if _money_scale_base(tok.text) and nxt_w in SCALES:
                pass
            elif _needs_money_renorm(tok.text):
                pass
            else:
                tok.locked = True
        elif _GLUED_TERMINAL_MONEY_RE.match(tok.text):
            # Idempotency: a 2nd pass sees a glued terminal-money token ("a $400M") whole
            # (one word) — lock it so capitalization can't lowercase the suffix.
            tok.locked = True
        out.append(tok)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Rule 2 (impl as 3): Number words -> digits, incl. compound numbers
# ---------------------------------------------------------------------------

def _collect_number_run(tokens, i):
    """Starting at index i, greedily collect a run of number words that compose a
    single numeric value. Returns (value, end_index, used)
    or None if tokens[i] is not a number word.

    Handles: ones/teens, tens [+ one], scales (hundred/thousand/million/...),
    compound: "fifty thousand", "one hundred thousand", "three hundred million",
    "five hundred", "two million".
    Also accepts a LEADING bare-digit token followed by a scale word, e.g.
    "44 million", "200 million", "5 thousand" -> combines digit * scale.
    Does NOT consume across non-number words.
    """
    n = len(tokens)
    j = i
    total = 0          # accumulated finished groups
    current = 0        # current group being built (below 1000)
    used = 0           # how many number words consumed
    saw_number = False

    # Allow a leading bare-digit token to seed `current` IF followed by a scale word.
    # The seed may carry a DECIMAL ("46.2 million", "1.5 million") — before that was
    # allowed, the decimal was left stranded and the lone scale word expanded on its own,
    # so "46.2 million in profit" burned as "46.2 $1M in profit".
    if j < n and not tokens[j].locked:
        dv = parse_int_token(tokens[j].text)
        if dv is None:
            qty = _parse_qty_token(tokens[j].text)
            if qty is not None and "." in qty:
                nxt_w = lc(tokens[j + 1].text) if (j + 1 < n and not tokens[j + 1].locked) else ""
                if nxt_w in SCALES:
                    scaled = Decimal(qty) * SCALES[nxt_w]
                    if scaled == scaled.to_integral_value():
                        return int(scaled), j + 2, 2
                return None  # stranded decimal: leave it to the money passes
        if dv is not None:
            nxt_w = lc(tokens[j + 1].text) if (j + 1 < n and not tokens[j + 1].locked) else ""
            if nxt_w in SCALES:
                current = dv
                saw_number = True
                used += 1
                j += 1
            else:
                return None  # bare digit not followed by scale: not our job

    while j < n:
        if tokens[j].locked:
            break
        w = lc(tokens[j].text)
        if w in ONES:
            if used and current == 0 and total == 0 and saw_number:
                # e.g. "fifty thousand five" -> would need additive; spec defers.
                break
            current += ONES[w]
            saw_number = True
            used += 1
            j += 1
        elif w in TENS:
            current += TENS[w]
            saw_number = True
            used += 1
            j += 1
            # allow "twenty two"
            if j < n and not tokens[j].locked and lc(tokens[j].text) in ONES and ONES[lc(tokens[j].text)] < 10 and lc(tokens[j].text) != "zero":
                current += ONES[lc(tokens[j].text)]
                used += 1
                j += 1
        elif w == "hundred":
            if current == 0:
                current = 1
            current *= 100
            saw_number = True
            used += 1
            j += 1
        elif w in ("thousand", "million", "billion", "trillion"):
            mult = SCALES[w]
            if current == 0:
                current = 1
            total += current * mult
            current = 0
            saw_number = True
            used += 1
            j += 1
            # stop after a big scale unless followed by another scale chain we already handle
            # (the "hundred thousand" case is handled because hundred set current first)
        else:
            break

    if not saw_number:
        return None
    value = total + current
    return value, j, used


def apply_number_words(tokens):
    """Convert number-word runs into a single digit token. Compound numbers combine.

    Special handling:
      - "a" before a scale word ("a thousand") -> behaves like "1" but in non-money
        context spec wants "a 1,000" (article kept). We keep "a" as its own token and
        convert the scale-run after it. Money rules later may consume the "a".
      - leave lone "one" tokens as the WORD for Rule 4 to decide; but if "one" is part
        of a larger compound (one hundred, one thousand) it IS consumed here.
      - "zero" stays "zero" unless directly followed by a money/percent word (handled
        partly here: we leave zero as word; money rule converts).
    """
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)

        # v2 Rule 3: "a"/"an" directly before a spoken SCALE word is the quantity "one" —
        # DROP the article and expand ("a thousand" -> "1,000", "a hundred bucks" -> 100
        # bucks, "a million people" -> 1,000,000 people). EXCEPTION: when "dollar(s)"
        # follows the amount, the article reads as the article for the priced item and is
        # KEPT ("a thousand dollars" -> "a $1,000").
        if w in ("a", "an") and i + 1 < n and not tokens[i + 1].locked \
                and lc(tokens[i + 1].text) in ("hundred", "thousand", "million", "billion", "trillion"):
            run = _collect_number_run(tokens, i + 1)
            if run is not None:
                value, end, _used = run
                after_w = lc(tokens[end].text) if (end < n and not tokens[end].locked) else ""
                if after_w in ("dollar", "dollars"):
                    out.append(tok)  # keep the article; the money pass folds the amount
                    newtok = Token(str(value), lead=tokens[i + 1].lead,
                                   trail=tokens[end - 1].trail, space_before=True,
                                   spoken=True, src=_merge_src(*tokens[i + 1:end]))
                else:
                    newtok = Token(str(value), lead=tok.lead,
                                   trail=tokens[end - 1].trail,
                                   space_before=tok.space_before,
                                   spoken=True, src=_merge_src(tok, *tokens[i + 1:end]))
                out.append(newtok)
                i = end
                continue

        # Lone "one": defer to Rule 4 unless it begins a compound (one hundred/thousand/...).
        if w == "one":
            nxt = lc(tokens[i + 1].text) if i + 1 < n and not tokens[i + 1].locked else ""
            if nxt in ("hundred", "thousand", "million", "billion", "trillion"):
                pass  # fall through to compound collection
            else:
                out.append(tok)  # keep word; Rule 4 decides
                i += 1
                continue

        # "zero": keep as word here; money/percent conversion handled in Rule 6/5.
        if w == "zero":
            out.append(tok)
            i += 1
            continue

        # Lone scale word immediately after a "$N" amount: leave for the money pass to
        # recombine (e.g. "$100 million" -> $100M). _money_scale_base also recognizes an
        # STT-glued-article amount ("a $400") and a decimal ("$1.5"), so the scale word
        # never falls through here and expands to 1,000,000.
        if w in SCALES and out:
            prev = out[-1]
            if _money_scale_base(prev.text):
                out.append(tok)
                i += 1
                continue

        run = _collect_number_run(tokens, i)
        if run is not None:
            value, end, _used = run
            # Build a single digit token. No comma yet (Rule 7 adds it / money rule).
            # spoken=True ONLY when at least one true number WORD was used (a leading
            # bare-digit seed like "5000" stays non-spoken; "5 thousand" becomes spoken).
            seeded_by_bare_digit = parse_int_token(tokens[i].text) is not None
            produced_spoken = (not seeded_by_bare_digit) or (end - i) > 1
            newtok = Token(str(value),
                           lead=tokens[i].lead,
                           trail=tokens[end - 1].trail,
                           space_before=tokens[i].space_before,
                           spoken=produced_spoken,
                           src=_merge_src(*tokens[i:end]))
            out.append(newtok)
            i = end
            continue

        out.append(tok)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Rule 3 (impl): "one" vs "1"
# ---------------------------------------------------------------------------

def apply_one_vs_1(tokens):
    out = []
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok.locked:
            out.append(tok)
            continue
        if lc(tok.text) != "one":
            out.append(tok)
            continue
        # Decide.
        prev = None
        for k in range(i - 1, -1, -1):
            prev = tokens[k]
            break
        nxt = tokens[i + 1] if i + 1 < n else None
        prev_w = lc(prev.text) if prev is not None else None
        nxt_w = lc(nxt.text) if nxt is not None else None

        # Next word forces "1": money word or another number.
        next_is_money = nxt_w in MONEY_WORDS if nxt_w else False
        next_is_number = bool(nxt and (is_pure_int_digits(nxt.text) or lc(nxt.text) in ONES or lc(nxt.text) in TENS or lc(nxt.text) in SCALES)) if nxt else False
        if next_is_money or next_is_number:
            tok.text = "1"
            out.append(tok)
            continue

        # DEFAULT = KEEP THE WORD. In conversational speech a bare "one" is overwhelmingly the
        # pronoun / article — "no one", "one of the most", "the one thing", "is one of", "become
        # one", "which one" — NOT a digit-worthy count. The ONLY paths to a numeral are the
        # positive signals above (money / adjacent number, e.g. "one hundred" handled upstream) and
        # the listicle labels "number/step/day one" -> "#1", which apply_listicle_sequence handles
        # DOWNSTREAM by matching the WORD "one" (so keeping the word here does not break "#1").
        #
        # This replaces the old "default to 1" which shipped THREE numeral bugs in one batch
        # (2026-06-12: "no 1 will care", "judgment is 1") — every one a pronoun mis-read as a count.
        # KEEP_ONE_PREV / prev / nxt are left computed for clarity but no longer gate the keep.
        _ = (prev_w, nxt_w, KEEP_ONE_PREV)  # (kept for readability; default is now KEEP)
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Rule 4b (impl, v2): Ordinals
# ---------------------------------------------------------------------------

def apply_ordinals(tokens):
    """v2 Rule 4b: "third" and above ALWAYS convert to ordinal numerals (3rd, 4th, ...).
    "first"/"second" stay words UNLESS directly followed by an ordinal-signaling noun
    ("the second thing" -> "the 2nd thing"; "second nature" / "a second" untouched)."""
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok.locked:
            continue
        w = lc(tok.text)
        if w in ORDINAL_WORDS:
            tok.text = ORDINAL_WORDS[w]
            tok.locked = True
        elif w in ("first", "second") and i + 1 < n \
                and lc(tokens[i + 1].text) in ORDINAL_NOUNS:
            tok.text = "1st" if w == "first" else "2nd"
            tok.locked = True
    return tokens


# ---------------------------------------------------------------------------
# Rule 4 (impl): Listicle & sequence labels
# ---------------------------------------------------------------------------

def apply_listicle_sequence(tokens):
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)

        # Listicle: "number" directly precedes a numeral -> "#N"
        if w == "number" and i + 1 < n:
            nxt = tokens[i + 1]
            val = parse_int_token(nxt.text)
            nxt_w = lc(nxt.text)
            if val is None and nxt_w in ONES:
                val = ONES[nxt_w]
            if val is not None:
                newtok = Token(f"#{val}",
                               lead=tok.lead,
                               trail=nxt.trail,
                               space_before=tok.space_before,
                               src=_merge_src(tok, nxt))
                newtok.locked = True
                out.append(newtok)
                i += 2
                continue

        # Sequence labels: list-item word followed by a numeral.
        if (w in SEQ_HASH or w in SEQ_PLAIN) and i + 1 < n:
            nxt = tokens[i + 1]
            val = parse_int_token(nxt.text)
            nxt_w = lc(nxt.text)
            if val is None and nxt_w in ONES:
                val = ONES[nxt_w]
            if val is not None:
                # keep the label word, replace number token
                out.append(tok)
                if w in SEQ_HASH:
                    newtok = Token(f"#{val}", lead="", trail=nxt.trail, space_before=True,
                                   src=_merge_src(nxt))
                else:
                    newtok = Token(str(val), lead="", trail=nxt.trail, space_before=True,
                                   src=_merge_src(nxt))
                newtok.locked = True
                out.append(newtok)
                i += 2
                continue

        out.append(tok)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Rule 5 (impl): Money formatting
# ---------------------------------------------------------------------------

def format_money_value(value):
    """Format an integer dollar value per the v2 money table.

    $1-$999 -> $N
    $1,000-$1,999 -> $N,000  (the ONLY comma band)
    $2,000-$999,999 -> $NK
    $1M-$999.9M -> $NM
    $1B-$999.9B -> $N billion   (lowercase, per v2)
    $1T-$999.9T -> $N trillion
    """
    if value == 0:
        return "$0"
    if value < 1000:
        return f"${value}"
    if value < 2000:
        return f"${add_thousands(value)}"
    if value < 1_000_000:
        k = value / 1000
        return f"${_trim(k)}K"
    if value < 1_000_000_000:
        m = value / 1_000_000
        return f"${_trim(m)}M"
    if value < 1_000_000_000_000:
        b = value / 1_000_000_000
        return f"${_trim(b)} billion"
    t = value / 1_000_000_000_000
    return f"${_trim(t)} trillion"


def compact_magnitude(value):
    """The COUNT form of the money table: "<mantissa><K|M|B|T>" with NO "$".

    Used when a <number>+<magnitude> phrase is counting something rather than naming an
    amount ("nine billion views" -> "9B views", "a thousand times" -> "1K times").
    Returns None when the value is not a clean single-magnitude quantity (mantissa with at
    most one decimal), so an odd number falls through to Rule 8's plain scaling.
    ⚠️ KEEP IN SYNC with spice_normalize.py (MAG + fmt_mant)."""
    for power, suffix in ((1_000_000_000_000, "T"), (1_000_000_000, "B"),
                          (1_000_000, "M"), (1000, "K")):
        if value < power:
            continue
        # Inside the thousands band only EXACT thousands compact, so a spoken "fifteen
        # hundred people" keeps Rule 8's comma form ("1,500 people") instead of "1.5K".
        if power == 1000 and value % 1000 != 0:
            return None
        mant = value / power
        if abs(mant * 10 - round(mant * 10)) > 1e-9:
            return None  # more precision than one decimal: not a clean magnitude phrase
        return f"{_trim(mant)}{suffix}"
    return None


def format_money_shorthand_k(value):
    """$NK form for $1,000-$19,999 spoken shorthand (1k/5k/10k)."""
    if value < 1000:
        return f"${value}"
    k = value / 1000
    return f"${_trim(k)}K"


def _trim(x):
    """Trim trailing .0 from a float; keep one decimal otherwise."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.1f}".rstrip("0").rstrip(".")


# Numeric quantity that may carry a decimal point (e.g. "1.5", "3.5", "100").
_NUM_QTY_RE = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")


def _parse_qty_token(text):
    """Parse a bare numeric quantity token (integer or decimal, commas allowed) into a
    normalized numeric STRING for compact-money rendering (commas stripped, trailing .0
    dropped). Returns None if the token isn't a clean standalone quantity.

    Used by the spoken-money SHORTHAND pass so "1.5"/"3.5"/"100" all render compactly
    ("1.5", "3.5", "100") in "$<n>K" / "$<n>M". Conservative: the WHOLE token must be the
    number, so symbols-suffixed tokens ("$5", "10X", "#1") never match here.
    """
    if not _NUM_QTY_RE.fullmatch(text):
        return None
    raw = text.replace(",", "")
    try:
        float(raw)
    except ValueError:
        return None
    # Render: keep the spoken precision exactly (".25" must survive). Strip a redundant
    # trailing ".0"/".00" and any trailing zeros on a real fraction; never round.
    if "." in raw:
        intpart, frac = raw.split(".", 1)
        frac = frac.rstrip("0")
        return intpart if frac == "" else f"{intpart}.{frac}"
    return str(int(raw))


def _value_from_number_token(tok):
    """Get integer value from a (possibly digit, possibly K-shorthand) token."""
    v = parse_int_token(tok.text)
    if v is not None:
        return v, False  # (value, was_shorthand_k)
    m = re.fullmatch(r"(\d+)k", lc(tok.text))
    if m:
        return int(m.group(1)) * 1000, True
    m = re.fullmatch(r"\$?(\d+)k", lc(tok.text))
    if m:
        return int(m.group(1)) * 1000, True
    return None, False


# Money-unit words a collapsed word-fraction ("three and a half" -> 3.5) is allowed to
# precede. Gated to the SLANG money shorthands only, so the collapse can ONLY fire in an
# unambiguous money context — it never rewrites "an hour and a half" / "three and a half
# years", and it never touches the full-word "million"/"thousand" (which keep their plain
# digit-expansion semantics, e.g. "three million" -> 3,000,000, unless an explicit
# "dollars"/trigger is present).
_FRACTION_MONEY_UNITS = {"k", "mil", "m", "grand"}
# Spoken word-fraction tails -> decimal STRING addend. Common cases only (task scope).
_FRACTION_TAILS = {
    ("and", "a", "half"): "0.5",
    ("and", "a", "quarter"): "0.25",
}


def _fraction_decimal(base_int, tail_str):
    """Render an integer + a spoken fraction tail ("0.5"/"0.25") as a clean decimal string
    with no trailing-zero loss (e.g. 3 + '0.5' -> '3.5', 5 + '0.25' -> '5.25')."""
    from decimal import Decimal
    d = Decimal(base_int) + Decimal(tail_str)
    s = format(d.normalize(), "f")
    return s


def apply_money(tokens):
    """Apply money formatting. Handles:
       - word-number fractions in a money context ("three and a half mil" -> 3.5 mil)
       - explicit dollars/dollar after a number -> $ formatting
       - "$N" + scale word recombination
       - grand and spoken shorthand units (k / mil / m)
       - implied money (rate phrase, very large, trigger words) with guards
       - year guard
       - zero dollars/percent
    """
    n = len(tokens)

    # Pass 0: word-number FRACTION collapse, money-gated.
    # "<int> and a half|quarter <money-unit>" -> "<int>.5|.25 <money-unit>". Conservative:
    # the integer must be a clean number token, the tail must be exactly "and a half" /
    # "and a quarter", and a money unit (k / mil / m / grand / thousand / million / ...)
    # must immediately follow — so non-money phrases ("three and a half years") are
    # untouched. The resulting decimal is consumed by the shorthand/scale money passes
    # below ("3.5 mil" -> "$3.5M").
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        base = parse_int_token(tok.text)
        if base is not None and i + 4 < len(tokens):
            tail = tuple(lc(tokens[i + k].text) for k in range(1, 4))
            unit = lc(tokens[i + 4].text)
            if tail in _FRACTION_TAILS and unit in _FRACTION_MONEY_UNITS \
                    and all(not tokens[i + k].locked for k in range(1, 4)):
                dec_str = _fraction_decimal(base, _FRACTION_TAILS[tail])
                newtok = Token(dec_str, lead=tok.lead, trail=tokens[i + 3].trail,
                               space_before=tok.space_before,
                               spoken=True,
                               src=_merge_src(*tokens[i:i + 4]))
                out.append(newtok)
                i += 4
                continue
        out.append(tok)
        i += 1
    tokens = out
    n = len(tokens)

    # Precompute lowercased cores for context scanning.
    cores = [lc(t.text) for t in tokens]

    # Pass A: explicit "<number> dollar(s)" and "zero dollars"
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)

        # v2: renormalize an already-"$" whole-dollar literal >= $2,000 to the table
        # ("$100,000" -> $100K, "$2,000" -> $2K). Skip when a scale word follows — the
        # "$N + scale" fold below owns that shape.
        if _needs_money_renorm(tok.text) \
                and not (i + 1 < n and lc(tokens[i + 1].text) in SCALES):
            val = int(tok.text[1:].replace(",", ""))
            tok.text = format_money_value(val)
            tok.locked = True
            out.append(tok)
            i += 1
            continue

        # zero dollars -> $0
        if w == "zero" and i + 1 < n and lc(tokens[i + 1].text) in ("dollar", "dollars"):
            newtok = Token("$0", lead=tok.lead, trail=tokens[i + 1].trail, space_before=tok.space_before,
                           src=_merge_src(tok, tokens[i + 1]))
            newtok.locked = True
            out.append(newtok)
            i += 2
            continue
        # zero percent / percentage -> handled in Rule 6, but convert zero->0 there.

        # "$N" + scale word  (e.g. "$100 million", "$5 thousand", "$2 billion").
        # _money_scale_base also matches an STT-glued-article amount ("a $400 million") and
        # a decimal amount ("$1.5 billion"); any glued leading word is preserved verbatim on
        # the folded token ("a $400" + "million" -> "a $400M").
        msb = _money_scale_base(tok.text)
        if msb and i + 1 < n and lc(tokens[i + 1].text) in ("thousand", "million", "billion", "trillion"):
            prefix, num = msb
            scale = SCALES[lc(tokens[i + 1].text)]
            value = int(Decimal(num) * scale)  # exact; scale >= 1000 so always whole
            newtok = Token(prefix + format_money_value(value), lead=tok.lead,
                           trail=tokens[i + 1].trail, space_before=tok.space_before,
                           src=_merge_src(tok, tokens[i + 1]))
            newtok.locked = True
            out.append(newtok)
            i += 2
            continue

        # number token followed by dollar(s)
        val, was_k = _value_from_number_token(tok)
        if val is not None and i + 1 < n and lc(tokens[i + 1].text) in ("dollar", "dollars"):
            # v2: only the $1,000-$1,999 comma band needs shorthand disambiguation
            # ("1k dollars" -> $1K); everything >= $2,000 is $NK via the table anyway.
            if 1000 <= val < 2000 and was_k:
                txt = format_money_shorthand_k(val)
            else:
                txt = format_money_value(val)
            newtok = Token(txt, lead=tok.lead, trail=tokens[i + 1].trail, space_before=tok.space_before,
                           src=_merge_src(tok, tokens[i + 1]))
            newtok.locked = True
            out.append(newtok)
            i += 2
            continue

        out.append(tok)
        i += 1
    tokens = out
    n = len(tokens)

    # Pass A2: spoken-money SHORTHAND units  "<qty> k|mil|m" -> "$<qty>K" / "$<qty>M".
    # Conservative: fires ONLY when a CLEAN standalone numeric quantity (integer or
    # decimal, e.g. "50", "3", "1.5") sits immediately before the unit token. The unit
    # must be exactly "k" / "mil" / "m" (slang shorthands that imply money in this
    # domain). Bare full-words "thousand" / "million" are intentionally NOT money-ized
    # here — they keep their plain digit-expansion semantics ("two million" -> 2,000,000)
    # and only become money via an explicit "dollars" / money-trigger elsewhere.
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)
        if w in ("k", "mil", "m") and out:
            prev = out[-1]
            qty = None if prev.locked else _parse_qty_token(prev.text)
            if qty is not None:
                suffix = MONEY_UNIT_SUFFIX[w]
                consumed = out.pop()  # the quantity token
                newtok = Token(f"${qty}{suffix}", lead=consumed.lead,
                               trail=tok.trail or consumed.trail,
                               space_before=consumed.space_before,
                               src=_merge_src(consumed, tok))
                newtok.locked = True
                out.append(newtok)
                i += 1
                continue
        out.append(tok)
        i += 1
    tokens = out
    n = len(tokens)

    # Pass A3 (v2): "bucks" = colloquial dollars. Delete it right after a money amount
    # ("20 bucks" -> $20, "$1M bucks" -> $1M); keep it otherwise ("a couple bucks").
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        w = lc(tok.text)
        if w == "bucks" and not tok.locked and out:
            prev = out[-1]
            if prev.text.startswith("$"):
                # already-formatted money: absorb "bucks"
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue
            pv = parse_int_token(prev.text) if not prev.locked else None
            if pv is not None:
                prev.text = format_money_value(pv)
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue
        out.append(tok)
        i += 1
    tokens = out
    n = len(tokens)

    # Pass A4 (v2): a bare UPPERCASE K/M-suffixed number ("250K", "2.5M") reads as money
    # -> prepend "$", UNLESS a counting/quantity noun follows ("100K followers" stays).
    # Lowercase "5k"/"3m" keep the v1 trigger-context behavior (Pass C) — ASR writes
    # race distances and casual counts lowercase ("i run 5k").
    # Skipped for a single isolated token (idempotency: Rule 8's own "2M" output must
    # not money-ize when re-fed, matching the isolated-number suppression in Pass C).
    _isolated_a4 = len([t for t in tokens if t.text]) == 1
    out = []
    for i, tok in enumerate(tokens):
        if not tok.locked and not _isolated_a4:
            m = re.fullmatch(r"(\d+(?:\.\d+)?)([KM])", tok.text)
            if m:
                nxt_w = lc(tokens[i + 1].text) if i + 1 < n else ""
                if nxt_w in NON_MONEY_AFTER:
                    tok.locked = True  # quantity — freeze so capitalization can't lowercase the K
                else:
                    tok.text = f"${m.group(1)}{m.group(2)}"
                    tok.locked = True
        out.append(tok)
    tokens = out
    n = len(tokens)

    # Pass B: "grand" handling.  <number|a|one> grand
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)
        if w == "grand":
            # v2 guard: a NOUN after "grand" makes it an adjective, not $1,000
            # ("a grand opening", "a grand slam offer" stay words).
            nxt_w = lc(tokens[i + 1].text) if i + 1 < n else ""
            if nxt_w in GRAND_NOUN_GUARD:
                out.append(tok)
                i += 1
                continue
            # DECIMAL quantity before "grand" ("1.5 grand") -> compact "$1.5K". A whole-
            # number grand still routes through the integer path below (so the money table
            # + article-dropping for "a hundred grand" stay intact).
            if out and not out[-1].locked:
                pdec = _parse_qty_token(out[-1].text)
                if pdec is not None and "." in pdec:
                    consumed = out.pop()
                    newtok = Token(f"${pdec}K", lead=consumed.lead,
                                   trail=tok.trail or consumed.trail,
                                   space_before=consumed.space_before,
                                   src=_merge_src(consumed, tok))
                    newtok.locked = True
                    out.append(newtok)
                    i += 1
                    continue
            # look back at previous emitted token for the multiplier
            mult = None
            consumed_prev = False
            if out:
                prev = out[-1]
                pv = parse_int_token(prev.text)
                pw = lc(prev.text)
                if pv is not None and not prev.locked:
                    mult = pv
                    consumed_prev = True
                elif pw in ("a", "one") and not prev.locked:
                    mult = 1
                    consumed_prev = True
                elif pw in ONES and not prev.locked:
                    mult = ONES[pw]
                    consumed_prev = True
            if mult is None:
                mult = 1
            value = mult * 1000
            consumed_toks = [tok]
            if consumed_prev:
                consumed_toks.insert(0, out.pop())
                # If an article "a"/"an" precedes the consumed number ("a hundred grand"),
                # it was the "one" article -> drop it.
                if out and lc(out[-1].text) in ("a", "an") and not out[-1].locked:
                    consumed_toks.insert(0, out.pop())
            txt = format_money_value(value)
            newtok = Token(txt, lead=(out and "" or tok.lead) or tok.lead,
                           trail=tok.trail, space_before=tok.space_before,
                           src=_merge_src(*consumed_toks))
            newtok.locked = True
            out.append(newtok)
            i += 1
            continue
        out.append(tok)
        i += 1
    tokens = out
    n = len(tokens)
    cores = [lc(t.text) for t in tokens]

    # Pass B2 (2026-08-11, ported from spice_normalize's NON_MONEY_AFTER fix): a SPOKEN
    # <number>+<magnitude> phrase whose next word names a countable thing is a COUNT, not
    # an amount — render the compact magnitude WITHOUT "$" and LOCK it ("nine billion
    # views" -> "9B views", "a thousand times more" -> "1K times more"). Locking is the
    # point: it stops Rule 7 folding the count noun ("times" -> "X") and stops Rule 8
    # re-rendering the magnitude as a word ("9 billion"). Explicit dollar words were
    # already folded to money by Pass A, which locks — so money never reaches here.
    # Only SPOKEN values qualify (the magnitude was said out loud); a bare digit literal
    # ("1,000 views") keeps Rule 8's plain scaling.
    for i, tok in enumerate(tokens):
        if tok.locked or not tok.spoken:
            continue
        val = parse_int_token(tok.text)
        if val is None or val < 1000:
            continue
        next_core = lc(tokens[i + 1].text) if i + 1 < n else ""
        if next_core not in NON_MONEY_AFTER:
            continue
        compact = compact_magnitude(val)
        if compact:
            tok.text = compact
            tok.locked = True
    cores = [lc(t.text) for t in tokens]

    # Is the WHOLE input a single isolated number? (e.g. "three hundred million")
    # If so, suppress the very-large auto-money rule — an isolated number is a count
    # demonstration, not an amount in running speech.
    nonempty = [t for t in tokens if t.text]
    isolated_number = (len(nonempty) == 1 and parse_int_token(nonempty[0].text) is not None)

    # Pass C: implied money on bare number tokens.
    out = []
    drop_idx = set()
    for i, tok in enumerate(tokens):
        if tok.locked or i in drop_idx:
            if i not in drop_idx:
                out.append(tok)
            continue
        val = parse_int_token(tok.text)
        # Also recognize spoken-shorthand "K" tokens ("5k", "10k", "50k") so implied
        # money context can format them ("the price is 5k" -> "the price is $5K").
        is_shorthand_k = False
        if val is None:
            kv, was_k = _value_from_number_token(tok)
            if was_k:
                val = kv
                is_shorthand_k = True
        if val is None:
            out.append(tok)
            continue

        # Year guard: a bare 4-digit DIGIT literal in 1900-2099 is a year, not money.
        # Word-spoken amounts ("two thousand"->2000) are EXEMPT from the year guard
        # (spec Rule 6/8), so only pre-existing digit literals trigger it.
        is_yearish = (not tok.spoken) and bool(re.fullmatch(r"\d{4}", tok.text)) and 1900 <= val <= 2099

        money = False
        rate_drop_prev_a = False

        # 1. Rate phrase (highest): number followed by "a"/"an" + rate unit.
        if i + 2 < len(tokens) and lc(tokens[i + 1].text) in ("a", "an") \
                and lc(tokens[i + 2].text) in RATE_UNITS:
            money = True
            # the leading "a" meaning "one" before the AMOUNT is dropped (if present);
            # the rate "a" (tokens[i+1]) is KEPT.
            if out and lc(out[-1].text) in ("a", "an") and not out[-1].locked:
                rate_drop_prev_a = True

        # 2. Counting-noun guard: number directly followed by a counting/quantity noun
        #    -> NOT money ("2 million people", "50K subscribers" are quantities; the
        #    large-number pass scales them without "$"). A following multiplier/percent
        #    word also blocks money — "a million times" is 1,000,000X, not $1M.
        next_core = lc(tokens[i + 1].text) if i + 1 < len(tokens) else ""
        if next_core in NON_MONEY_AFTER or next_core in ("percent", "percentage"):
            out.append(tok)
            continue

        # 3. Very large numbers (v2): anything >= $1M is money, no trigger needed
        #    (unless isolated — a lone number without sentence context is a count demo).
        if not money and val >= 1_000_000 and not isolated_number and not is_yearish:
            money = True

        # 4. Reliable trigger words within ~8 before / 3 after.
        trigger_drop_prev_a = False
        if not money and not is_yearish:
            if _has_money_trigger(cores, i, before=8, after=3) and val >= 1000:
                money = True
                # standalone money answer: "a thousand" -> "$1,000" (consume the "a").
                # Only when the amount is the standalone value (end of clause), NOT when
                # an item noun follows ("a 100 dollar deal" keeps "a").
                is_last = (i + 1 >= len(tokens)) or bool(re.search(r"[\.\?\!]", tokens[i].trail))
                if is_last and out and lc(out[-1].text) in ("a", "an") and not out[-1].locked:
                    trigger_drop_prev_a = True

        if is_yearish:
            money = False

        if money:
            consumed_toks = [tok]
            if rate_drop_prev_a or trigger_drop_prev_a:
                consumed_toks.insert(0, out.pop())  # drop the preceding article "a"/"an"
            # Shorthand-K in the $1,000-$1,999 comma band stays $NK ("1k"->$1K);
            # everything >= $2,000 follows the standard money table ($NK anyway).
            if is_shorthand_k and 1000 <= val < 2000:
                txt = format_money_shorthand_k(val)
            else:
                txt = format_money_value(val)
            newtok = Token(txt, lead=tok.lead, trail=tok.trail, space_before=tok.space_before,
                           src=_merge_src(*consumed_toks))
            newtok.locked = True
            out.append(newtok)
            continue

        out.append(tok)

    # Pass D (v2): EMBEDDED "$"-comma amounts inside a GLUED token. Groq writes money
    # enumerations as ONE word ("make $200,000, $300,000, $400,000"), so the whole-token
    # renorm above never sees them (caught live by caption_lint on the 2026-07-06 e2e
    # verify). Rewrite each embedded whole-dollar amount >= $2,000 to the table.
    def _renorm_embedded(m):
        v = int(m.group(1).replace(",", ""))
        return format_money_value(v) if v >= 2000 else m.group(0)

    for tok in out:
        if not tok.locked and "$" in tok.text and "," in tok.text:
            tok.text = re.sub(r"\$(\d{1,3}(?:,\d{3})+)(?!\d)", _renorm_embedded, tok.text)

    # Pass E (v2, caught by the 2026-07-06 Oliver-corpus verify): a bare lowercase k/m
    # number RANGED with an explicit money token inherits money-ness — "from 600k to
    # $5M" -> "$600K to $5M" (Oliver's published caption reads "$600K to"). Lowercase
    # k/m normally keeps the trigger-context behavior (race distances, "i run 5k"), but
    # "to"/"or"/"through" joining it to a "$" amount IS the money context.
    def _money_tok(j):
        return 0 <= j < len(out) and out[j].text.startswith("$")

    for i, tok in enumerate(out):
        if tok.locked:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)([kmKM])", tok.text)
        if not m:
            continue
        joined_fwd = (i + 2 < len(out) and lc(out[i + 1].text) in ("to", "or", "through")
                      and _money_tok(i + 2))
        joined_back = (i - 2 >= 0 and lc(out[i - 1].text) in ("to", "or", "through")
                       and _money_tok(i - 2))
        if joined_fwd or joined_back:
            scale = 1000 if m.group(2).lower() == "k" else 1_000_000
            val = float(m.group(1)) * scale
            if val == int(val):
                tok.text = format_money_value(int(val))
            else:
                tok.text = f"${m.group(1)}{m.group(2).upper()}"
            tok.locked = True
    return out


def _has_money_trigger(cores, idx, before, after):
    n = len(cores)
    lo = max(0, idx - before)
    hi = min(n, idx + after + 1)
    for k in range(lo, hi):
        if k == idx:
            continue
        c = cores[k].strip(".,!?")
        if c in MONEY_TRIGGERS:
            return True
        # charge/charging/charged prefix
        if c.startswith("charg"):
            return True
    return False


# ---------------------------------------------------------------------------
# Rule 6 (impl): Symbol & multiplier rule
# ---------------------------------------------------------------------------

def apply_symbols_multipliers(tokens):
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.locked:
            out.append(tok)
            i += 1
            continue
        w = lc(tok.text)

        # percent / percentage after a number -> N%
        # (% locks the token, so Rule-8 thousands can't run afterward — apply the comma
        #  HERE for spoken values >= 1,000: "fifty thousand percent" -> "50,000%".)
        if w in ("percent", "percentage") and out:
            prev = out[-1]
            pv = parse_int_token(prev.text)
            pw = lc(prev.text)
            if pv is not None and not prev.locked:
                prev.text = f"{_num_for_suffix(pv, prev)}%"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue
            if pw == "zero" and not prev.locked:
                prev.text = "0%"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue

        # bare "%" symbol after a number (or "zero") -> N% (spec Rule 3 zero exception)
        if tok.text == "%" and out:
            prev = out[-1]
            pv = parse_int_token(prev.text)
            pw = lc(prev.text)
            if pv is not None and not prev.locked:
                prev.text = f"{_num_for_suffix(pv, prev)}%"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue
            if pw == "zero" and not prev.locked:
                prev.text = "0%"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue

        # bare "$" symbol after "zero" -> $0 (spec Rule 3 zero exception: '$' trigger)
        if tok.text == "$" and out:
            prev = out[-1]
            if lc(prev.text) == "zero" and not prev.locked:
                prev.text = "$0"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue

        # times -> X after a number (no space)
        # (X locks the token — apply Rule-8 comma HERE: "two thousand times" -> "2,000X".)
        if w == "times" and out:
            prev = out[-1]
            pv = parse_int_token(prev.text)
            if pv is not None and not prev.locked:
                prev.text = f"{_num_for_suffix(pv, prev)}X"
                prev.locked = True
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                i += 1
                continue

        # spoken/typed "x" multiplier normalization: 10x -> 10X, 10x'ing -> 10X'ing, 2xing->2Xing.
        # The number part matches the RAW digits INCLUDING a thousands separator, so a comma
        # survives ("1,000x" -> "1,000X"); matching bare digits only used to miss the token
        # entirely and leave a lowercase "1,000x" burned in.
        m = re.fullmatch(r"(\d[\d,]*)x('?\w*)", w)
        if m and tok.text[0].isdigit():
            num = m.group(1)
            suffix = tok.text[len(num) + 1:]  # preserve original-case suffix after x
            tok.text = f"{num}X{suffix}"
            tok.locked = True
            out.append(tok)
            i += 1
            continue

        # v2: "plus" -> "+" ONLY directly after a number/money/percent token
        # ("$5M plus" -> "$5M+", "50% plus" -> "50%+", "1 plus" -> "1+").
        # Otherwise it stays the word ("a plus player"). The previous token is usually
        # LOCKED money — this fold is explicitly allowed to append to it.
        if w == "plus" and out:
            prev = out[-1]
            if _PLUSABLE_RE.fullmatch(prev.text):
                prev.text = prev.text + "+"
                prev.trail = tok.trail or prev.trail
                prev.src = _merge_src(prev, tok)
                prev.locked = True
                i += 1
                continue

        # v2: multiplier words -> NX ("double revenue" -> "2X revenue"). Guarded against
        # idioms/compounds ("double down", "triple threat") and noun usages ("a double").
        if w in MULTIPLIER_WORDS and not tok.locked:
            prev_w = lc(out[-1].text) if out else ""
            nxt_w = lc(tokens[i + 1].text) if i + 1 < n else ""
            if prev_w not in MULT_PREV_BLOCK and nxt_w not in MULT_NEXT_BLOCK:
                tok.text = MULTIPLIER_WORDS[w]
                tok.locked = True
                out.append(tok)
                i += 1
                continue

        out.append(tok)
        i += 1

    # v2 post-pass: percentage RANGE distribution — a bare number joined by "to"/"through"
    # to a number that carries "%" takes "%" too ("10 to 20%" -> "10% to 20%").
    # A non-percentage range is untouched ("5 to 10 people").
    for k in range(len(out) - 2):
        a, mid, b = out[k], out[k + 1], out[k + 2]
        if lc(mid.text) in ("to", "through") and re.fullmatch(r"\d+(?:,\d{3})*%", b.text) \
                and not a.locked and parse_int_token(a.text) is not None:
            a.text = f"{_num_for_suffix(parse_int_token(a.text), a)}%"
            a.locked = True
    return out


# ---------------------------------------------------------------------------
# Rule 8 (impl, v2): Large non-money numbers — money scale structure WITHOUT "$"
# ---------------------------------------------------------------------------

def apply_large_numbers(tokens):
    """v2 Rule 8: a number >= 1,000 that is NOT money follows the money table without
    the "$" — surface form irrelevant ("fifty thousand subscribers" AND "300,000
    customers" both -> K form; always "300K", never "300,000").

      1,000-1,999   -> comma form (1,500)
      2,000-999,999 -> NK (50K)
      1M-999.9M     -> NM (2M)
      1B+           -> N billion / N trillion (lowercase)

    Year exception: a bare 4-digit DIGIT literal in 1900-2099 reads as a year and is
    untouched ("back in 2024"). Word-spoken amounts are exempt from the guard.
    """
    def _scale(val):
        if val < 2000:
            return add_thousands(val)
        if val < 1_000_000:
            return f"{_trim(val / 1000)}K"
        if val < 1_000_000_000:
            return f"{_trim(val / 1_000_000)}M"
        if val < 1_000_000_000_000:
            return f"{_trim(val / 1_000_000_000)} billion"
        return f"{_trim(val / 1_000_000_000_000)} trillion"

    for tok in tokens:
        if tok.locked:
            continue
        val = parse_int_token(tok.text)
        if val is None or val < 1000:
            # EMBEDDED comma-number inside a GLUED multi-word token (Groq writes
            # enumerations as one word) — same fix as apply_money Pass D, for the
            # non-money case ("300,000 customers" glued). "$"-amounts were already
            # handled by the money pass; the lookbehind skips them.
            if re.search(r"(?<![$\d.])\d{1,3}(?:,\d{3})+(?!\d)", tok.text):
                tok.text = re.sub(
                    r"(?<![$\d.])(\d{1,3}(?:,\d{3})+)(?!\d)",
                    lambda m: _scale(int(m.group(1).replace(",", ""))), tok.text)
            continue
        # Year guard applies ONLY to a bare 4-digit digit literal (not spoken words).
        if not tok.spoken and re.fullmatch(r"\d{4}", tok.text) and 1900 <= val <= 2099:
            continue
        tok.text = _scale(val)
        tok.locked = True
    return tokens


# Back-compat alias (pre-v2 name).
apply_thousands = apply_large_numbers


# ---------------------------------------------------------------------------
# Rule 8 (impl): Capitalization
# ---------------------------------------------------------------------------

I_FORMS = {"i", "i'm", "i'll", "i'd", "i've"}


def apply_capitalization(tokens):
    for tok in tokens:
        if tok.locked:
            continue
        core = tok.text
        if core == "":
            continue
        w = lc(core)

        # "I" forms
        if w in I_FORMS:
            tok.text = _cap_i_form(w)
            continue
        # lowercase-locked abbreviations
        if w in LOWER_ABBREV:
            tok.text = w  # keep as-is lowercase
            continue
        # acronyms / proper words already correct stay (likely locked, but safety)
        if core in ACRONYMS or core in PROPER_WORDS:
            continue
        if core.upper() == core and len(core) > 1 and core.isalpha() and core in ACRONYMS:
            continue
        # v2 Rule 9(a): any token ALREADY in ALL-CAPS (2+ letters, optional plural/
        # possessive s) is preserved as-is — AC, VIP, VIPs, CEO's, TV, DM, USA.
        # Prevents sentence-start lowercasing from turning "AC" into "ac".
        if re.fullmatch(r"[A-Z]{2,}(?:['’]?s)?", core):
            continue
        # v2: a K/M-scaled number ("2M", "250K" — Rule 8 output or ASR shorthand) keeps
        # its capital suffix; default-lowercasing would corrupt it to "2m".
        if re.fullmatch(r"\d+(?:\.\d+)?[KM]", core):
            continue
        # case-insensitive proper-noun lookup: "elon" -> "Elon", "vegas" -> "Vegas", etc.
        canon = _PROPER_LOWER.get(w)
        if canon:
            tok.text = canon
            continue
        # possessive of a proper noun: "beast's"->"Beast's", "elon's"->"Elon's" (the bare lookup misses the 's)
        if (w.endswith("'s") or w.endswith("’s")) and _PROPER_LOWER.get(w[:-2]):
            tok.text = _PROPER_LOWER[w[:-2]] + "'s"
            continue
        # MULTI-PART proper tokens: Groq (and the corrections phrase-merge) emit a SINGLE token
        # spanning a multi-word name ("Roy Sutherland") or a hyphen compound ("IRL-based"). The
        # per-token lookups above can't match those, so we'd lowercase a real name. Split on
        # space/hyphen (keeping separators), recapitalize any subword that is a known proper noun /
        # acronym / "I"-form, and rejoin. Only rewrite if at least one subword hit (so ordinary
        # multi-word tokens fall through to default-lowercase and aren't spuriously Title-cased).
        if (" " in core) or ("-" in core):
            import re as _re
            _hit = False
            _parts = _re.split(r"([ \-])", core)
            for _i, _p in enumerate(_parts):
                if _p in (" ", "-") or _p == "":
                    continue
                # strip surrounding punctuation for the lookup ("Mr." -> "mr"), reattach after
                _m = _re.match(r"^(\W*)(.*?)(\W*)$", _p)
                _pre, _mid, _post = _m.group(1), _m.group(2), _m.group(3)
                _pw = lc(_mid)
                _pc = _PROPER_LOWER.get(_pw)
                if _pc:
                    _parts[_i] = _pre + _pc + _post; _hit = True
                elif _pw in I_FORMS:
                    _parts[_i] = _pre + _cap_i_form(_pw) + _post; _hit = True
                elif any(c.isdigit() for c in _p):
                    pass  # digit-bearing segment ("$200K,") — never lowercase the suffix
                else:
                    _parts[_i] = _p.lower()
            if _hit:
                tok.text = "".join(_parts)
                continue
        # default lowercase — but a digit-bearing segment (money/scaled numbers like
        # "$200K, $300K" glued into one Groq token) keeps its case (K/M/X suffixes).
        if any(c.isdigit() for c in core):
            tok.text = " ".join(w if any(c.isdigit() for c in w) else w.lower()
                                for w in core.split(" "))
        else:
            tok.text = core.lower()
    return tokens


def _cap_i_form(w):
    if w == "i":
        return "I"
    # i'm -> I'm
    return "I" + w[1:]


# ---------------------------------------------------------------------------
# Rule 9 (impl): Punctuation cleanup
# ---------------------------------------------------------------------------

def apply_punctuation(tokens):
    for tok in tokens:
        # Clean lead/trail: drop commas and periods (with exceptions handled by being
        # inside number/abbrev/domain — those live INSIDE the core, not in trail).
        # Keep ? and ! in trail; keep apostrophes (they're inside cores).
        # Drop stray leading quotes/parens too (not in spec keep-list).
        new_trail = ""
        for ch in tok.trail:
            if ch in "?!":
                new_trail += ch
            # commas, periods dropped
        tok.trail = new_trail
        # leading punctuation: drop quotes/parens (not in keep-list)
        tok.lead = ""
        # Internal commas/periods are preserved (they're inside number/abbrev/domain
        # cores which were locked or are legitimate). We do NOT strip those.
    return tokens


# ---------------------------------------------------------------------------
# Reassembly
# ---------------------------------------------------------------------------

def reassemble(tokens):
    parts = []
    for idx, tok in enumerate(tokens):
        piece = tok.lead + tok.text + tok.trail
        if piece == "":
            continue
        if idx == 0:
            parts.append(piece)
        else:
            parts.append(" " + piece)
    return "".join(parts).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_caption_text(text: str) -> str:
    if text is None:
        return ""
    if text.strip() == "":
        return ""
    tokens = tokenize(text)
    tokens = apply_fragments(tokens)           # Step 0a: dangling dashes / half-words (v2)
    tokens = apply_misspellings(tokens)        # Step 0: STT error correction
    tokens = apply_dictionary(tokens)          # Rule 9 (dict) FIRST
    tokens = apply_number_words(tokens)        # Rule 3
    tokens = apply_one_vs_1(tokens)            # Rule 4 (the "one" decision)
    tokens = apply_ordinals(tokens)            # Rule 4b (ordinals, v2)
    tokens = apply_listicle_sequence(tokens)   # Rule 5 (listicle/sequence)
    tokens = apply_money(tokens)               # Rule 6 (money)
    tokens = apply_symbols_multipliers(tokens) # Rule 7 (symbols/multiplier/plus/ranges)
    tokens = apply_large_numbers(tokens)       # Rule 8 (large non-money scaling, v2)
    tokens = apply_capitalization(tokens)      # Rule 1 (capitalization)
    tokens = apply_punctuation(tokens)         # Rule 2 (punctuation cleanup)
    return reassemble(tokens)


def format_words(words):
    """Apply Oliver's caption-text rules to a word-timestamp list, preserving timing.

    words: list of {"word","start","end", ...}. Returns a NEW list of
    {"word","start","end"} with the SAME rule sequence as format_caption_text applied,
    where merged tokens (number words, money phrases, %/X/$ folds, dictionary phrases)
    carry the start of their earliest source word and the end of their latest source word.
    Tokens that drop to empty text are removed. Never returns None timings, never crashes.
    """
    if not words:
        return []

    # Build one Token per input word, peeling lead/trail exactly like tokenize does, and
    # stamping src=[i] so provenance flows through every rule.
    tokens = []
    for i, w in enumerate(words):
        raw = (w.get("word") or "")
        core, lead, trail = _peel_token(raw)
        t = Token(core, lead=lead, trail=trail, space_before=(i != 0), src=[i])
        tokens.append(t)

    # SAME rule sequence as format_caption_text.
    tokens = apply_fragments(tokens)           # Step 0a: dangling dashes / half-words (v2)
    tokens = apply_misspellings(tokens)        # Step 0: STT error correction
    tokens = apply_dictionary(tokens)
    tokens = apply_number_words(tokens)
    tokens = apply_one_vs_1(tokens)
    tokens = apply_ordinals(tokens)
    tokens = apply_listicle_sequence(tokens)
    tokens = apply_money(tokens)
    tokens = apply_symbols_multipliers(tokens)
    tokens = apply_large_numbers(tokens)
    tokens = apply_capitalization(tokens)
    tokens = apply_punctuation(tokens)

    n_in = len(words)
    result = []
    prev_end = None
    for tok in tokens:
        text = tok.lead + tok.text + tok.trail
        if text == "":
            continue
        src = getattr(tok, "src", None) or []
        if src:
            lo = min(src)
            hi = max(src)
            start = words[lo].get("start")
            end = words[hi].get("end")
        else:
            # No provenance: fall back to nearest-neighbor timing so we never emit None.
            start = prev_end
            end = None
        if start is None:
            start = prev_end if prev_end is not None else (
                words[0].get("start", 0.0) if n_in else 0.0)
        if end is None:
            # carry the start of the next input word (or nudge past start).
            end = (words[min(hi + 1, n_in - 1)].get("start") if src and hi + 1 < n_in else None)
            if end is None or end <= start:
                end = start + 0.01
        # ALWAYS carry the boundary flag, including when it is False. Omitting it
        # on a false made "the normalizer said no boundary" indistinguishable from
        # "nothing normalized this", and resolve_cards' oliver_v2 contract check
        # keys off exactly that difference -- a clip cut mid-sentence (no .?! on
        # any word) would otherwise be rejected as un-normalized after normalizing.
        item = {"word": text, "start": start, "end": end, "sentence_end": False}
        if src:
            raw_tail = str(words[hi].get("word") or "").strip()
            # Visible periods/commas are intentionally removed by the house style,
            # but their semantic boundary must survive for the downstream chunker.
            # Preserve an existing flag on idempotent re-entry as well as punctuation
            # observed on the last source word consumed by a merged token.
            if (words[hi].get("sentence_end") is True
                    or re.search(r'[.?!]["\'”’)]*$', raw_tail)):
                item["sentence_end"] = True
            if (words[hi].get("comma_end") is True
                    or re.search(r',["\'”’)]*$', raw_tail)):
                item["comma_end"] = True
        result.append(item)
        prev_end = end
    return result


def main():
    # --words mode: read a words-JSON, apply format_words, write a words-JSON.
    if len(sys.argv) > 1 and sys.argv[1] == "--words":
        import json
        inp_path = sys.argv[2]
        out_path = sys.argv[3]
        with open(inp_path) as f:
            d = json.load(f)
        words = d.get("words", d) if isinstance(d, dict) else d
        formatted = format_words(words)
        with open(out_path, "w") as f:
            json.dump({"words": formatted}, f, indent=2)
        return
    # default: stdin text mode.
    data = sys.stdin.read()
    sys.stdout.write(format_caption_text(data))


if __name__ == "__main__":
    main()
