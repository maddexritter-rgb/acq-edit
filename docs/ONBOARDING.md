# Set up ACQ Edit on a new Mac

Open this repo in Codex or Claude Code and say:

> Set up ACQ Edit for me. Follow docs/ONBOARDING.md, ask one question at a time,
> save my progress, and use only this repository's editing skills.

After a Homebrew/Workbrew installation, ask your agent to finish ACQ Edit setup. The agent
runs `acq-edit onboard guide` to find the installed folder and reads its instructions.
You do not need to open a terminal or type commands.

The agent does the setup; you sign in and paste your keys into a small local setup page. No configuration files to open.
There is no separate Anthropic or OpenAI API key requirement. Use your signed-in Codex or
Claude Code account. The setup page keeps key values out of chat history.

## Agent onboarding contract

These instructions are for the Codex or Claude Code assistant helping the user. You are their
personal setup guide. Own the process through the first working clip; do not just hand them
this document or a wall of terminal commands. ACQ Edit uses their existing signed-in agent;
it does not download a separate conversational model.

### Be a helpful person, one step at a time

- Start warmly and briefly. Explain the next useful outcome, then ask one question. For example:
  “Let's get you set up so you can drop in footage and ask for an edit. I'll handle the setup
  and walk you through the account connections. Would you like to use FilmCraft or Premiere?”
- Infer the current agent from the session. Reuse choices and working connections already
  recorded; never make someone create a second account or repeat a completed step unnecessarily.
- Explain unfamiliar terms only when needed. An API key is the private connection that lets
  ACQ Edit use that service. Explain what each service does before sending its signup link.
- Give one link and one action at a time. Wait for the user's result before moving to the next
  account. Do independent local setup while they sign in when it does not depend on the answer.
- Answer questions directly, then return to the current step. If the user gets stuck, ask what
  they see or for the non-secret error text. Never ask for a screenshot containing a key.
- Run available setup commands yourself when authorized. Let the user handle sign-in, billing,
  terms acceptance and pasting keys into the local setup page. Do not ask a nontechnical user to edit JSON.
- After each check, say what worked and what is next. Be specific: “The transcription connection
  works. Next we'll connect video analysis.” Avoid saying “everything is ready” before testing it.
- Keep setup progress across interruptions. Read `onboard status`, saved configuration and
  connection-check results; use presence/status checks for credentials without displaying them.
  Keep a brief non-secret interview checkpoint at `~/.config/acq-edit/onboarding-interview.json`
  (or the configured `ACQ_EDIT_HOME`): engine, agent, storage, brands, delivery progress, optional intake connections,
  current step and next action. Never store keys, account responses or login URLs in that file.
  Installer progress remains in `.local/onboarding.json`; do not edit its completed-step ledger.
- If an earlier session is already configured, summarize the remaining steps and resume there.
  Setup requests authorize routine installation, not purchases, unrelated editor changes or uploads.

### Premiere bridge selection is locked

When Premiere is selected, use only **ACQ Edit Agent MCP** from this toolkit. Other installed
Premiere bridges must not be used for discovery, inspection, editing or export. Open the
ACQ Edit Agent panel and verify this installation with doctor. Do not select an older connector
just because its tools are already visible in chat. If needed, refresh the session or use the
verified repository helper; a missing or failing ACQ Edit route is a setup repair, not a fallback.
Do not remove or reconfigure the user's other bridges. Explain that they remain separate.

### Make the skills available

Onboarding registers only six picker skills: edit, assembly-design, horizontal-to-vertical,
caption-clips, music and monday. Other packaged owners stay internal.
After installation, help the user reopen the project/session if its skill picker is stale.
Offer to make them available in all chats: run `acq-edit skills install --agent codex --scope user`
(or `claude`) when that scope is requested. For weekly updates add `--update-owned`; this
retargets only previously registered toolkit links, never replaces unrelated personal skills.
Registration also removes older receipt-owned internal picker entries, keeping their runtime
files intact. Refresh both workspace and personal scope if both were registered previously.
If the user only wants captions, assembly, music or delivery, follow [SKILLS.md](SKILLS.md)
and set up that capability only. Do not require an editing engine for standalone Monday delivery.

### Walk the user through connections

