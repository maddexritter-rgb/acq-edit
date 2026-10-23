#!/usr/bin/env python3
"""Spice transcript normalization (runs AFTER normalize_simple) — LOCKED caption-text SOP.

SOP subtitle rules (Maddex SOP, baked 2026-06-04 — DO NOT regress these):
  LOWERCASE        : everything except proper nouns + I-forms (I, I'm, I'd, I've, I'll). (normalize_simple)
  SINGLE LINE      : captions are single-line by default (chunker: <=18 chars AND <=3 words). A 2nd
                     line / "(parenthetical explainer)" is a deliberate exception, never the default.
  TIME UNITS       : "<number> minutes/years/..." -> "<digit> min/yrs/..." merged into ONE token.
  ET CETERA        : "et cetera"/"etcetera" -> "etc."
  MONEY + SYMBOLS  : (the rules I previously missed — now automatic)
    * "$" PREFIX is ALWAYS kept on money numbers ($1, $2.5K, $600K, $3M).
    * SYMBOLS not words:  "<n> dollars" -> "$<n>",  "<n> percent|percentage(s)" -> "<n>%".
    * MAGNITUDE merges into the number:  "$<n> thousand|million|billion" -> "$<n>K|M|B"
      ("$46.2 million" -> "$46.2M", "$17 million" -> "$17M"); "a|one million [dollars]" -> "$1M".
    * ABBREVIATE money (>= $10,000):  $20,000 -> $20K, $50,000 -> $50K, $100,000 -> $100K,
      $250,000 -> $250K, $1,200,000 -> $1.2M, $20,000,000 -> $20M, $3,000,000,000 -> $3B.
      Below $10,000 is left as-is ($1, $190, $1,600, $9,500 all fine).  (threshold $100K->$10K, 2026-06-18)
  PROPER NOUNS the base normalizer misses.
Numbers stay WHITE (the director handles color; money is NEVER yellow). Money/unit tokens are emitted
as ONE token so the number never splits from its unit/magnitude across caption lines.
Usage: spice_normalize.py <in.json> <out.json>
"""
import sys, json, re
from pathlib import Path

NUMWORD = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7",
           "eight":"8","nine":"9","ten":"10","eleven":"11","twelve":"12","thirteen":"13","fourteen":"14",
           "fifteen":"15","sixteen":"16","seventeen":"17","eighteen":"18","nineteen":"19","twenty":"20",
           "thirty":"30","forty":"40","fifty":"50","sixty":"60","seventy":"70","eighty":"80","ninety":"90"}
# NUMERALS over spelled-out numbers in captions (Maddex 2026-06-22, StageQA client note: "instead of
# spelling out the numbers it should be the actual number" — caption said "the three core"/"third kind of",
# client wanted "the 3 core"/"3rd kind of"). Converts STANDALONE cardinals >=2 and ordinals 3rd..10th.
# GUARDS: never "one" (pronoun: "no one"/"one of" — see feedback_caption_one_pronoun); skip "first"/"second"
# (idioms "first of all" / "a second"). Money/time/multiplier/rank constructs are consumed earlier in the loop,
# so anything reaching the conversion point is a truly standalone number-word.
CARD2PLUS = {k: v for k, v in NUMWORD.items() if k not in ("zero", "one")}
ORDINAL = {"third":"3rd","fourth":"4th","fifth":"5th","sixth":"6th","seventh":"7th",
           "eighth":"8th","ninth":"9th","tenth":"10th"}
UNIT = {"minute":"min","minutes":"min","hour":"hr","hours":"hr","year":"yrs","years":"yrs",
        "second":"sec","seconds":"sec","week":"wk","weeks":"wks",
        # month/months stay SPELLED OUT — client note 2026-07-30 ("say months instead of mos"),
        # flagged on 3 clips in one review round. Never re-add the mo/mos abbreviation.
        "month":"month","months":"months",
        "day":"day","days":"days"}
