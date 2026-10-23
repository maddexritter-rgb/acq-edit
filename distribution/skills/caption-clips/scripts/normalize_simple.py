#!/usr/bin/env python3
import json, sys, re, os as _os
from pathlib import Path
ACRONYMS = {"ai","ml","ceo","cfo","cto","coo","ev","ip","kpi","mvp","ui","ux","usa",
            "uk","fbi","cia","nasa","fda","irs","gdp","b2b","b2c","saas","cnn","bbc",
            "dtc","roi","fyi","tldr","faq","api","sdk","cli","gpu","cpu","w-2","w2",
            "fl","ny","la","sf","nyc","tx","ca","hr","pr","crm"}
PROPER_NOUNS = {
    "alex","leila","amir","hormozi","trump","biden","jordan","kobe","lebron",
    "shaq","christmas","easter","halloween","monday","tuesday","wednesday",
    "thursday","friday","saturday","sunday","january","february",
    "june","july","september","october","november","december",
    "florida","texas","california","new york","los angeles","america","american",
    "miami","tampa","orlando","jacksonville","pembroke","pines",
    "amazon","google","apple","instagram","tiktok","youtube","facebook","meta",
    "colette","valdes","jovanny","giovanni","mendoza","layla","amanda","nicklison",
    "europe",
}
# Months whose lowercase spelling is FAR more often a common word in Alex/Hormozi
# content than a calendar reference: the modal verb "may", the verb "march", the
# adjective "august", the name "april". These must NOT auto-capitalize like the other
# proper nouns — capitalize them as a month ONLY in a date context (see _month_context).
# The unambiguous months (january, february, june, july, september...) stay in
# PROPER_NOUNS above and always capitalize.
# Added 2026-06-04 after "that they may be valid" rendered "...they May be valid" on
# ALEX_DTC_250505_ExcusesGuaranteeFailure (had to hand-fix the .ass).
AMBIGUOUS_MONTHS = {"may", "march", "april", "august"}
# Prepositions that introduce a month but never an auxiliary/verb reading of the word
# ("in May", "by August", "from March"). Deliberately excludes "to" (collides with the
# infinitive "to march") and bare determiners/pronouns ("this may be", "they may").
DATE_PREPS = {"in", "on", "by", "from", "since", "until", "till", "through", "during", "of"}
# A following token that marks a date: an ordinal day ("5th", "23rd") or a 4-digit year
# ("2025"). A bare 1-2 digit number is intentionally NOT enough, so "march 10 miles"
# stays the verb.
_NEXT_DATE_RE = re.compile(r"^(\d+(?:st|nd|rd|th)|\d{4})$", re.IGNORECASE)
_CORE_RE = re.compile(r"^[\$]?([\w'\-]+)")
I_FORMS = {"i","i'm","i'll","i've","i'd"}

def _token_core(tok):
    """Lowercased core of a neighbouring token (strips a leading $ and trailing punctuation)."""
    if not tok:
        return ""
    m = _CORE_RE.match(tok)
    return m.group(1).lower() if m else ""

def _month_context(prev_token, next_token):
    """True when an ambiguous month word sits in a date context: a date preposition in
    front ("in May", "by August") OR an ordinal day / 4-digit year behind ("May 5th",
    "May 2025"). Conservative on purpose — when there is no date signal it returns False
    so the word keeps its common-word (lowercase) reading."""
    if _token_core(prev_token) in DATE_PREPS:
        return True
    return bool(_NEXT_DATE_RE.match(_token_core(next_token)))

