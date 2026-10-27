# Session regression ledger — preview.11

Evidence: supplied new-Mac review archive, 2026-10-27 18:17–19:32 UTC, 638 tool records.
Compared against main `8bf16514ff614501b9ca5e68dcee600a9e7e1428` before repair.
Private transcript, account data, project artifacts and media are not copied into this repository.

| Issue | Classification | Evidence / change |
|---|---|---|
| Rust required for Apple-silicon FilmCraft | Already fixed | preview.5 prebuilt runtime retained. |
| File editing to enter keys | Already fixed | preview.6 private browser key form retained. |
| Too many public skills | Already fixed | preview.9 six picker skills retained; internal dependencies remain available. |
| Missing Frame/Monday onboarding | Already fixed | preview.8 required delivery checkpoint retained. |
| Old Premiere bridge selected | Already fixed | preview.10 connector isolation retained and regression-tested. |
| Python and npm certificate failures | Newly repaired | Records 49/51/55: missing Homebrew CA bundle, then issuer failure. Valid system/company trust now propagates to installer children. Invalid trust stops; TLS verification cannot be disabled. |
| Setup aborted at piped storage prompt | Newly repaired | Records 68/69: EOF followed by improvised config script. `--non-interactive` now reuses the real setup/save path, backup and service lock. |
| YouTube JS challenge failure | Newly repaired | Records 157/158: missing enabled Node runtime, then session wrapper. Repository intake supplies exact Node; toolkit installs pinned yt-dlp[default]/EJS and probes the solver. |
| Broken pinned Node, external Premiere profile workaround | Newly repaired | Records 485/488/492: missing dylib. Executables are probed; `--fresh-runtime` preserves the old install and retargets owned config paths. External profiles stay prohibited. |
| Two editors collided with one runtime/config | Newly repaired | Per-engine runtime registry, explicit routing, in-place legacy adoption and shared credentials/assets. Storage and existing project paths are preserved. |
| Caption helpers lacked Pillow | Newly repaired | Records 203/525. Verified helper launcher selects toolkit Python; CLI/agent paths prepend it. |
| Guessed “Bold Italic” face | Newly repaired | Records 253/257/258. Calibration resolves the selected PostScript identity against installed font metadata and native styles, refusing missing/ambiguous faces. |
| Review-only room queued unprocessable revisions | Newly repaired | Record 291. UI labels Review only and disables submission; API returns 409 without a job. Feedback still saves. |
| Worker required MP4 for Premiere completion | Newly repaired in code; native verification pending | New jobs freeze a distinct editable-project completion contract. Native receipt/journal/artifact validation and recovery require no MP4/version or room. Existing rendered jobs retain their contract. |
| Gemini generation failed with HTTP 402 | Provider limitation | Record 232. Billing-required is distinct from authentication; a models read does not prove audiovisual analysis. No claim that credits were repaired. |
| Premiere 26.5.2 | Awaiting native verification | Record 492 observes that host. Registry reports it unqualified; this development Mac has 26.3.0, not 26.5.2. Exact host/scoped ownership guards remain. |
| Editor handoff | Awaiting native verification | Both-direction checkpoint/import orchestration and pause behavior implemented. Native layer reconstruction/fidelity remains unqualified; no arbitrary-project conversion or MP4 flattening. |
| Exported session's final Premiere native result | Awaiting native verification | Session ended before complete final reopen/render validation. Do not reinterpret earlier flattened import or successful API calls as editable/native acceptance. |

Regression checks cover certificate trust and subprocess environment, Node failure, toolkit
Python, setup/legacy adoption/two-engine coexistence, YouTube args, exact font resolution,
review-only UI/API, native completion and historical jobs, and both-direction handoff boundaries.
The clean-runtime rehearsal uses a fresh toolkit environment on this development Mac; it does
not claim a factory-clean Mac, fresh provider authorization, or human audiovisual approval.

## Rehearsal evidence

A fresh toolkit copy installed the full shared Python requirements and downloaded/verified the
pinned prebuilt FilmCraft runtime without Rust. A fresh npm install/build and noninteractive
configuration completed. Its repository intake downloaded and registered the session's complete
YouTube source: 45,421,499 bytes, SHA-256
`2a714475cf21a83965f7f4afc59633cef65302b8d18325488ca5df356b7fae39`, intake state `ready`.
The toolkit probe reported yt-dlp 2026.10.26, EJS 0.8.0 and verified Node 24.22.1.
A live headless FilmCraft font inventory plus installed font metadata resolved the relevant
PostScript italic face to `Bold It`. This is font-selection proof, not rendered caption approval.

Automated validation: 183 Node tests and 70 targeted Python tests pass. Python suites cover onboarding, delivery,
installation isolation, connector locking, runtime trust, font resolution and native readback.
Distribution audit found no portability findings. No production editor project was changed.
The full supplied editorial/render session was not replayed: native-only completion, 26.5.2
qualification and both-direction real editor handoffs remain explicit acceptance work.