MAG = {"thousand":"K","million":"M","billion":"B","trillion":"T"}
# Spoken SLANG money magnitudes: a number right before one of these is compact money with a symbol —
# "100 grand"->$100K, "50 k"->$50K, "3 mil"/"3 m"->$3M.  ⚠️ KEEP IN SYNC with oliver_format.py's apply_money
# (the standalone caption path uses oliver_format; this qa path uses spice_normalize — same SOP, two files).
SLANG_MAG = {"grand":"K", "k":"K", "mil":"M", "m":"M"}
DOLLAR_WORDS = {"dollar","dollars","buck","bucks"}
PERCENT_WORDS = {"percent","percents","percentage","percentages"}
# A magnitude is only MONEY if it isn't counting something else. "nine billion views" is a
# view count, not an amount — but the <number>+<magnitude> rules below used to stamp a "$" on
# every one of them ("$9B views", "$1K times more"). When the token right AFTER the magnitude
# names a countable thing, keep the compact magnitude and DROP the symbol -> "9B views".
# An explicit dollar word ("three million dollars") still wins: it's checked before this.
NON_MONEY_AFTER = {
    "times","x","people","person","humans","views","view","impressions","followers",
    "subscribers","subs","posts","post","videos","video","clips","clip","reels","shorts",
    "customers","clients","users","members","employees","reps","leads","calls","emails",
    "messages","words","units","steps","miles","feet","pounds","lbs","hours","hour",
    "days","day","weeks","week","months","month","years","year","minutes","seconds",
}
# GENERIC, BRAND-AGNOSTIC proper nouns the blanket-lowercase mangles. Only UNAMBIGUOUS names go here
# (a token that is essentially never a common word) so we never over-capitalize ordinary speech. The
# casing internal to the value is authoritative (LinkedIn/YouTube/SaaS keep their internal caps).
# ⚠️ Do NOT add brand/company/guest names specific to one project (e.g. a guest's company) — those are
# AMBIGUOUS and/or private to a job; supply them per-project via ACQ_CAPTION_VOCAB (see below), not here.
# Expanded 2026-06-18 after a StageQA audit found 'harvard/hemingway/linkedin/vegas/costco/armageddon'
# burned lowercase across 6 of 7 clips — the dict was simply too small to catch them.
# 2026-08-01 Frame-review misses (Julian notes on the LIVESTREAM batch) — never again:
#   "legion" = the ASR mishear of "lead gen" in business content; "gorevenue" = fused "goal revenue";
#   Goodyear the company; "Skool of Hard Knocks" phrase-cased WITHOUT touching the Skool platform name.
PROPER = {"apollo":"Apollo","creed":"Creed","bangladesh":"Bangladesh",
          "goodyear":"Goodyear","legion":"lead gen","gorevenue":"goal revenue",
          "down-for-you":"done-for-you",
          "princeton":"Princeton","samaritan":"Samaritan",
          # universities / institutions
          "harvard":"Harvard","stanford":"Stanford","yale":"Yale","mit":"MIT","wharton":"Wharton",
          # places
          "vegas":"Vegas","america":"America","american":"American","europe":"Europe","china":"China",
          "india":"India","texas":"Texas","california":"California","florida":"Florida","york":"York",
          # brands / platforms / tools (internal caps are authoritative)
          "google":"Google","facebook":"Facebook","instagram":"Instagram","tiktok":"TikTok",
          "youtube":"YouTube","linkedin":"LinkedIn","twitter":"Twitter","amazon":"Amazon",
          "apple":"Apple","microsoft":"Microsoft","netflix":"Netflix","spotify":"Spotify",
          "shopify":"Shopify","stripe":"Stripe","salesforce":"Salesforce","hubspot":"HubSpot",
          "costco":"Costco","walmart":"Walmart","starbucks":"Starbucks","tesla":"Tesla",
          "hemingway":"Hemingway","armageddon":"Armageddon","chatgpt":"ChatGPT","openai":"OpenAI",
          # days of week (always proper nouns) — added after L3 StageQA 2026-06-19 burned "mondays/wednesdays" lowercase
          "monday":"Monday","tuesday":"Tuesday","wednesday":"Wednesday","thursday":"Thursday",
          "friday":"Friday","saturday":"Saturday","sunday":"Sunday",
          "mondays":"Mondays","tuesdays":"Tuesdays","wednesdays":"Wednesdays","thursdays":"Thursdays",
          "fridays":"Fridays","saturdays":"Saturdays","sundays":"Sundays"}
# ACRONYMS stay UPPERCASE (the lowercase rule would mangle them — StageQA V3 shipped "not doing the md"
# instead of "MD", 2026-06-17; V-StageQA 2026-06-18 shipped lowercase "hvac"/"ect"). Business-Q&A acronyms;
# matched on the bare standalone word only, so they never fire inside a larger word (e.g. "command" ≠ "md").
# Add new ones here as they come up.
ACRONYM = {"md":"MD","ceo":"CEO","cfo":"CFO","coo":"COO","cto":"CTO","cmo":"CMO","vp":"VP","gp":"GP",
           "roi":"ROI","roas":"ROAS","ltv":"LTV","cac":"CAC","kpi":"KPI","crm":"CRM","seo":"SEO",
           "llc":"LLC","mba":"MBA","dtc":"DTC","b2b":"B2B","b2c":"B2C","saas":"SaaS","ai":"AI","hr":"HR",
           "ceos":"CEOs","kpis":"KPIs","hvac":"HVAC","ect":"ECT","ceo's":"CEO's","sop":"SOP",
           "p&l":"P&L","r&d":"R&D","b2b2c":"B2B2C","api":"API","kpi's":"KPI's"}