First confirm the chosen engine and project storage, then follow the installation steps below.
Use FilmCraft or Premiere for this pilot; Resolve is paused. Once prerequisites are ready,
run onboarding yourself. Its credentials step opens a local browser form and waits for Save.
Use a background tool session so the user can fill it while you remain available. Explain:

1. **AssemblyAI — transcription and word timing.**
   Say: “First we'll connect transcription so the editor can find and cut exact spoken words.
   Open the [AssemblyAI dashboard](https://www.assemblyai.com/dashboard), sign in or create an
   account, and find your API key. I'll open a little setup page where you can paste it.”
   Help them locate the key using the [official quickstart](https://www.assemblyai.com/docs/pre-recorded-audio/getting-started/transcribe-an-audio-file)
   if the dashboard differs. Explain that usage is billed by the provider; do not promise free
   usage or choose a paid plan for them.
2. **Gemini — audio and visual inspection.**
   After the AssemblyAI step, say: “Next is video and audio analysis. Open
   [Google AI Studio's API keys page](https://aistudio.google.com/apikey), sign in, and create
   or choose a key for the project you want to use. I'll help if you see a project or permission
   question.” Use Google's [key setup guide](https://ai.google.dev/gemini-api/docs/api-key)
   for current project/key instructions. Do not ask for a service-account JSON file or admin key.
3. **Private entry and verification.**
   Run `acq-edit credentials` yourself (`node dist/cli.js credentials` in a built checkout).
   Say: “I've opened a small setup page. Paste the keys into their labeled boxes and click
   **Save keys**. I'll take care of the rest.” The installer also opens this page automatically.
   Keep the command running in a background tool session while the user fills the form.
   If the browser did not open, show the printed localhost link as a clickable link, or open it
   in the app browser. `--no-open` prints the link without launching the system browser.
   Never ask them to open a credential file, edit JSON, or run a command just to enter keys.
   Blank fields preserve saved keys. Cancel or expiry preserves previous credentials. After
   Save, the page closes its local server and the command reports only success, never values.
   A regular chat question box is not a secret-input field. Use the local password form as the
   default, including when someone asks for a little question box. Do not read, screenshot or
   inspect populated password fields. Do not copy keys into tool arguments, logs or chat replies.
   If a user already pasted a key in chat, don't repeat it; explain that chat is not private key
   storage and guide them to the local form. Optional `credentials --terminal` is only for users
   who explicitly prefer an interactive terminal; never use it as the nontechnical fallback.
   Then run `onboard verify` and `doctor`, interpret their results in plain language, and fix the
   specific failed step. A read check is not proof of billing balance or model-generation access.
4. **Already included.**
   Tell the user that the fonts, caption profiles, approved music and restricted editorial-brain
   connection come through the team bundle. They do not need a Supabase account or a
   separate OpenAI/Anthropic API key for the signed-in agent. Verify installation instead of
   asking them to rebuild styles or copy files from someone else's computer.
5. **Frame and Monday — required standard onboarding step.**
   Say: “Next we'll connect where your finished clips go: Frame for video review and Monday
   for tracking. Get the shared Adobe client ID and secret from Maddex—no new Adobe app
   needed. You will sign into your own Adobe account and use your own Monday API token.”
   → Use skill: [monday](../distribution/skills/monday/SKILL.md), starting with its onboarding
   reference. Run the credential form, Frame browser login, destination discovery and final
   read check yourself; the user signs in and pastes credentials. Never silently skip this.
   Full setup is **delivery pending** until `acq-edit onboard delivery` succeeds. If the user
   explicitly chooses local-only work, record “delivery deferred by user” in the interview
   checkpoint and continue that limited work; do not describe full onboarding as complete.
   Drive remains optional and is separate from this delivery step.

The installer currently collects both editing keys together. You can explain both account steps
first, then open the form. Do not claim a key was entered before the command reports success.
If dependencies are still being installed, the agent can open the same form directly with
`python3 scripts/credentials.py "${ACQ_EDIT_HOME:-$HOME/.config/acq-edit}"` from this repo.

### Help with common questions and failures

| User's situation | What to do next |
| --- | --- |
| “I only have Workbrew installed.” | Use its existing `brew`. The public tap does not need a GitHub account or private-package token. Do not demand a workspace ID. If company policy blocks a dependency or tap, identify that exact admin action. |
| “What do I pay for?” | Explain that editor licensing, the signed-in agent and transcription/video-analysis usage may have separate costs. Check current official pricing if asked; never promise a fixed price or approve charges. |
| Key rejected / 401 or 403 | Confirm which service failed, guide them back to its key/account page, then rerun private entry and the read check. Inspect account/project permissions if indicated; never print the stored key. |
| Rate limit / 429 / credit error | Explain which provider is limiting usage. Help inspect its usage/billing page or retry guidance; do not repeatedly submit paid jobs or silently switch providers. |
| Google key creation is unavailable | Use the current official key guide to identify project/organization permissions. Ask the user to involve their admin when required. |
| Premiere panel is missing | Follow the isolated panel installation and CEP instructions below. Preserve any open unrelated project. |
| An install failed or a lock remains | Read the recorded failed step and inspect its process. Preserve partial installs and working files; follow installation recovery rather than deleting or restarting blindly. |
| “Can I stop and come back?” | Save the non-secret checkpoint and give the exact next step. On return, read progress and continue without redoing successful connections. |

When connection pages change, check their official documentation rather than guessing button
names. Stay with the user through troubleshooting. If an action needs the user, explain why and
give a concrete action; do not leave them with “contact support” and no diagnostic context.

### When the session cannot run an installation command

Check the selected engine's prerequisites before downloading assets or building components.
The normal supported FilmCraft path downloads a verified runtime; do not tell users to install
Rust unless they explicitly chose `--source-build`. Never change their selected engine because
an installation step was blocked. A Premiere user does not need Rust.

Distinguish the actual command error from a session policy refusal. Quote or summarize the
specific failed action and its reported reason; do not infer “Workbrew is broken” or “admin access
is required” merely because a tool call failed. Use the current environment's supported approval
flow only when available. If the session cannot request permission, explain that once and do not
repeat the blocked command, switch package managers, use a second Homebrew or suggest bypassing
company policy.

For an allowed installation that only the user can run interactively, provide one exact command
using the detected managed `brew` path and the missing package. For example, if the user explicitly
chose a source build and the detected wrapper is `/opt/workbrew/bin/brew`, ask them to run
`/opt/workbrew/bin/brew install rust` in Terminal, then reply “done” or share the non-secret error.
If Terminal also reports a managed-policy denial, explain the exact admin action needed; do not
keep trying alternate installation routes. While waiting, preserve progress and keep the selected
engine pending. Continue only genuinely independent checks. After their reply, rerun the read-only
prerequisite check and resume the same engine. Never treat elapsed time as permission or completion.

### Finish with something usable

Summarize configured, read-verified, skipped and pending items in a short checklist. Once the
user supplies footage for a test, follow the repository's editing owners, render in the selected
engine and open the actual review URL. Explain how to leave a timecoded note and apply a revision.
Inspect the resulting revision and verify reopening after restart. Ask for their judgment of the
clip; technical checks do not count as their approval. If they want setup only, stop after setup
and clearly mark the first-clip test as pending.

## 1. Install through Homebrew or Workbrew

If Workbrew is already installed, use its existing `brew` command. Do not install another
Homebrew or bypass the managed command. The code, tap and release assets are public; no GitHub
account, `gh auth login` or private-package token is required. Company package policies still apply.

```sh
brew tap maddexritter-rgb/acq https://github.com/maddexritter-rgb/homebrew-acq.git
brew install maddexritter-rgb/acq/acq-edit
acq-edit version
acq-edit onboard guide
```

Open the installed folder shown by `guide` in Codex or Claude Code and say “Help me get set up.”
The agent then follows this guide and handles the commands while you sign in to the editing
services and enter your own API keys privately.

For a source checkout, use public Git (or Download ZIP on the GitHub page):

```sh
brew install git
git clone https://github.com/maddexritter-rgb/acq-edit.git
cd acq-edit
brew bundle --file=Brewfile
export PATH="$(brew --prefix node@24)/bin:$(brew --prefix python@3.11)/bin:$PATH"
python3.11 scripts/onboard.py guide
```

Open that checkout in your agent. Direct setup is `python3.11 scripts/onboard.py filmcraft codex`
(use `premiere` / `claude` when selected). In a checkout, use `node dist/cli.js` instead of
`acq-edit` for service commands after setup, and `python3.11 scripts/onboard.py status` for progress.
Never bypass company restrictions; explain any blocked dependency to the user and their admin.

If the owner makes releases private later, new downloads will require authorized access.
The asset downloader retains a `gh` fallback for that situation. Already downloaded copies are
not revoked by a visibility change. Public availability does not grant additional third-party licenses.

## 2. Choose one engine and agent

Ask which engine and signed-in agent to use, and where to keep projects. The default project
folder is `~/Movies/ACQ Edit`; an external SSD is optional. Existing projects retain their
backend and folder. Never borrow another machine's paths, private keys or running bridge.

```sh
acq-edit onboard filmcraft codex
# Or: acq-edit onboard premiere claude
```

Only FilmCraft and Premiere are included in this onboarding pilot. Resolve remains paused.
Use the current signed-in chat. Do not install or sign into another agent CLI. FilmCraft installs its pinned
headless runtime from a pinned prebuilt package on Apple-silicon Macs running macOS 15.7 or
later. Rust and Xcode build tools are not required for that runtime. Other architectures or
older macOS must be reported explicitly; never silently fall back to another editor or build.
A developer can explicitly choose `acq-edit onboard filmcraft codex --source-build`, which
requires Rust 1.95+ and Xcode Command Line Tools and can take longer than an edit.
Premiere must be installed and licensed separately; this release targets the tested 26.3 host.

Onboarding downloads the hash-pinned team bundle: 112 approved music files and indexes,
caption profiles for Alex/Leila/Sharran, the supplied caption fonts and dedicated read-only
editorial-brain access. One unavailable music catalog item remains excluded. Fonts are installed
in `~/Library/Fonts/ACQEdit`, with conflicts refused. Commercial fonts require the user's
applicable font license; the bundle does not grant one. Restart an already-open editor after
font installation. Font installation verifies every copied file; the caption owner also checks exact font faces before construction. No separate Supabase signup or brain-token entry is needed.

The shared helpers, verified skills and only the selected engine are installed into a
versioned per-user runtime. Progress survives ordinary errors. Interrupted partial installs
are retained for diagnosis, not silently replaced. If a lock remains after a crash, inspect
its recorded PID before reconciling it; never remove a live process's lock.

For Premiere, run:

```sh
acq-edit onboard premiere-panel
```

This installs only the separately identified ACQ Edit panel and refuses to replace a different
existing copy. For an existing toolkit panel, use `acq-edit --engine premiere onboard premiere-panel --update-owned`; it verifies ownership and preserves the old panel in a backup. Close/reopen the panel after replacement. Open **Window → Extensions → ACQ Edit Agent**. If the unsigned extension is
hidden, follow the host's CEP debug instructions in [ENGINES.md](ENGINES.md). Setup never
closes or changes an unrelated project. Upgrading a panel needs an explicit coordinated step.

## 3. Connect editing services

The installer opens a local page with password fields for these two personal keys.
Paste and click **Save keys**; blank keeps an existing key. The page expires after 15 minutes.

| Connection | Purpose | Where to get it |
| --- | --- | --- |
| AssemblyAI | Transcripts, word timings and speaker labels | [AssemblyAI dashboard](https://www.assemblyai.com/dashboard) |
| Gemini | Audio/visual inspection and audits | [Google AI Studio](https://aistudio.google.com/apikey) |
| Editorial brain | Current shared editorial guidance | Included restricted team reader; no user signup |
| Codex or Claude Code | Editing reasoning and job execution | Use the existing signed-in chat |

```sh
acq-edit onboard verify
acq-edit doctor
```

`verify` checks read access without uploading media. It does not prove sufficient credit,
model-specific access or generation. `doctor` checks local paths, asset hashes, helper/runtime
integrity and the selected engine connection. A successful install is not yet a successful
clip. Credential files are kept outside the repo under `~/.config/acq-edit` with mode 0600.
For optional Groq fallback/audits, configure that helper only if selected; it is not a primary
transcription or onboarding requirement. No third model-provider key is required for editing.

## 4. Connect Frame and Monday before completing onboarding

Ask which brands the user edits and guide Frame/Monday delivery setup by default. Default to shorts.
Reuse the included profiles; don't ask users to rebuild the approved caption styles.

For delivery, → Use skill: [monday](../distribution/skills/monday/SKILL.md).
The shipped owner handles Adobe Frame OAuth login, the user's Monday token, editor initials,
and exact Frame folder/Monday board routes for each brand. Commands:

```sh
acq-edit delivery credentials
acq-edit delivery login
acq-edit onboard delivery  # Verify identities and all saved destinations; record the checkpoint
acq-edit delivery status  # Read-only local readiness (never prints keys)
```

Read and save destination IDs using the owner's [route guide](../distribution/skills/monday/references/configuration.md).
Do not mark onboarding complete after merely saving tokens or opening sign-in. The final
check requires both identities, editor initials, and valid routes for every saved brand/format.
Setup checks identity and routes only. It does not upload clips, create board items or grant
permission for future deliveries. A later request such as “push these clips to Frame and Monday”
authorizes that selected batch. Preserve the delivery ledger for recovery and revisions.

### Pasted Google Drive footage links

Homebrew/Workbrew installs rclone with ACQ Edit; no separate downloader application is needed.
When the user supplies a Drive link, route it to footage-fetch. The agent handles commands:

1. Run `drive-status`. It checks the downloader and lists connection names without tokens.
2. With no connection, say “I'll open Google sign-in. Choose the account that can open
   this footage.” Run `drive-login`; the browser handles Google login. Newly created
   connections request read-only metadata and download access. Never ask for a password
   or an OAuth token in chat, or for a second Claude/Codex login.
3. One existing Drive connection is selected automatically. If there are multiple, ask
   which work connection to use, then run `drive-connect NAME`; remember it across both
   editors. Do not guess between personal and work accounts or overwrite existing remotes.
4. Run `drive PROJECT_ID "PASTED_URL"`. The same command accepts a file or folder link;
   folders recursively import supported video/audio files. Originals stay on Drive,
   verified project copies go to `00_SOURCE`, and interrupted transfers retain their records.

The user only needs to paste the link and, on first use, sign into Google if needed.
Account readiness does not prove access to every link: explain sharing restrictions,
expired access or organization OAuth policy specifically. Do not bypass those controls.
If rclone is missing or old, use the machine's existing Homebrew/Workbrew installation
through the normal allowed command flow. Do not replace another installation or loop on
blocked commands. Drive login can wait until first Drive use; it does not block local files.
YouTube uses the installed yt-dlp. Private content still needs the user's access.

## 5. Prove one real job, then use the review room

Show a short checklist with **configured / read-verified / pending / deferred by user** and any repair.
Always include Frame sign-in, Monday connection and brand destinations. A missing delivery
connection must remain visible; it must not disappear behind an “editing ready” summary.
Use `acq-edit onboard status` to resume. Ask for one source file or link and the desired clip.
Use the installed repository's `/edit` owners, fetch live guidance before design, and produce a
native render with the selected engine. Inspect the actual clip, then open the review room:

```sh
acq-edit serve
```

Keep that terminal/service running. Open the authenticated localhost URL printed by the command;
never assume another machine uses port 17352. Stop with Ctrl-C and restart with the same command.
Projects, feedback and immutable versions persist. `acq-edit projects` lists prior work.

The new-Mac acceptance is: installed from the pinned release, correct fonts and styled captions,
verified music, one native clip visible/playable in the room, one caption revision preserving cuts,
and successful reopening after restart. Record timings and bugs with `acq-edit version`, backend,
macOS/CPU architecture, failed step and redacted logs. Do not include credentials or login URLs.

The other chat's `vibe-editing` onboarding is the source for the delivery interview;
ACQ Edit is the authoritative engine/runtime for this test. Do not install the old editing pipeline
alongside it. Read-only checks and offline tests do not certify a new Mac or Workbrew-managed deployment.

## Agent execution and repair paths

After gathering the editor, agent and storage choices in chat, use:

```sh
acq-edit onboard filmcraft codex --non-interactive --storage-root "/Volumes/Your Drive/ACQ Edit"
```

Use `premiere` or `claude` when selected. This skips terminal configuration questions,
reusing the normal validator, configuration history and active-service lock. The private key
form and account sign-in still need the user. Never improvise scripts to write config after EOF.

Both engines can be installed: run onboarding once for each. Use `--engine premiere` or
`--engine filmcraft` on subsequent commands. Each engine has its own runtime, config and state;
assets, fonts and credentials are shared. The earlier single-engine configuration is adopted
in place, preserving its database and project paths. New jobs still ask the editor choice.

The launcher checks Node and certificate trust before downloads and supplies the same environment
to children. Company CA variables are preserved; invalid/missing bundles stop with a repair.
Never disable certificate verification. `doctor` checks the toolkit YouTube downloader, EJS solver
and selected Node. No session-created downloader wrapper is needed.

If a pinned runtime executable breaks, repair the underlying Homebrew/Workbrew dependency and
run `acq-edit onboard premiere codex --fresh-runtime --non-interactive` (or FilmCraft). This builds
a newly verified runtime, backs up config and retargets only paths owned by the old runtime;
it preserves storage, projects, custom paths and the old runtime. Stop/reconcile active work first.
Never hand-edit an alternate Premiere profile. Premiere discovery reports installed and observed
host versions from the compatibility registry. Premiere 26.3.0 and 26.5.2 are enabled.
Setup automatically binds to the running enabled Premiere, or the newest enabled installed
version if none is running. Keep the user's installed editor; do not require a downgrade,
separate qualification session, or FilmCraft switch for 26.5.2. The registry's
`enabled-native-verification-pending` status describes our release evidence; it is not a
setup blocker when `executionAllowed` and the live profile match are true. Continue ordinary
editing with the same source-linked/native readback, save and receipt checks. Report actual
operation failures specifically. Unknown versions remain disabled; never hand-edit profiles.

For the first clip, Premiere finishes in its editable timeline. FilmCraft finishes in its review
room with current-chat revision handoffs. `serve --no-worker` is explicitly **Review only**: notes
save, but revision buttons and API submission are disabled. A successful provider read check
is authentication evidence only. Gemini HTTP 402 means billing/credit is needed, not successful
analysis; do not mark audio/video inspection complete without an actual generation result.

## Teammate regression repairs — preview.12

Before engine onboarding, run `acq-edit media-check`. If neither FFmpeg tool nor an
FFmpeg formula is installed, run `acq-edit media-check --install-missing`. This uses
the existing Homebrew/Workbrew command. A present but broken/unlinked third-party
installation is preserved and reported for repair; do not uninstall it or trust a tap
automatically. If Homebrew requests tap trust, explain the exact tap and use its normal
user/admin decision. No `--ignore-dependencies` workaround or second Homebrew is needed.
The Brewfile and formula deliberately leave FFmpeg provisioning to this check.
The installer also executes both media binaries before expensive setup, on resume,
and the shared installer checks again after dependency changes.

The browser key form opens only when keys are missing. Both editor installations reuse
the shared credential store. Use `--reenter-keys` on engine onboarding or the explicit
`credentials` command to replace keys. Presence does not prove valid keys or available
credit; keep `onboard verify` and provider-generation status distinct.

After an explicit local-only choice, pass `--defer-delivery` to engine onboarding.
This records `editing-configured-delivery-deferred`, skips the delivery forms and permits
local editing. It never claims full onboarding or upload readiness. Cancellation is not
this choice and is never silently converted to deferral. Resume accounts/routes with
`delivery credentials`, `delivery login`, the monday owner's destination steps, and
`onboard delivery`. Re-running engine onboarding without the flag resumes delivery.

Normal onboarding and editing use the current chat. Do not open another Claude/Codex
CLI, request another login, run an agent smoke test, or demand saved command approvals.
`doctor` checks editing dependencies without requiring an agent CLI.
Separate agent workers and their login/smoke-test setup are removed. Do not offer a CLI
setup or ask the user to open a terminal or type commands. Execute internal toolkit
commands from this chat; users only supply choices, browser sign-ins and review feedback.
See [CLAUDE_SETUP.md](CLAUDE_SETUP.md). Normal host permission prompts still apply.
