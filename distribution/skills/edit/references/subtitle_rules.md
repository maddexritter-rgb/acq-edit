# Q&A subtitle text normalization rules

Applied automatically by [`scripts/normalize_caption_text.py`](../scripts/normalize_caption_text.py). Goal: visual clarity, immediate understanding, zero friction between spoken audio and on-screen subtitle.

## Capitalization

- **Lowercase everything** by default.
- **Exceptions** (keep original case):
  - Proper nouns (heuristic: capitalized mid-sentence in source transcript)
  - First-person `I`, `I'm`, `I'd`, `I've`, `I'll`
  - Fully capitalized acronyms in source (e.g. `USA`, `CRM`, `SaaS`, `LTV`)

## Numbers and symbols

- **Money prefix always `$`:** `$1`, `$190`, `$1,600`, `$2.5K`, `$600K`, `$3M`, `$20M`, `$3B`
- **Words → symbols:**
  - `dollars` / `bucks` → `$`
  - `percent` / `percentage` / `percentages` / `per cent` → `%`
  - `number one` when context is ranking → `#1`
- **Money abbreviations:**
  - `≥ $100,000` always abbreviated to `K` / `M` / `B`
    - `$250,000` → `$250K`
    - `$1,200,000` → `$1.2M`
    - `$20,000,000` → `$20M`
    - `$3,000,000,000` → `$3B`
  - `< $100,000` either form is fine; prefer abbreviated if source uses round thousands (`$10,000` → `$10K`)

## Layout

- **Single line** default. Break into two lines only if the line would exceed ~20 chars.
- **Parenthetical explainers** below the main line are allowed: `(think: Facebook pixel)`.
- **No dead gaps** — one chunk's end time abuts the next chunk's start time (≤30ms gap).
- **No trailing stub words** — a standalone "and", "but", "so" at the very end is cut.

## Content

- **Filler words** already stripped by `shortform/detect_fillers.py` — captions only show kept words.
- **Spell-check** — run a final pass before shipping. The Groq transcription is good but not perfect on proper nouns.
- **Emphasis words** promote to the `Black` / `Black Italic` weight variant — typically numbers, dollar amounts, percentages, key nouns in the payoff.

## Test cases the normalizer should pass

| Input | Output |
|---|---|
| `We made 1.2 million dollars last year.` | `we made $1.2M last year` |
| `Our close rate went from 5 percent to 20 percent.` | `our close rate went from 5% to 20%` |
| `I paid 75,000 dollars for the lead source.` | `I paid $75K for the lead source` |
| `The LTV is 300 bucks, not 30 dollars.` | `the LTV is $300, not $30` |
| `I think what I'd do is call Samantha first.` | `I think what I'd do is call Samantha first` |