# PER-PROJECT vocab (brand-agnostic mechanism): a job can supply its own proper-noun map — guest names,
# company names ("Fluence", "Capital Direct"), product names — without hardcoding any brand into the skill.
# Point ACQ_CAPTION_VOCAB at a JSON file: {"fluence":"Fluence","capital direct":"Capital Direct", ...}.
# Single-token keys merge into PROPER (cased on the bare standalone word); multi-word keys (a phrase with a
# space) are applied as an ordered phrase pass so e.g. "capital direct" -> "Capital Direct" without ever
# capitalizing a bare "capital". Added 2026-06-18 (StageQA: 'fluence'/'capital direct' need per-job casing).
import os as _os
PROPER_PHRASES = {"skool of hard knocks": "School of Hard Knocks",
                  "community on school": "community on Skool"}  # phrase-level so the Skool platform name stays untouched  # {"capital direct": "Capital Direct"} — applied as a phrase pass, longest-first
def _load_project_vocab():
    p = _os.environ.get("ACQ_CAPTION_VOCAB")
    if not p or not _os.path.exists(p): return
    try:
        vocab = json.loads(Path(p).read_text())
    except Exception as e:
        print(f"spice_normalize: WARN could not read ACQ_CAPTION_VOCAB={p}: {e}", file=sys.stderr); return
    for k, v in vocab.items():
        kb = k.lower().strip()
        if " " in kb: PROPER_PHRASES[kb] = v
        else: PROPER[re.sub(r'[^a-z0-9]', '', kb)] = v
    print(f"spice_normalize: loaded {len(vocab)} project proper-nouns from {Path(p).name}", file=sys.stderr)
_load_project_vocab()

# SHARED VOCAB (2026-08-03): one correction file feeds BOTH normalizers so review-note
# fixes can never land in only one path again (the 'legion'/08-01 drift bug).
# New vocab fixes go in vocab/shared_vocab.json — not in the tables above.
def _load_shared_vocab():
    p = Path(__file__).resolve().parent.parent / "vocab" / "shared_vocab.json"
    if not p.exists(): return
    try:
        sv = json.loads(p.read_text())
    except Exception as e:
        print(f"spice_normalize: WARN could not read shared_vocab.json: {e}", file=sys.stderr); return
    # 🛑 GATE (2026-08-27): a common noun here capitalises EVERY generic use. This exact
    # regression ("Gym"/"Launch") shipped 4 review notes before it was caught. Fail loud.
    _never = {w.lower() for w in sv.get("never_proper", [])}
    _bad = sorted({w for w in sv.get("proper_words", []) if w.lower() in _never})
    if _bad:
        raise SystemExit(
            f"spice_normalize: shared_vocab.json proper_words contains common noun(s) {_bad} — "
            "these capitalise every generic use. Put the multi-word brand in phrase_fixes instead.")
    for w in sv.get("proper_words", []):
        PROPER[re.sub(r'[^a-z0-9]', '', w.lower())] = w
    for k, v in {**sv.get("misspellings", {}), **sv.get("phrase_fixes", {})}.items():
        kb = k.lower().strip()
        if " " in kb: PROPER_PHRASES[kb] = v
        else: PROPER[re.sub(r'[^a-z0-9]', '', kb)] = v
_load_shared_vocab()
DOWNCASE = {"may"}  # normalize_simple capitalizes the month "May"; in speech it's usually the verb

def bare(w): return re.sub(r"[^a-z0-9]", "", w.lower())
def tail(w):
    m = re.search(r"[.,?!]+$", w.strip()); return m.group(0) if m else ""

NUM_IN = re.compile(r"(\$?)(\d[\d,]*(?:\.\d+)?)")  # a number, maybe $-prefixed, commas + decimal

def fmt_mant(x):
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s

def abbrev_money(numstr):
    """numstr like '20,000' / '46.2' -> '$<abbrev>' if >= $10,000, else None (leave as-is).
    Lowered $100K->$10K threshold 2026-06-18 (Maddex): compact dollar THOUSANDS too
    ($20,000 -> $20K, $50,000 -> $50K). Sub-$10,000 left as-is to avoid awkward $1.6K-style."""
    try:
        v = float(numstr.replace(",", ""))
    except ValueError:
        return None
    if v >= 1e9: return "$" + fmt_mant(v / 1e9) + "B"
    if v >= 1e6: return "$" + fmt_mant(v / 1e6) + "M"
    if v >= 1e4: return "$" + fmt_mant(v / 1e3) + "K"
    return None

