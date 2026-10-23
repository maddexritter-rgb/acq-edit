#!/usr/bin/env python3
"""
test_oliver_format.py — every worked input->output example from the spec.

Source: caption-clips/references/oliver_caption_formatting_spec.md
Each CASES entry is (input, expected, why/rule). Run directly:
    python3 test_oliver_format.py
Exit code 0 = all pass; nonzero = some fail (failures printed).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oliver_format import format_caption_text, format_words  # noqa: E402


# (input, expected, label)
CASES = [
    # ---------------- Rule 3: number words -> digits ----------------
    ("two", "2", "R3 two->2"),
    ("three", "3", "R3 three->3"),
    ("ten", "10", "R3 ten->10"),
    ("twenty two", "22", "R3 twenty two->22"),
    ("fifty", "50", "R3 fifty->50"),
    ("one hundred", "100", "R3 one hundred->100"),
    ("five hundred", "500", "R3 five hundred->500"),
    ("one thousand", "1,000", "R3/R8 one thousand->1,000 (comma band)"),
    # compound numbers — v2 Rule 8: large non-money numbers use the K/M scale
    ("fifty thousand", "50K", "R3/R8v2 fifty thousand->50K"),
    ("one hundred thousand", "100K", "R3/R8v2 one hundred thousand->100K"),
    ("two million", "2M", "R3/R8v2 two million->2M (isolated: no $)"),
    ("three hundred million", "300M", "R3/R8v2 three hundred million->300M"),

    # v2 R3: "a" as quantity — article DROPPED before a spoken scale number
    ("a thousand", "1,000", "R3v2 a thousand -> 1,000 (article dropped)"),

    # zero exception (non-money keeps word)
    ("zero people", "zero people", "R3 zero people stays"),

    # ---------------- Rule 4: one vs 1 ----------------
    # LOCKED LESSON (2026-06-12, overrides the spec's convert-by-default): "one" stays
    # the WORD unless a POSITIVE signal fires (money word / adjacent number / listicle
    # label). The spec's trigger-word list would re-ship "judgment is 1" / "no 1 will
    # care" — every conversational "one" is overwhelmingly a pronoun/article.
    ("there's only one way", "there's only one way", "R4-LOCKED keep word (no positive signal)"),
    ("just one more rep", "just one more rep", "R4-LOCKED keep word"),
    ("we closed one deal", "we closed one deal", "R4-LOCKED keep word"),
    ("at least one person", "at least one person", "R4-LOCKED keep word"),
    ("if there's one lesson", "if there's one lesson", "R4-LOCKED keep word"),
    ("no one will care", "no one will care", "R4-LOCKED 'no one' (shipped-bug probe)"),
    ("judgment is one", "judgment is one", "R4-LOCKED 'is one' (shipped-bug probe)"),
    # keep "one"
    ("so one thing", "so one thing", "R4 keep one after 'so'"),
    ("one of the biggest mistakes", "one of the biggest mistakes", "R4 keep one (no preceding word)"),
    ("and one day it clicked", "and one day it clicked", "R4 keep one after 'and'"),
    ("another one", "another one", "R4v2 'another one' never 'another 1'"),
    # dictionary-locked one shot
    ("one shot", "one shot", "R9 one shot locked"),
    # positive signal: next word is a money word -> "1"
    ("one grand", "$1,000", "R4 one grand -> $1,000 (money signal)"),

    # ---------------- Rule 5: listicle & sequence ----------------
    ("number two", "#2", "R5 listicle number two->#2"),
    ("number one", "#1", "R5 listicle number one->#1"),
    ("law number 1", "law #1", "R5 listicle law number 1->law #1"),
    ("rule number 2", "rule #2", "R5 listicle rule number 2->rule #2"),
    ("step number 5", "step #5", "R5 listicle step number 5->step #5"),
    ("week number one", "week #1", "R5 listicle wins: week number one->week #1"),
    # sequence hash words
    ("step one", "step #1", "R5 seq step one->step #1"),
    ("tip three", "tip #3", "R5 seq tip three->tip #3"),
    ("reason one", "reason #1", "R5 seq reason one->reason #1"),
    # sequence plain words
    ("day one", "day 1", "R5 seq day one->day 1"),
    ("week one", "week 1", "R5 seq week one->week 1"),
    ("round two", "round 2", "R5 seq round two->round 2"),

    # ---------------- Rule 6: money formatting ----------------
    ("zero dollars", "$0", "R6 zero dollars->$0"),
    ("five hundred dollars", "$500", "R6 five hundred dollars->$500"),
    ("fifty thousand dollars", "$50K", "R6 fifty thousand dollars->$50K"),
    ("two million dollars", "$2M", "R6 two million dollars->$2M"),
    ("one billion dollars", "$1 billion", "R6v2 one billion dollars->$1 billion (lowercase)"),
    ("one trillion dollars", "$1 trillion", "R6v2 one trillion dollars->$1 trillion (lowercase)"),
    # v2: the comma band is ONLY $1,000-$1,999; $2,000+ is $NK
    ("a thousand dollars", "a $1,000", "R6 a thousand dollars (article kept)->a $1,000"),
    ("one thousand dollars", "$1,000", "R6 one thousand dollars->$1,000"),
    ("five thousand dollars", "$5K", "R6v2 five thousand dollars->$5K"),
    ("two thousand dollars", "$2K", "R6v2 two thousand dollars->$2K"),
    ("ten thousand dollars", "$10K", "R6v2 ten thousand dollars->$10K"),
    ("fifteen hundred dollars", "$1,500", "R6v2 fifteen hundred dollars->$1,500 (comma band)"),
    ("thousand dollars", "$1,000", "R6 thousand dollars->$1,000"),
    # standalone money answer in money context (the question supplies the context)
    ("how much do you charge a thousand", "how much do you charge $1,000",
     "R6 standalone money answer w/ 'charge' trigger -> $1,000"),

    # shorthand K
    ("1k", "1k", "R6 idempotency-ish: bare 1k with no dollars stays (no money ctx)"),
    ("$1K", "$1K", "idempotency $1K"),

    # grand (v2 table: $2K+ is $NK)
    ("a grand", "$1,000", "R6 a grand->$1,000"),
    ("one grand", "$1,000", "R6 one grand->$1,000"),
    ("five grand", "$5K", "R6v2 five grand->$5K"),
    ("ten grand", "$10K", "R6v2 ten grand->$10K"),
    ("a hundred grand", "$100K", "R6 a hundred grand->$100K"),
    # v2: "grand" adjective guard — a noun after "grand" keeps the word
    ("a grand opening", "a grand opening", "R6v2 grand+noun stays (adjective)"),
    ("a grand slam offer", "a grand slam offer", "R6v2 grand slam stays"),
    ("a grand total", "a grand total", "R6v2 grand total stays"),
    ("made a grand", "made $1,000", "R6v2 grand standalone converts"),
    ("a grand a month", "$1,000 a month", "R6v2 grand + rate converts"),
    ("a grand in revenue", "$1,000 in revenue", "R6v2 grand + identifier converts"),
    ("500 grand", "$500K", "R6 500 grand->$500K"),
    ("100 grand", "$100K", "R6 100 grand->$100K"),
    ("200 grand", "$200K", "R6 200 grand->$200K"),
    ("100 grand or 200 grand", "$100K or $200K", "R6 two digit-grands in a line"),
    ("1.5 grand", "$1.5K", "R6 decimal grand->$1.5K"),

    # spoken-money SHORTHAND units (k / mil / m) after a clean numeric quantity
    ("50 k", "$50K", "R6 shorthand 50 k->$50K"),
    ("3 mil", "$3M", "R6 shorthand 3 mil->$3M"),
    ("10 m", "$10M", "R6 shorthand 10 m->$10M"),
    ("5 mil in revenue", "$5M in revenue", "R6 shorthand mil in context"),
    # word-number fraction money (money-gated: only before slang units)
    ("three and a half mil in revenue", "$3.5M in revenue", "R6 word-fraction mil->$3.5M"),
    ("five and a quarter mil", "$5.25M", "R6 word-fraction quarter->$5.25M"),
    # shorthand-unit guards: bare unit with no numeric quantity stays untouched
    ("vitamin k", "vitamin k", "R6 guard: 'k' not after a number stays"),
    ("plan m", "plan m", "R6 guard: 'm' not after a number stays"),
    ("three and a half years", "3 and a half years", "R6 guard: non-money fraction untouched"),

    # $N + scale recombination
    # NB the v2 spec's own worked example says "$5 thousand" -> $5,000, but that
    # contradicts its threshold table ("$2,000 upward uses $NK... surface form is
    # irrelevant") AND its "$"-literal renormalization ("$2,000" -> $2K). We follow
    # the table; the example reads as a stale v1 carryover.
    ("$100 million", "$100M", "R6 $100 million->$100M"),
    ("$5 thousand", "$5K", "R6v2 $5 thousand->$5K (table wins)"),
    ("$2 billion", "$2 billion", "R6v2 $2 billion->$2 billion (lowercase)"),
    # v2: already-"$" whole-dollar literals renormalize to the table
    ("$100,000", "$100K", "R6v2 $-literal renorm $100,000->$100K"),
    ("$2,000", "$2K", "R6v2 $-literal renorm $2,000->$2K"),
    ("$1,000,000", "$1M", "R6v2 $-literal renorm $1,000,000->$1M"),
    ("$1,500", "$1,500", "R6v2 $1,500 stays (comma band)"),
    ("$19.99", "$19.99", "R6v2 real cents stay"),
    # v2: bucks
    ("20 bucks", "$20", "R6v2 20 bucks->$20"),
    ("a couple bucks", "a couple bucks", "R6v2 bucks not after a number stays"),
    ("$1M bucks", "$1M", "R6v2 $1M bucks->$1M"),
    ("a hundred bucks", "$100", "R6v2 a hundred bucks->$100 (article dropped)"),
    # v2: bare UPPERCASE K/M numbers are money unless a quantity noun follows.
    # (An ISOLATED single K/M token is deliberately left alone — idempotency with
    # Rule 8's own "2M"/"300K" outputs.)
    ("we spent 250K on ads", "we spent $250K on ads", "R6v2 bare 250K in sentence"),
    ("it did 2.5M last year", "it did $2.5M last year", "R6v2 bare 2.5M in sentence"),
    ("100K followers", "100K followers", "R6v2 K + counting noun stays quantity"),
    ("50K subscribers", "50K subscribers", "R6v2 K + subscribers stays quantity"),

    # implied money - rate phrase
    ("a million a month", "$1M a month", "R6 rate: a million a month->$1M a month"),
    ("making a million a month", "making $1M a month", "R6 rate: making $1M a month"),
    ("two hundred thousand a week", "$200K a week", "R6 rate: ->$200K a week"),

    # counting-noun guard
    ("the past five years", "the past 5 years", "R6 guard: 5 years"),
    ("two points three points", "2 points 3 points", "R6 guard: points"),
    ("five people", "5 people", "R6 guard: 5 people"),

    # very large numbers
    ("200 million or 500 million", "$200M or $500M", "R6 very-large implied money"),

    # Pass E (2026-07-06 Oliver-corpus verify): a bare lowercase k/m number RANGED with a
    # money token inherits money — Oliver's published caption reads "$600K to".
    ("how do I go from 600k to 5 million?", "how do I go from $600K to $5M?",
     "R6 PassE bare k to-joined with money"),
    ("2m or 500k in profit", "$2M or $500K in profit", "R6 PassE bare m or-joined with money"),
    ("i run 5k every morning", "I run 5k every morning", "R6 lowercase k race distance NOT money"),

    # reliable trigger words
    ("we did 44 million in revenue", "we did $44M in revenue", "R6 trigger revenue"),
    ("cash was tight we only had five thousand left", "cash was tight we only had $5K left", "R6v2 trigger cash ($5K per table)"),
    # v2: implied money >= $1M, no trigger needed (counting noun still blocks)
    ("we grew it to two million", "we grew it to $2M", "R6v2 >=1M implied money"),
    ("two million people", "2M people", "R6v2/R8v2 counting noun blocks money, K/M scales"),
    ("a million people", "1M people", "R3v2/R8v2 a million people->1M people"),

    # neutral words don't trigger
    ("a 100 dollar deal", "a $100 deal", "R6 explicit $ near 'deal'"),
    ("50 sales", "50 sales", "R6 neutral 'sales' no trigger"),

    # year guard
    ("in 2024 our revenue grew", "in 2024 our revenue grew", "R6 year guard 2024"),
    ("back in 2024 we launched", "back in 2024 we launched", "R8 year no comma"),

    # ---------------- Rule 7: symbol & multiplier ----------------
    ("fifty dollars", "$50", "R7 fifty dollars->$50"),
    ("fifty percent", "50%", "R7 fifty percent->50%"),
    ("five times", "5X", "R7 five times->5X"),
    ("thirty percent growth", "30% growth", "R7 30% growth"),
    ("ten times bigger", "10X bigger", "R7 10X bigger"),
    ("100 times", "100X", "R7 100 times->100X"),
    ("10x", "10X", "R7 10x->10X"),
    ("10x'ing", "10X'ing", "R7 10x'ing->10X'ing"),
    ("2xing", "2Xing", "R7 2xing->2Xing"),
    # do-not-convert (no specific number before unit)
    ("a lot of dollars", "a lot of dollars", "R7 no number before dollars"),
    ("what percentage did you get", "what percentage did you get", "R7 no number before percentage"),
    ("many times over", "many times over", "R7 no number before times"),
    ("zero percent", "0%", "R7/R3 zero percent->0%"),

    # ---------------- Rule 8 (v2): large non-money numbers -> K/M scale ----------------
    ("two hundred thousand", "200K", "R8v2 two hundred thousand->200K"),
    ("fifty thousand subscribers", "50K subscribers", "R8v2 50K subscribers"),
    ("300,000 customers", "300K customers", "R8v2 digit-literal 300,000->300K"),
    ("two billion", "2 billion", "R8v2 two billion->2 billion (lowercase, isolated)"),
    ("back in 2024", "back in 2024", "R8v2 year guard: 4-digit digit literal untouched"),

    # ---------------- Rule 9: dictionary ----------------
    ("one on one", "1-on-1", "R9 one on one->1-on-1"),
    ("alex hormozi", "Alex Hormozi", "R9 name"),
    ("leila hormozi", "Leila Hormozi", "R9 name"),
    ("sharran srivatsaa", "Sharran Srivatsaa", "R9 name"),
    ("gym launch", "Gym Launch", "R9 brand"),
    ("the gym launch was yesterday", "the Gym Launch was yesterday", "shared vocab multi-word brand"),
    ("i went to the gym before launch", "I went to the gym before launch", "common gym/launch stay lowercase"),
    ("taylor sheridan made yellowstone", "Taylor Sheridan made Yellowstone", "review regression: names/title"),
    ("palmer luckey and jerry seinfeld", "Palmer Luckey and Jerry Seinfeld", "review regression: names"),
    ("acq uses money models", "ACQ uses Money Models", "review regression: acronym/title"),
    ("acquisition.com", "Acquisition.com", "R9 domain"),
    ("ai", "AI", "R9 acronym AI"),
    ("roi", "ROI", "R9 acronym ROI"),
    ("cac", "CAC", "R9 acronym CAC"),
    ("ltv", "LTV", "R9 acronym LTV"),
    ("ebitda", "EBITDA", "R9 acronym EBITDA"),
    ("kpi", "KPI", "R9 acronym KPI"),
    ("kpis", "KPIs", "R9 acronym KPIs"),
    ("cta", "CTA", "R9 acronym CTA"),
    ("ctas", "CTAs", "R9 acronym CTAs"),
    ("b2b", "B2B", "R9 acronym B2B"),
    ("b2c", "B2C", "R9 acronym B2C"),
    ("ceo", "CEO", "R9 acronym CEO"),
    ("cfo", "CFO", "R9 acronym CFO"),

    # ---------------- Rule 1: capitalization ----------------
    ("i", "I", "R1 I"),
    ("i'm", "I'm", "R1 I'm"),
    ("i'll", "I'll", "R1 I'll"),
    ("i'd", "I'd", "R1 I'd"),
    ("i've", "I've", "R1 I've"),
    ("etc.", "etc.", "R1 etc. lowercase"),
    ("e.g.", "e.g.", "R1 e.g. lowercase"),
    ("i.e.", "i.e.", "R1 i.e. lowercase"),
    # sentence start not capitalized
    ("the best thing i did", "the best thing I did", "R1 sentence start lowercase, I capped"),

    # ---------------- Rule 2: punctuation ----------------
    ("hello, world", "hello world", "R2 remove comma"),
    ("this is great.", "this is great", "R2 remove trailing period"),
    ("are you sure?", "are you sure?", "R2 keep ?"),
    ("that's amazing!", "that's amazing!", "R2 keep !"),
    ("don't do it", "don't do it", "R2 keep contraction apostrophe"),
    ("1,000", "1,000", "R2 keep comma inside number"),
    ("$1.2M", "$1.2M", "R2 keep period inside money"),
    ("U.S.", "U.S.", "R2 keep abbreviation periods"),

    # ---------------- Idempotency ----------------
    ("$1K", "$1K", "idem $1K"),
    ("ROI", "ROI", "idem ROI"),
    ("1-on-1", "1-on-1", "idem 1-on-1"),
    ("AI", "AI", "idem AI"),
    ("10X", "10X", "idem 10X"),
    ("1,000", "1,000", "idem 1,000"),

    # ---------------- Regression: adversarial-finding fixes (2026-06-11) ----------------
    # R1: spec-listed acronyms missing from the dict (capitalize from lowercase input)
    ("sop", "SOP", "R1 SOP acronym capitalized"),
    ("we wrote an sop", "we wrote an SOP", "R1 SOP mid-sentence"),
    ("u.s.", "U.S.", "R1 lowercase u.s. -> U.S."),
    ("the u.s. economy", "the U.S. economy", "R1 lowercase u.s. mid-sentence"),
    # R2: trailing comma after protected abbreviation/domain must be removed
    ("e.g.,", "e.g.", "R2 drop comma after e.g."),
    ("i.e.,", "i.e.", "R2 drop comma after i.e."),
    ("etc.,", "etc.", "R2 drop comma after etc."),
    ("U.S.,", "U.S.", "R2 drop comma after U.S. (keep cap)"),
    ("in the U.S., we win", "in the U.S. we win", "R2 drop comma after U.S. mid-sentence"),
    ("acquisition.com,", "Acquisition.com", "R2 drop comma after domain (+cap)"),
    ("Acquisition.com,", "Acquisition.com", "R2 drop comma, keep correct domain"),
    # R8 lock-before-thousands: % / X suffix must not eat the thousands comma
    # (multiplier/percent numbers keep COMMA form — the v2 K/M scale is for plain
    # counts; "50,000%" reads clearer than "50K%")
    # 2026-08-11: a spoken MAGNITUDE now wins over the "times"->X fold, so these three
    # read "1K times" / "2K times" / "1M times" instead of "1,000X" / "2,000X" /
    # "1,000,000X". That is the NON_MONEY_AFTER rule ported from spice_normalize (the
    # count noun is what drops the "$", and the compact magnitude is locked before Rule 7
    # can fold it) — both files now agree. The bare "<n> times" X-fold is UNCHANGED
    # ("ten times bigger" -> "10X bigger", "100 times" -> "100X", asserted above).
    ("one thousand times", "1K times", "R6/R7 magnitude wins over X-fold (spice parity)"),
    ("a million times", "1M times", "R6/R7 magnitude wins over X-fold (spice parity)"),
    ("five thousand percent", "5,000%", "R8+R7 5,000% comma survives percent"),
    ("fifty thousand percent", "50,000%", "R8+R7 50,000% comma survives percent"),
    ("two thousand times", "2K times", "R6/R7 magnitude wins over X-fold (spice parity)"),
    # R3 zero exception via bare symbols
    ("zero %", "0%", "R3 zero + bare % -> 0%"),
    ("zero $", "$0", "R3 zero + bare $ -> $0"),
    # v2: spoken 'two thousand' scales to 2K (exempt from the year guard)
    ("two thousand", "2K", "R8v2 spoken two thousand -> 2K (not year-guarded)"),
    ("two thousand in revenue", "$2K in revenue", "R6v2 revenue trigger -> $2K"),
    # v2: digit literals scale too (surface form irrelevant; years excepted)
    ("5000", "5K", "R8v2 digit literal 5000->5K"),
    ("12000 steps", "12K steps", "R8v2 digit literal 12000 steps->12K steps"),
    # idempotency: thousands-comma multiplier preserved + X stays uppercase
    ("2,000X", "2,000X", "idem 2,000X (comma + uppercase X)"),
    # R6 shorthand-K in implied money context -> $NK
    ("the price is 5k", "the price is $5K", "R6 5k near 'price' -> $5K"),
    ("charging 10k", "charging $10K", "R6 10k near 'charging' -> $10K"),
    ("the price is 50k", "the price is $50K", "R6 50k near 'price' -> $50K"),
    # guard: shorthand-K with NO money context stays raw (not falsely money-formatted)
    ("i run 5k every morning", "I run 5k every morning", "R6 5k (no money ctx) stays 5k"),

    # ---------------- Regression: money amount + scale word (2026-06-16) ----------------
    # A "$N"/"$N.N" amount immediately before a scale word folds into ONE money token; the
    # scale word must NOT expand on its own. Bug: "$400 million" rendered "$400 1,000,000"
    # because the guards only matched a bare r"\$\d+" — missing the decimal form ("$1.5")
    # and the STT-glued-article form ("a $400", exercised in WORD_CASES below; text mode
    # splits on the space so the article never glues here). Fix: _money_scale_base.
    ("$5 million", "$5M", "money+scale $5 million->$5M"),
    ("$400 million", "$400M", "money+scale $400 million->$400M"),
    ("$1.5 billion", "$1.5 billion", "money+scale DECIMAL ->$1.5 billion (v2 lowercase)"),
    ("$1.5 million", "$1.5M", "money+scale DECIMAL ->$1.5M"),
    ("100 million dollars", "$100M", "money 100 million dollars->$100M"),
    ("five hundred million", "500M", "R8v2 isolated no-$ five hundred million->500M"),
    ("I made a $400 million exit", "I made a $400M exit", "money+scale in sentence, article 'a' kept"),
    ("it's a $2 billion company", "it's a $2 billion company", "money+scale billion in sentence (v2 lowercase)"),
    # NB the rate phrase "a million a month"->$1M a month is asserted above (R6 rate)
    # and unchanged; the fold fix only fires when a "$" token precedes the scale word.

    # ================= v2 spec additions (2026-07-06) =================
    # ---- Rule 4b: ordinals ----
    ("the third time", "the 3rd time", "R4b third->3rd (always)"),
    ("I came in fourth", "I came in 4th", "R4b fourth->4th (always)"),
    ("the fifth reason", "the 5th reason", "R4b fifth->5th"),
    ("the twentieth century", "the 20th century", "R4b twentieth->20th"),
    ("the second thing", "the 2nd thing", "R4b second+ordinal noun->2nd"),
    ("second option", "2nd option", "R4b second option->2nd option"),
    ("first step", "1st step", "R4b first step->1st step"),
    ("second nature", "second nature", "R4b idiom stays (no ordinal noun)"),
    ("first of all", "first of all", "R4b idiom stays"),
    ("thirty seconds", "30 seconds", "R4b time unit untouched (counting noun)"),
    ("give me a second", "give me a second", "R4b 'a second' time unit stays"),
    # ---- Rule 5: sequence labels on digit forms + expanded list ----
    ("step 1", "step #1", "R5v2 digit form step 1->step #1"),
    ("thing two", "thing #2", "R5v2 thing two->thing #2"),
    ("takeaway three", "takeaway #3", "R5v2 takeaway three->takeaway #3"),
    # ---- Rule 7: plus / multiplier words / percentage ranges ----
    ("$5M plus", "$5M+", "R7v2 $5M plus->$5M+"),
    ("50% plus", "50%+", "R7v2 50% plus->50%+"),
    ("a plus player", "a plus player", "R7v2 plus not after number stays"),
    ("double revenue", "2X revenue", "R7v2 double->2X"),
    ("triple your output", "3X your output", "R7v2 triple->3X"),
    ("quadruple the leads", "4X the leads", "R7v2 quadruple->4X"),
    ("double down on it", "double down on it", "R7v2 'double down' idiom stays"),
    ("a triple threat", "a triple threat", "R7v2 'triple threat' stays"),
    ("10 to 20%", "10% to 20%", "R7v2 percentage range distributes"),
    ("ten to twenty percent", "10% to 20%", "R7v2 spoken percentage range"),
    ("5 to 10 people", "5 to 10 people", "R7v2 non-percentage range untouched"),
    # ---- Rule 2: dangling dashes + fragments ----
    ("short- term wins", "short term wins", "R2v2 dangling dash stripped"),
    ("i- I mean it", "I I mean it", "R2v2 'i-' -> I"),
    ("you make-?", "you make?", "R2v2 dangling dash keeps ?"),
    ("the s- the sales team", "the the sales team", "R2v2 1-2 letter fragment dropped"),
    ("short-term wins", "short-term wins", "R2v2 internal hyphen kept"),
    # ---- Rule 9: dictionary additions ----
    ("versus", "vs", "R9v2 versus->vs"),
    ("me versus you", "me vs you", "R9v2 versus mid-sentence"),
    ("going to be great", "gonna be great", "R9v2 going to be->gonna be"),
    ("want to be rich", "wanna be rich", "R9v2 want to be->wanna be"),
    ("going to the gym", "going to the gym", "R9v2 'going to' NOT contracted elsewhere"),
    ("want to win", "want to win", "R9v2 'want to' NOT contracted elsewhere"),
    ("steve jobs", "Steve Jobs", "R9v2 Steve Jobs"),
    ("he created jobs", "he created jobs", "R9v2 bare 'jobs' stays lowercase"),
    ("qr code", "QR code", "R9v2 qr->QR"),
    ("go to school", "go to Skool", "R9v2 school->Skool (brand homophone)"),
    ("high school", "high school", "R9v2 education modifier blocks Skool"),
    ("business school", "business school", "R9v2 education modifier blocks Skool"),
    ("the school district", "the school district", "R9v2 education noun blocks Skool"),
    ("skool is great", "Skool is great", "R9v2 skool spelling capitalizes"),
    ("mm", "mmh", "R9v2 mm->mmh backchannel"),
    ("mm-hmm", "mhm", "R9v2 mm-hmm->mhm"),
    ("mmhmm", "mhm", "R9v2 mmhmm->mhm"),
    ("hmm", "hmm", "R9v2 hmm untouched"),
    # ---- Rule 1: places / languages / ALL-CAPS ----
    ("utah", "Utah", "R1v2 state capitalized"),
    ("moved to texas", "moved to Texas", "R1v2 texas mid-sentence"),
    ("las vegas", "Las Vegas", "R1v2 multi-word city"),
    ("new york", "New York", "R1v2 multi-word city"),
    ("he speaks spanish", "he speaks Spanish", "R1v2 language capitalized"),
    ("polish the offer", "polish the offer", "R1v2 'polish' common-word exclusion"),
    ("turkey sandwich", "turkey sandwich", "R1v2 'turkey' common-word exclusion"),
    ("the AC broke", "the AC broke", "R1v2 ALL-CAPS token preserved"),
    ("VIPs only", "VIPs only", "R1v2 ALL-CAPS plural preserved"),

    # ========== Rule 6: <number>+<magnitude> — COUNT vs MONEY (2026-08-11) ==========
    # Ported from spice_normalize.py's NON_MONEY_AFTER fix (2026-08-10): a magnitude
    # phrase used to be stamped with "$" unconditionally, so "nine billion views" burned
    # as "$9B views" and "a thousand times more" as "$1K times more". BOTH directions are
    # asserted here — a count must LOSE the "$", real money must KEEP it — because a
    # one-sided test would pass on a rule that simply stopped money-izing everything.
    # ⚠️ KEEP IN SYNC with spice_normalize.py: these same strings must round-trip
    # identically through the qa path (scripts/spice_normalize.py).
    # --- COUNT: the token after the magnitude names a countable thing -> no "$" ---
    ("nine billion views", "9B views", "R6 count: nine billion views->9B views (no $)"),
    ("a thousand times more", "1K times more", "R6 count: a thousand times more->1K times more"),
    ("three million subscribers", "3M subscribers", "R6 count: 3M subscribers (no $)"),
    ("three billion people", "3B people", "R6 count: 3B people (no $)"),
    ("700 thousand views", "700K views", "R6 count: digit+magnitude 700K views (no $)"),
    ("46.2 million views", "46.2M views", "R6 count: decimal mantissa 46.2M views (no $)"),
    ("a thousand posts", "1K posts", "R6 count: 1K posts (no $)"),
    ("9 billion views", "9B views", "R6 count: digit form 9B views (no $)"),
    # --- MONEY: an explicit dollar word / money context still wins -> keep "$" ---
    ("three million dollars", "$3M", "R6 money: dollar word wins->$3M"),
    ("700 thousand a year", "$700K a year", "R6 money: rate phrase->$700K a year"),
    ("a million bucks", "$1M", "R6 money: bucks->$1M"),
    ("46.2 million in profit", "$46.2M in profit", "R6 money: decimal + trigger->$46.2M"),
    ("2.5 million dollars", "$2.5M", "R6 money: decimal + dollar word->$2.5M"),
    ("we did 44 million in revenue", "we did $44M in revenue", "R6 money: revenue trigger->$44M"),
    ("one billion dollars", "$1 billion", "R6 money: billions keep the v2 word form"),
    # --- the count guard must not eat the bare "<n> times" X-fold ---
    ("ten times bigger", "10X bigger", "R7 bare count+times still folds to 10X"),
    ("100 times", "100X", "R7 bare count+times still folds to 100X"),
    # --- lone "Nx" multiplier matches the RAW token, so a thousands comma survives ---
    ("1,000x", "1,000X", "R7 1,000x->1,000X (comma survives; raw-token match)"),
    ("1,000x'ing", "1,000X'ing", "R7 1,000x'ing->1,000X'ing (comma + suffix)"),
    ("10x", "10X", "R7 10x->10X (unchanged)"),
    # --- guard: an inexact thousands value keeps Rule 8's comma form ---
    ("fifteen hundred people", "1,500 people", "R8 1,500 people (not 1.5K)"),
]


def _words(*surfaces):
    """Build a minimal word-timestamp list (1s slots) from surface strings, the shape
    format_words consumes from the transcriber."""
    return [{"word": s, "start": float(i), "end": i + 0.5} for i, s in enumerate(surfaces)]


def _join_words(word_list):
    """Render a format_words() result back to a space-joined caption string."""
    return " ".join(t["word"] for t in word_list)


# (input word surfaces, expected joined output, label) for the WORD-TIMESTAMP path
# (format_words) — the real caption path, and the one the STT-glued-article bug lives on:
# Whisper emits the article fused to the amount as a SINGLE token ("a $400"), so the bug
# does NOT reproduce in text mode (which splits on the space). The scale word must fold,
# never expand to digits ("a $400" + "million" must be "a $400M", NOT "a $400 1,000,000").
WORD_CASES = [
    # the reported bug — glued article on the money token
    (["a $400", "million"], "a $400M", "WORD glued 'a $400' million -> a $400M (NOT 1,000,000)"),
    (["the $5", "million"], "the $5M", "WORD glued 'the $5' million -> the $5M"),
    (["an $8", "billion"], "an $8 billion", "WORD glued 'an $8' billion -> an $8 billion (v2 lowercase)"),
    (["a $400", "million", "exit"], "a $400M exit", "WORD glued article mid-phrase"),
    (["I", "made", "a $400", "million", "exit"], "I made a $400M exit", "WORD glued in a sentence"),
    # un-glued money token + scale word (must match text mode)
    (["$400", "million"], "$400M", "WORD $400 million -> $400M"),
    (["$2", "billion"], "$2 billion", "WORD $2 billion -> $2 billion (v2 lowercase)"),
    (["$1.5", "billion"], "$1.5 billion", "WORD decimal $1.5 billion -> $1.5 billion"),
    (["$5", "thousand"], "$5K", "WORD $5 thousand -> $5K (v2 table)"),
    # NO "$" -> isolated number words scale per v2 Rule 8 (no money-izing when isolated)
    (["two", "million"], "2M", "WORD no-$ isolated two million -> 2M"),
    (["five", "hundred", "million"], "500M", "WORD no-$ isolated five hundred million -> 500M"),
    # v2: merged-token timing must survive the new rules (money + ordinals + fragments)
    (["two", "million", "people"], "2M people", "WORD counting noun blocks money, K/M scales"),
    # 2026-08-11 count-vs-money split on the REAL caption path (timing + idempotency are
    # checked by the runner, so this also proves "9B views"/"1K times" re-feed unchanged).
    (["nine", "billion", "views"], "9B views", "WORD count: nine billion views -> 9B views"),
    (["a", "thousand", "times", "more"], "1K times more", "WORD count: 1K times more"),
    (["three", "million", "subscribers"], "3M subscribers", "WORD count: 3M subscribers"),
    (["three", "million", "dollars"], "$3M", "WORD money: dollar word wins -> $3M"),
    (["46.2", "million", "in", "profit"], "$46.2M in profit", "WORD money: decimal mantissa -> $46.2M"),
    (["700", "thousand", "a", "year"], "$700K a year", "WORD money: rate phrase -> $700K a year"),
    (["the", "second", "thing"], "the 2nd thing", "WORD ordinal before ordinal noun"),
    (["va-", "value"], "value", "WORD fragment dropped, timing intact"),
    # v2 Pass D: Groq glues money ENUMERATIONS into ONE word token — embedded amounts
    # must still renormalize (caught live by caption_lint on the 2026-07-06 e2e verify).
    (["make $200,000, $300,000, $400,000", "a", "year"], "make $200K, $300K, $400K a year",
     "WORD glued money enumeration renormalizes"),
    (["you", "keep", "$1,500, $1,800"], "you keep $1,500, $1,800",
     "WORD glued comma-band amounts stay comma form"),
    (["serving", "300,000 customers", "daily"], "serving 300K customers daily",
     "WORD glued bare comma-number scales"),
]


def run_word_cases():
    """Exercise format_words: correctness, idempotency (re-feeding the output is stable),
    and timing-metadata sanity (no None timings, end>start, starts non-decreasing)."""
    passed = 0
    failures = []
    for surfaces, expected, label in WORD_CASES:
        words = _words(*surfaces)
        out = format_words(words)
        actual = _join_words(out)
        # idempotency: feeding format_words its own output must not change the text
        twice = _join_words(format_words(out))
        # timing sanity
        timing_ok = all(
            (t.get("start") is not None and t.get("end") is not None
             and t["end"] > t["start"]) for t in out
        )
        starts = [t["start"] for t in out]
        monotonic = all(b >= a for a, b in zip(starts, starts[1:]))
        ok = (actual == expected) and (twice == actual) and timing_ok and monotonic
        if ok:
            passed += 1
        else:
            why = []
            if actual != expected:
                why.append("output")
            if twice != actual:
                why.append(f"idempotency (twice={twice!r})")
            if not timing_ok:
                why.append("timing")
            if not monotonic:
                why.append("start-order")
            failures.append((surfaces, expected, actual, label, ", ".join(why)))
    total = len(WORD_CASES)
    print(f"WORD-MODE PASSED {passed}/{total}")
    if failures:
        print(f"\nWORD-MODE FAILURES ({len(failures)}):")
        for surfaces, exp, act, label, why in failures:
            print(f"  [{label}]  (failed: {why})")
            print(f"    input:    {surfaces!r}")
            print(f"    expected: {exp!r}")
            print(f"    actual:   {act!r}")
    return passed, total, failures


def run():
    passed = 0
    failures = []
    for inp, expected, label in CASES:
        actual = format_caption_text(inp)
        if actual == expected:
            passed += 1
        else:
            failures.append((inp, expected, actual, label))
    total = len(CASES)
    print(f"PASSED {passed}/{total}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for inp, exp, act, label in failures:
            print(f"  [{label}]")
            print(f"    input:    {inp!r}")
            print(f"    expected: {exp!r}")
            print(f"    actual:   {act!r}")
    return passed, total, failures


if __name__ == "__main__":
    p, t, f = run()
    wp, wt, wf = run_word_cases()
    sys.exit(0 if not f and not wf else 1)
