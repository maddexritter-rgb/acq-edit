# Worked caption decisions

These generalized cases preserve the research lessons without binding this skill
to a person, project ID, machine path or external drive. They are examples, not
automatic replacement rules. `Source IDs` below illustrate lineage, not production
IDs. Consult [research_unresolved.md](research_unresolved.md) before implementing.

## Timing, restart and continuity cases

| Source situation | Observed problem | Supported decision |
|---|---|---|
| `I ... felt like` with a stretched ASR label | A solo `I` appears well before speech | Verify onset, then group `I felt like` if pause/cut constraints permit |
| `some`, real pause, `20-year-olds` | Incoming age replaces the prefix and feels isolated | Optionally retain `some` at the later age onset; never reveal the age at the earlier prefix onset |
| `I think that you, you must have` | Cleanup removes the first `you` | Reference keeps `I think that you-` then `you must have`; preserve both source occurrences; dash is a separate reviewed choice |
| `then let's do that` twice | First completed statement deleted as a restart | Preserve both occurrences; different weight on the repeat is possible, not mandatory |
| `open up—` | Fragment removal deletes complete `up` | Protect the complete source word before display punctuation |
| `the, the, the list quality` | Cleanup moves later words onto an earlier article onset | Review each occurrence and the real pause; do not hide an omitted article by excluding its source ID |
| A camera cut during an existing hold | Outgoing caption ends and leaves a hole | Partition into continuation segments with one owner and advanced animation phase |

For the prefix example, the reviewed offline candidate kept the incoming onset
at frame2546 and end2560, inheriting a prefix first shown at2531. Its animation
elapsed15frames; source ownership stayed with the original occurrence. Exact
numbers are example-local, not a timing preset. This refinement was not rendered
or user-approved; the preceding full comparison was already called shippable.

Illustrative ownership:

```json
{
  "prefix": {"text": "some", "owned_source_ids": [10]},
  "incoming": {
    "text": "some 20-year-olds",
    "owned_source_ids": [11],
    "inherited_source_ids": [10],
    "onset_policy": "retain the age's independently reviewed later onset"
  }
}
```

This is explanatory notation, not a replacement for the native manifest schema.
For actual cards update all styled words/text, width, timing and continuation data.

## Numeric examples and their boundaries

| Spoken/contextual form | Failure seen | Reviewed or intended interpretation |
|---|---|---|
| `unit four, five, and six` | `four five` summed to9 | Separate4,5,6; retain individual intervals |
| `option two, one moment` | Label becomes#3 | `option #2` followed by `one moment` |
| `forty fifty K` in a fee discussion | `$90K` | Reference displays `$40K-$50K`; context, not adjacency, establishes range |
| `two fifty, three hundred K` | `$5500K` | Reference displays `$250K-$300K`; the collector guard alone leaves unresolved `2 50 $300K` |
| `fifty sixty percent` |110% | Reviewed range50%-60%; genuine `one hundred ten percent` must still be110% |
| `sixty to seventy K` | Uneven units | Reference retains connector: `$60K to $70K`, not a mandatory hyphen |
| `two point one million` | `2 point #1000000` | Decimal candidate gives `$2.1M` in supported money context |
| `zero point five percent` | `zero point #5` | Decimal candidate gives0.5% |
| `four ninety seven` answering cost |101, then candidate `4 97` | Context suggests a compact price; candidate is incomplete, not automatically approved as$497 |
| `fifty fifty` describing ownership |100 | Do not sum; precise ratio display still requires a context decision |
| `nineteen ninety nine` |118, then `19 99` | Could be year-style speech; candidate does not resolve it |
| `one hundred and twenty five` | `100 and 25` | Conjunction grammar remains unfinished |

Explicit numeric review must bind source hash, exact original text/IDs, current
normalized display, evidence and reviewer decision. A reviewed multi-record merge
must preserve contiguous single ownership, known voice, valid durations and hard
boundaries, then rebuild downstream indices BEFORE grouping. Do not retrofit a
merge into cards using stale normalized indices.

One range could not pass timing validation: its first amount had a zero-duration
ASR interval54.140–54.140. Regional ASR proposed53.700–54.040 but overlapped a
low-energy interval53.7605–54.0004; acoustic character emissions occurred around
53.976–54.157. The previous speaker's label extended to54.140. Thus widening one
token by a frame would not resolve the question/answer boundary. Keep display
approval separate from timing approval; never invent duration to satisfy a gate.

## Annotation and voice contrasts

- `net` displayed as `[profit]`: reviewed substitution retains the spoken word's
  ID, unlike an added gloss that explains something never spoken.
- Spoken `quote` displayed as an opening quotation mark: explicit substitution
  retains that ID. Do not silently delete it or invent a spoken `unquote`.
- Quoted terminology: can remain upright and current-voice colored. Quoted inner
  thought: can be italic while retaining host color. Role-played other voice is
  a different case; quotation marks alone cannot select the color.
- A silent interval displaying a name placeholder: preserve redacted/unresolved
  status. ASR completing a plausible brand name is not recovered speech.
- A logo carrying a spoken brand word: visually accounted for, but text-only SRT
  still needs explicit accessible coverage; image presence is not a text record.
- `*audience laughing*`: verified event annotation, not three fabricated `ha`
  speech tokens and not permission to fill every blank.

## Rendering contrast

An exact face missing locally caused substituted text despite familiar family
names appearing in the font menu. Exact PostScript preflight, approved donor
graphics and rendered verification solved the relevant workflow. Font installation
still needs authorization. Clone native donor shadow/animation rather than
approximating them for each card; preserve editable mixed-style runs.