def find_num(tok):
    """Split the FIRST number out of a token: (prefix, dollar_sign, numstr, suffix) or None."""
    m = NUM_IN.search(tok)
    if not m: return None
    return tok[:m.start()], m.group(1), m.group(2), tok[m.end():]

def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    d = json.loads(inp.read_text())
    words = d.get("words", d) if isinstance(d, dict) else d
    res = []
    i = 0
    n = len(words)
    while i < n:
        w = words[i]; raw = w["word"]; b = bare(raw)
        nxt = words[i + 1] if i + 1 < n else None
        nb = bare(nxt["word"]) if nxt else ""
        nn = words[i + 2] if i + 2 < n else None
        nnb = bare(nn["word"]) if nn else ""

        # word-number FRACTION in a money context: "<numword> and a half|quarter <money unit>"
        # -> "$<n.5|n.25><K|M>" ("three and a half mil" -> "$3.5M"). Gated to a money unit so non-money
        # phrases ("three and a half years/hours") are untouched. Mirrors oliver_format.py's money Pass 0.
        if b in NUMWORD and not b.isdigit() and i + 4 < n:
            s1, s2, s3, s4 = (bare(words[i + k]["word"]) for k in range(1, 5))
            _fmag = MAG.get(s4) or SLANG_MAG.get(s4)
            if s1 == "and" and s2 == "a" and s3 in ("half", "quarter") and _fmag:
                frac = "5" if s3 == "half" else "25"
                m = dict(w); m["word"] = f"${NUMWORD[b]}.{frac}{_fmag}{tail(words[i+4]['word'])}"; m["end"] = words[i + 4]["end"]
                res.append(m); i += 5; continue

        # number (digit or number-word, NOT 'a') + TIME unit -> "<digit> <abbrev>"
        if (b.isdigit() or (b in NUMWORD and b not in ("a", "an"))) and nb in UNIT:
            digit = b if b.isdigit() else NUMWORD[b]
            m = dict(w); m["word"] = f"{digit} {UNIT[nb]}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue

        # MULTIPLIER: "<number> times" -> "<digit>X"  ("two times" -> "2X", "10 times" -> "10X")  [reels lesson]
        if (b.isdigit() or (b in NUMWORD and b not in ("a", "an"))) and nb == "times":
            digit = b if b.isdigit() else NUMWORD[b]
            m = dict(w); m["word"] = f"{digit}X{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # lone "10x"/"3x" -> "10X".  Match the RAW token, not bare(), so a thousands
        # separator survives ("1,000x" -> "1,000X", not "1000X").
        _mx = re.fullmatch(r"(\d[\d,]*)x", raw.strip().lower().rstrip(".,?!"))
        if _mx:
            m = dict(w); m["word"] = f"{_mx.group(1)}X{tail(raw)}"; res.append(m); i += 1; continue
        # ORDINAL/RANK: "number <n>" -> "#<n>"  ("number one" -> "#1")  [reels lesson]
        if b == "number" and (nb.isdigit() or (nb in NUMWORD and nb not in ("a", "an"))):
            digit = nb if nb.isdigit() else NUMWORD[nb]
            m = dict(w); m["word"] = f"#{digit}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue

        fn = find_num(raw)
        # "<word-number> million|thousand|billion [dollars]" -> "$<n>K|M|B"
        # ("three million" -> "$3M", "five thousand dollars" -> "$5K")  [2026-06-14: was
        # only catching digit forms via fn; word forms were leaving "three million"
        # un-normalized → caption_lint spelled-number error.]
        if b in NUMWORD and b not in ("a", "an", "one") and (nb in MAG or nb in SLANG_MAG):
            digit = NUMWORD[b]
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            mag = MAG.get(nb) or SLANG_MAG.get(nb)
            _sym = "" if (consume == 2 and nnb in NON_MONEY_AFTER) else "$"
            m = dict(w); m["word"] = f"{_sym}{digit}{mag}{tail(tnode['word'])}"; m["end"] = end
            res.append(m); i += consume; continue
        # "a|one million [dollars]" -> "$1M"   (idiomatic 'a million' = 1)
        if b in ("a", "an", "one") and (nb in MAG or nb in SLANG_MAG):
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            _sym = "" if (consume == 2 and nnb in NON_MONEY_AFTER) else "$"
            m = dict(w); m["word"] = _sym + "1" + (MAG.get(nb) or SLANG_MAG.get(nb)) + tail(tnode["word"]); m["end"] = end
            res.append(m); i += consume; continue
        # "$<n>"/<n> + magnitude [+ dollars] -> "$<n>K|M|B"  (thousand/million/billion + slang grand/k/mil/m)
        _mag = MAG.get(nb) or SLANG_MAG.get(nb)
        if fn and _mag:
            prefix, _dol, numstr, _suf = fn
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            _sym = "" if (consume == 2 and nnb in NON_MONEY_AFTER and not _dol) else "$"
            m = dict(w); m["word"] = f"{prefix}{_sym}{numstr}{_mag}{tail(tnode['word'])}"; m["end"] = end
            res.append(m); i += consume; continue
        # "<n> dollars" -> "$<n>"
        if fn and nb in DOLLAR_WORDS:
            prefix, _dol, numstr, _suf = fn
            m = dict(w); m["word"] = f"{prefix}${numstr}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # "<n> percent" -> "<n>%"
        if fn and nb in PERCENT_WORDS:
            prefix, _dol, numstr, _suf = fn
            m = dict(w); m["word"] = f"{prefix}{numstr}%{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # standalone $ amount >= $100,000 -> abbreviate in place
        if fn and fn[1] == "$":
            prefix, _dol, numstr, suf = fn
            ab = abbrev_money(numstr)
            if ab:
                m = dict(w); m["word"] = prefix + ab + suf
                res.append(m); i += 1; continue

        # standalone CARDINAL (>=2) / ORDINAL (3rd..10th) -> numeral (Maddex 2026-06-22). By here all
        # money/time/multiplier/rank constructs have already consumed their tokens and continued, so a
        # remaining number-word is standalone: "the three core"->"the 3 core", "third kind of"->"3rd kind of".
        if b in CARD2PLUS:
            w = dict(w); w["word"] = CARD2PLUS[b] + tail(raw); res.append(w); i += 1; continue
        if b in ORDINAL:
            w = dict(w); w["word"] = ORDINAL[b] + tail(raw); res.append(w); i += 1; continue

        # "et cetera" -> "etc."
        if b == "et" and nb == "cetera":
            m = dict(w); m["word"] = "etc."; m["end"] = nxt["end"]; res.append(m); i += 2; continue
        if b == "etcetera":
            w = dict(w); w["word"] = "etc." + tail(raw)
        # proper-noun capitalization / acronym uppercasing / forced downcase
        if b in PROPER:
            w = dict(w); w["word"] = PROPER[b] + tail(raw)
        elif b in ACRONYM:
            w = dict(w); w["word"] = ACRONYM[b] + tail(raw)
        elif "-" in raw and bare(raw.split("-", 1)[0]) in (PROPER.keys() | ACRONYM.keys()):
            # hyphenated proper-noun/acronym compound: "costco-like"->"Costco-like", "hvac-related"->"HVAC-related"
            head = raw.split("-", 1)[0]; hb = bare(head)
            cased = PROPER.get(hb) or ACRONYM.get(hb)
            w = dict(w); w["word"] = cased + raw[len(head):]
        elif b in DOWNCASE and raw != raw.lower():
            w = dict(w); w["word"] = raw.lower()
        res.append(w); i += 1

    # PHRASE pass for multi-word project proper-nouns ("capital direct" -> "Capital Direct"), longest-first
    # so a longer phrase wins over a contained shorter one. Casing is applied across the run of tokens;
    # trailing punctuation on the last token is preserved.
    if PROPER_PHRASES:
        for phrase in sorted(PROPER_PHRASES, key=lambda s: -len(s.split())):
            parts = phrase.split(); L = len(parts); cased = PROPER_PHRASES[phrase].split()
            j = 0
            while j + L <= len(res):
                if all(bare(res[j + k]["word"]) == parts[k] for k in range(L)):
                    for k in range(L):
                        repl = cased[k] if k < len(cased) else res[j + k]["word"]
                        res[j + k] = dict(res[j + k]); res[j + k]["word"] = repl + (tail(res[j + k]["word"]) if k == L - 1 else "")
                    j += L
                else:
                    j += 1

    if isinstance(d, dict):
        d["words"] = res; out.write_text(json.dumps(d, indent=2))
    else:
        out.write_text(json.dumps(res, indent=2))
    print(f"spice_normalize: {len(words)} -> {len(res)} tokens -> {out.name}")

if __name__ == "__main__":
    main()
