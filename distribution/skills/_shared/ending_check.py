#!/usr/bin/env python3
"""ending_check.py — THE canonical "did we cut the speaker off / false ending" rule. ONE home,
shared by window_validator (pre-cut), reqc (post-delivery), and build_ad (testimonial ads).

A clip MUST end on a COMPLETE thought. It is a FALSE ENDING (cut-off sentence) when, in the SOURCE,
the same speaker keeps going on the same clause after our end point — i.e. the last kept word is NOT
sentence-terminal AND the next source word continues the clause (lowercase, no new turn). Also a
false ending if the clip ends ON a word that NEVER ends a sentence (and/but/the/a/to/of/which/…).

Hard gate for ALL content domains (Q&A, workshops/ads, listicle, podcast, monologue). Origin:
a CMO review (2026-06-17): "the AI cuts off the speaker and goes to the end bumper".

⚠️ DESIGN NOTE: prepositions like at/on/by/for/with/in/from/up/out are NOT treated as mid-clause —
they legitimately end a sentence via phrasal verbs ("what we're good at.", "someone to rely on.",
"the problem I showed up for."). Only words that can NEVER end a complete sentence are hard-failed;
prepositions/content-word endings are judged by source continuation. (The "good at" false-positive
was caught on the DirectHomeOffers test, 2026-06-17.)

Two entry points:
  ends_complete(end_word, next_words)  — pre-cut / source-mapped: has the SOURCE words AFTER the end.
  tail_only_verdict(last_words)        — post-delivery fallback: only the delivered clip's own tail
                                          → catches a hard mid-clause ending; ("ok"|"fail"|"unknown").
"""
import re

# words that NEVER end a complete sentence → hard-fail regardless of context (NOT prepositions,
# which can end a phrasal verb). Conjunctions, articles, infinitive 'to', possessives, bare auxiliaries.
HARD_MIDCLAUSE = {
    "and", "but", "or", "so", "because", "the", "a", "an", "to", "of", "that", "which", "as",
    "than", "then", "into", "very", "my", "your", "his", "her", "their", "our", "its",
    "is", "was", "are", "were", "been", "be", "am", "if", "while", "whose",
    # subordinating conjunctions that NEVER end a complete sentence (added 2026-06-17 after the
    # Dominique/ThreeFunctions clip shipped ending on "and until" — the gate returned 'unknown' not
    # 'fail' because "until" was missing). NOTE: "though"/"since" CAN end a sentence colloquially — do NOT add.
    "until", "unless", "whether", "whereas", "although", "nor", "upon",
    # CONTRACTIONS of mid-clause words (added 2026-06-17 after the StageQA/tyler clip shipped ending on
    # a trailing "...a sales motion that's, that's." stammer — the gate had "that" but the captioned/spoken
    # word was the contraction "that's", which expands to "that is" and can NEVER end a sentence. _norm
    # keeps the apostrophe, so both forms are listed). The clean payoff was "...a sales motion." (full stop).
    "that's", "thats", "what's", "whats", "here's", "heres", "there's", "theres",
}
# next-turn markers: if these open the SOURCE words right after our end, the speaker FINISHED and a
# new turn (interviewer / next question) took over → a complete stopping point, not a cut-off.
_INTERVIEWER = re.compile(
    r"\b(how|what|why|describe|tell me|so how|and your|and what|number one takeaway|did you|"
    r"was it|gotcha|awesome|perfect|cool|great|thank|sweet|nice|love it|got it|amazing|"
    r"wonderful|let's|next question|moving on)\b")

def _norm(w):
    return re.sub(r"[^a-z']", "", (w or "").lower())

def _terminal(word):
    return bool(re.search(r"[.!?][\"'\)\]]*\s*$", (word or "").strip()))

def _wtext(w):
    return (w.get("word") if isinstance(w, dict) else w) or ""

def ends_complete(end_word, next_words):
    """PRE-CUT / SOURCE-MAPPED check. end_word = the clip's last kept word (source dict or str).
    next_words = the SOURCE words that come AFTER it (list of dicts/strs; [] if source ended).
    Returns (ok: bool, reason: str)."""
    ew = _wtext(end_word).strip(); cword = _norm(ew)
    if _terminal(ew):
        return True, f"ends on {ew!r} (sentence-terminal)"
    if cword in HARD_MIDCLAUSE:
        return False, f"ends ON mid-clause word {ew!r} — cut-off sentence"
    nxt = next_words or []
    if not nxt:
        return True, f"ends on {ew!r} (source ends here — speaker finished)"
    nxt_txt = " ".join(_wtext(w) for w in nxt[:15])
    iv = bool(_INTERVIEWER.search(nxt_txt.lower())) or "?" in nxt_txt
    nxt0 = _wtext(nxt[0]).strip()
    new_sentence = bool(nxt0) and nxt0[:1].isupper()      # Whisper capitalizes a new sentence start
    if iv or new_sentence:
        return True, f"ends on {ew!r} (new turn / sentence follows — complete)"
    return False, (f"ends on {ew!r} but the SAME speaker continues: …{nxt_txt[:80]!r} — false ending. "
                   f"Extend to the sentence's true end (or pick a self-contained close).")

def tail_only_verdict(last_words):
    """POST-DELIVERY fallback when no source is available — only the delivered clip's own last words
    (with the ASR's punctuation). Cannot see source continuation, so it only catches the
    unambiguous cases. Returns (verdict, reason): 'fail' (hard mid-clause word = definitely cut-off),
    'ok' (sentence-terminal), or 'unknown' (content/preposition word, no terminal punct → needs
    --project/source to confirm)."""
    real = [w for w in (last_words or []) if _norm(_wtext(w))]
    if not real:
        return "unknown", "no words in tail"
    ew = _wtext(real[-1]).strip(); cword = _norm(ew)
    if _terminal(ew):
        return "ok", f"clip ends on {ew!r} (sentence-terminal)"
    if cword in HARD_MIDCLAUSE:
        return "fail", f"clip ends ON mid-clause word {ew!r} — cut-off sentence"
    return "unknown", (f"clip ends on {ew!r} with no terminal punctuation — re-run with --project "
                       f"(source) to confirm it's not a false ending")
