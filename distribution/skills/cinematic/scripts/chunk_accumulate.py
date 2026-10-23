#!/usr/bin/env python3
"""chunk_accumulate.py — build ACCUMULATING PHRASE blocks (the ElitexVision structure).

  python3 chunk_accumulate.py            # reads cut/timeline_words.json, writes generated_groups.py

🛑 THE DIFFERENCE FROM `chunk_captions.py`:
that one emits independent cues that REPLACE each other. This one emits **phrases that BUILD** —
observed frame-by-frame on his reels:

    YOU WANT  ->  YOU WANT TO BE  ->  YOU WANT TO BE / RICH   ->  (whole phrase clears)

A group of words lands, the next group lands NEXT TO it, and when the line is full the new group
drops to a line BELOW while the earlier line stays on screen. The whole phrase clears at once.
That is what makes his captions read as one sentence landing rather than as a ticker.

The rendering machinery needs no change: a PHRASE becomes the block, and each word's item simply
runs from its own onset to the PHRASE end instead of the cue end. `render(block, only=k)` already
positions word k inside a multi-line block.

⚠️ RETARGET `EMPH_PHRASES` / `EMPH` per clip — the only clip-specific lines here.
"""
import json, os, re, sys

D = os.path.dirname(os.path.abspath(__file__))
W = json.load(open(f"{D}/cut/timeline_words.json"))

EMPH_PHRASES = [("yours", "or", "theirs"), ("smaller", "dreams")]
EMPH = {"die", "bigger"}
SERIF = {"and","but","so","because","than","the","a","in","to","of","that","is","how","you"}
# A phrase should end on a THOUGHT, not on a word count. These open a new clause, so a phrase
# closes BEFORE them once it is long enough to stand on its own. Without this the chunker split
# "make sure that the person who is dreaming" mid-thought purely because it hit the word cap.
# "you" earns its place here: on an ANAPHORA run ("you don't have the money, you don't have the
# skill, you don't have the connections") the repeated subject IS the unit boundary. Without it the
# chunker split mid-unit — "money you / don't have / the skill" — which reads as a ticker.
CLAUSE_OPEN = {"and","but","so","because","that","which","when","if","then","for","than","who",
               "have","has","want","just","you"}
MIN_PHRASE  = 4   # 3 let a bare connective ('as long as') satisfy the clause-close
                  # test and ship as its own 0.28s cue — under the 0.35s read floor.

# phrase shape — measured off his reels
WORDS_PER_LINE = 2     # he splits "about two words, sometimes one or three"
MAX_LINES      = 3     # a phrase wraps to at most 3 lines before it must clear
MAX_WORDS      = 6     # and never carries more than this many words


# 🛑 CAPTIONS ARE SELECTIVE, NOT A TRANSCRIPT (measured on DbzAXF5BqEw: he speaks "the norm" and
# never captions it). Natural speech carries stutters — "the hardest, the hardest loss", "the, the
# boy" — which are fine to HEAR but read as sloppy on screen. Drop them from the caption only; the
# audio stays untouched, so the cut keeps its natural delivery.
# Each group therefore records `keep` — the indices (relative to i0) of the words actually shown —
# so gen_captions can time word k from the RIGHT source word instead of assuming k-th shown ==
# k-th spoken. Without that map every drop shifts the rest of the phrase early.
FILLER = {"i mean", "you know", "sort of", "kind of",
          # attribution fillers: audible and natural to HEAR, sloppy to READ, and the "he"
          # is usually an unbound pronoun on a clip that never names the source.
          "he's like", "she's like", "they're like", "i'm like"}
# A single-word tic is only a tic when it OPENS a phrase (the previous word ended a sentence).
# "it's like a fallacy" keeps its "like"; "stranger. Like as long as" drops it. The AUDIO is
# untouched either way — the delivery stays natural, the caption stops reading sloppy.
SENTENCE_INITIAL_FILLER = {"like", "so", "and", "yeah", "okay", "right"}

def drop_noise(words):
    """words = [(idx, text)]. Returns the same list minus immediate repeats and filler."""
    out = []
    i = 0
    while i < len(words):
        w = words[i][1].lower().strip(".,?!")
        two = (w + " " + words[i+1][1].lower().strip(".,?!")) if i+1 < len(words) else ""
        if two in FILLER:
            i += 2; continue
        if out and out[-1][1].lower().strip(".,?!") == w and w not in ("that","had"):
            i += 1; continue            # immediate stutter repeat
        if w in SENTENCE_INITIAL_FILLER and (not out or re.search(r"[.?!]$", out[-1][1])):
            i += 1; continue            # phrase-opening verbal tic
        out.append(words[i]); i += 1
    return out