def normalize_word(w_token, prev_token=None, next_token=None):
    # MERGED ASR TOKENS. transcribe_lv3 sometimes emits several words as ONE token, e.g.
    # the literal token "course, $99" (space AND comma inside). Every downstream layer
    # assumes one word per token and silently skips it: the regex below does not match a
    # token containing a space and returns early; generate_spice.disp() only rstrips a
    # TERMINAL comma, and this one is internal; the corrections matcher ignores any token
    # whose bare form has a space. That is how a single comma reached the screen while no
    # other caption had one. Strip only COMMA-SPACE, which is punctuation — a thousands
    # separator ("46,000") has no space and is left alone.
    if _os.environ.get("ACQ_STRIP_CAPTION_COMMAS") == "1" and ", " in w_token:
        w_token = w_token.replace(", ", " ")
    m = re.match(r"^([\$]?[\w'\-]+)([.,!?]*)$", w_token)
    if not m: return w_token
    core, trail = m.group(1), m.group(2)
    # Spice captions are 2-3 word chunks; a comma inside one is ASR punctuation noise, not
    # style. It survived because every branch below re-appends `trail` untouched, and the
    # corrections map cannot remove it either (the matcher strips punctuation to compare,
    # then puts it back). Maddex flagged a burned "course, $99" directly. Opt-in via
    # ACQ_STRIP_CAPTION_COMMAS so other skills' renders are unaffected. Keeps . ? !
    if trail and _os.environ.get("ACQ_STRIP_CAPTION_COMMAS") == "1":
        trail = trail.replace(",", "")
    lc = core.lower()
    if lc in I_FORMS:
        if lc == "i": core = "I"
        elif lc == "i'm": core = "I'm"
        elif lc == "i'll": core = "I'll"
        elif lc == "i've": core = "I've"
        elif lc == "i'd": core = "I'd"
        return core + trail
    if lc in ACRONYMS: return lc.upper() + trail
    if lc in AMBIGUOUS_MONTHS:
        if _month_context(prev_token, next_token):
            return core[0].upper() + core[1:].lower() + trail
        return core.lower() + trail
    if lc in PROPER_NOUNS: return core[0].upper() + core[1:].lower() + trail
    if any(c.isdigit() for c in core): return core + trail
    return core.lower() + trail
def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    d = json.loads(inp.read_text())
    words = d.get("words", d) if isinstance(d, dict) else d
    toks = [w["word"] for w in words]  # snapshot originals so context is order-independent
    for i, w in enumerate(words):
        prev_t = toks[i - 1] if i > 0 else None
        next_t = toks[i + 1] if i + 1 < len(toks) else None
        w["word"] = normalize_word(toks[i], prev_t, next_t)
    out.write_text(json.dumps({"words": words} if isinstance(d, dict) else words, indent=2))

def _selftest():
    """`python3 normalize_simple.py --selftest` — guards the may/march fix plus
    regressions on I-forms, acronyms, proper nouns, and the unambiguous months."""
    def run(tokens):
        return [normalize_word(tokens[i],
                               tokens[i - 1] if i > 0 else None,
                               tokens[i + 1] if i + 1 < len(tokens) else None)
                for i in range(len(tokens))]
    cases = [
        # the bug: modal / verb / adjective senses stay lowercase
        (["that", "they", "may", "be", "valid"], ["that", "they", "may", "be", "valid"]),
        (["you", "may", "not", "win"],           ["you", "may", "not", "win"]),
        (["we", "march", "forward"],             ["we", "march", "forward"]),
        (["march", "10", "miles"],               ["march", "10", "miles"]),
        (["an", "august", "body"],               ["an", "august", "body"]),
        # date context -> capitalize as a month
        (["in", "may"],                          ["in", "May"]),
        (["may", "5th", "deadline"],             ["May", "5th", "deadline"]),
        (["on", "march", "3rd"],                 ["on", "March", "3rd"]),
        (["by", "august"],                       ["by", "August"]),
        (["since", "april"],                     ["since", "April"]),
        (["may", "2025", "was", "wild"],         ["May", "2025", "was", "wild"]),
        (["in", "may,", "2025"],                 ["in", "May,", "2025"]),
        # unambiguous months always capitalize (unchanged behaviour)
        (["in", "january"],                      ["in", "January"]),
        (["see", "you", "in", "december"],       ["see", "you", "in", "December"]),
        (["born", "in", "june"],                 ["born", "in", "June"]),
        # regressions: I-forms / acronyms / proper nouns
        (["i", "think", "i'm", "right"],         ["I", "think", "I'm", "right"]),
        (["the", "ceo", "of", "ai"],             ["the", "CEO", "of", "AI"]),
        (["alex", "and", "hormozi"],             ["Alex", "and", "Hormozi"]),
    ]
    failed = 0
    for src, want in cases:
        got = run(src)
        ok = got == want
        if not ok: failed += 1
        line = "PASS" if ok else "FAIL"
        print(f"[{line}] {' '.join(src)}"
              + ("" if ok else f"\n        got:  {' '.join(got)}\n        want: {' '.join(want)}"))
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--selftest", "--test"):
        _selftest()
    else:
        main()