def clean(w): return re.sub(r"[^A-Za-z0-9'$%.,?!-]", "", w)
def show(w):  return re.sub(r"[.,?!;:]+", "", w)          # NO PUNCTUATION ON CAPTIONS. EVER.


def style_for(bare, is_beat):
    if is_beat:            return "peak"
    if bare in SERIF:      return "base"
    return "strong"


def main():
    n = len(W)
    words = [(i, clean(W[i]["word"])) for i in range(n) if clean(W[i]["word"])]
    words = drop_noise(words)
    phrases, cur = [], []

    def beat_at(idx):
        """multi-word beat starting at position idx in `words`"""
        for ph in EMPH_PHRASES:
            got = []
            for k, want in enumerate(ph):
                if idx + k >= len(words): got = []; break
                if words[idx + k][1].lower().strip(".,?!") != want: got = []; break
                got.append(words[idx + k])
            if got: return got
        return None

    i = 0
    while i < len(words):
        b = beat_at(i)
        if b and cur and len(cur) + len(b) > MAX_WORDS:
            phrases.append(cur); cur = []
        take = b if b else [words[i]]
        cur.extend(take)
        i += len(take)
        last = take[-1][1]
        # a phrase CLOSES on sentence punctuation, on a beat, or when it is full
        nxt = words[i][1].lower().strip(".,?!") if i < len(words) else ""
        closes = (bool(re.search(r"[.?!]$", last)) or bool(b)
                  or len(cur) >= MAX_WORDS or len(cur) >= WORDS_PER_LINE * MAX_LINES
                  or (nxt in CLAUSE_OPEN and len(cur) >= MIN_PHRASE))
        if closes:
            phrases.append(cur); cur = []
    if cur: phrases.append(cur)

    groups = []
    for ph in phrases:
        beats = set()
        for j, (_, w) in enumerate(ph):
            if w.lower().strip(".,?!") in EMPH: beats.add(j)
        for pe in EMPH_PHRASES:
            for j in range(len(ph) - len(pe) + 1):
                if tuple(ph[j + k][1].lower().strip(".,?!") for k in range(len(pe))) == pe:
                    beats.update(range(j, j + len(pe)))
        lines, buf = [], []
        for j, (_, w) in enumerate(ph):
            st = style_for(w.lower().strip(".,?!"), j in beats)
            txt = show(w).upper() if j in beats else show(w)
            buf.append((txt, st))
            if len(buf) >= WORDS_PER_LINE:
                lines.append(merge(buf)); buf = []
        if buf: lines.append(merge(buf))
        # 🛑 THE TWO-LINE LOCKUP (measured 2.24x, DbzAXF5BqEw). When a phrase lands as exactly two
        # lines and the FIRST carries no beat word, demote it to the small `lead` size: lead-in
        # words small on top, payload big below -- "on the / freeway". Only fires when line 1 is
        # pure connective tissue, so a beat word is never shrunk.
        if len(lines) == 2 and all(st not in ("emph", "peak") for _, st in lines[0]):
            lines[0] = [(t, "lead") for t, _ in lines[0]]
        groups.append(dict(i0=ph[0][0], i1=ph[-1][0], lines=lines, cue_scale=1.0,
                           keep=[idx - ph[0][0] for idx, _ in ph]))

    out = ["# AUTO-GENERATED by chunk_accumulate.py — ACCUMULATING phrases (words persist to the",
           "# PHRASE end, not the cue end). Each group is one phrase; its lines build up on screen.",
           "GROUPS = ["]
    for g in groups:
        out.append("        dict(i0=%d, i1=%d, lines=%r, cue_scale=%r, keep=%r)," % (g["i0"], g["i1"], g["lines"], g["cue_scale"], g["keep"]))
    out.append("]")
    open(f"{D}/generated_groups.py", "w").write("\n".join(out) + "\n")

    wl = sum(len(g["lines"]) for g in groups)
    print(f"{len(groups)} PHRASES from {len(words)} words  "
          f"(avg {len(words)/len(groups):.1f} words/phrase, {wl/len(groups):.1f} lines/phrase)")
    for g in groups[:10]:
        print("    " + "  /  ".join(" ".join(t for t, _ in l) for l in g["lines"]))


def merge(buf):
    """collapse neighbouring same-style words so tracking maths is unchanged"""
    m = []
    for t, st in buf:
        if m and m[-1][1] == st: m[-1] = (m[-1][0] + " " + t, st)
        else: m.append((t, st))
    return m


if __name__ == "__main__":
    main()
