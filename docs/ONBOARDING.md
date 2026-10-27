# Set up ACQ Edit on a new Mac

Open this repo in Codex or Claude Code and say:

> Set up ACQ Edit for me. Follow docs/ONBOARDING.md, ask one question at a time,
> save my progress, and use only this repository's editing skills.

After a Homebrew/Workbrew installation, run `acq-edit onboard guide` to find the installed
folder and a ready-to-paste request for your agent. Open that folder in Codex or Claude Code.

The agent does the setup; you sign in and enter your own keys in private terminal prompts.
There is no separate Anthropic or OpenAI API key requirement. Use your signed-in Codex or
Claude Code account. Never paste API keys into the chat.

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
  terms acceptance and hidden credential entry. Do not ask a nontechnical user to edit JSON.
- After each check, say what worked and what is next. Be specific: “The transcription connection
  works. Next we'll connect video analysis.” Avoid saying “everything is ready” before testing it.
- Keep setup progress across interruptions. Read `onboard status`, saved configuration and
  connection-check results; use presence/status checks for credentials without displaying them.
  Keep a brief non-secret interview checkpoint at `~/.config/acq-edit/onboarding-interview.json`
  (or the configured `ACQ_EDIT_HOME`): engine, agent, storage, brands, optional connections,
  current step and next action. Never store keys, account responses or login URLs in that file.
  Installer progress remains in `.local/onboarding.json`; do not edit its completed-step ledger.
- If an earlier session is already configured, summarize the remaining steps and resume there.
  Setup requests authorize routine installation, not purchases, unrelated editor changes or uploads.

### Walk the user through connections

First confirm the chosen engine and project storage, then follow the installation steps below.
Use FilmCraft or Premiere for this pilot; Resolve is paused. Once prerequisites are ready,
run onboarding in a terminal the user can interact with. Before its credential prompts, explain:

1. **AssemblyAI — transcription and word timing.**
   Say: “First we'll connect transcription so the editor can find and cut exact spoken words.
   Open the [AssemblyAI dashboard](https://www.assemblyai.com/dashboard), sign in or create an
   account, and find your API key. Let me know when you have it—don't paste it into this chat.”
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
   Say exactly where to paste each key: the matching hidden terminal prompt in the installer,
   or `acq-edit credentials` if setup already ran (`node dist/cli.js credentials` in a checkout).
   Explain that typed/pasted characters are hidden and that Enter submits; blank preserves an
   existing key. If your tool cannot offer a user-interactive terminal, give them that single
   command to run locally and wait for “done.” Never collect secrets through chat, tool arguments,
   shell history or a feedback form. If a key was accidentally pasted into chat, don't repeat it;
   guide the user to replace it at the provider and enter the replacement privately.
   Then run `onboard verify` and `doctor`, interpret their results in plain language, and fix the
   specific failed step. A read check is not proof of billing balance or model-generation access.
4. **Already included.**
   Tell the user that the fonts, caption profiles, approved music and restricted editorial-brain
   connection come through the team bundle. They do not need a Supabase account or a
   separate OpenAI/Anthropic API key for the signed-in agent. Verify installation instead of
   asking them to rebuild styles or copy files from someone else's computer.
5. **Optional connections, after the essentials.**
   Ask about Drive only if they want Drive footage. Ask about Frame/Monday only if they want
   delivery. They can skip both for a local-file first clip. Follow the existing owners below;
   do not invent a second connection or delivery workflow.

The installer currently collects both editing keys together. You can explain both account steps
first, then bring the user to the two hidden prompts. Do not leave a prompt waiting for an answer
that only the agent can supply, and do not claim a key was entered before checking the result.

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
Install and sign into the chosen agent CLI before continuing. FilmCraft builds its pinned
headless runtime locally; if requested by preflight, run `brew install rust` and
`xcode-select --install`, then repeat onboarding. This first build can take longer than an edit.
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
existing copy. Open **Window → Extensions → ACQ Edit Agent**. If the unsigned extension is
hidden, follow the host's CEP debug instructions in [ENGINES.md](ENGINES.md). Setup never
closes or changes an unrelated project. Upgrading a panel needs an explicit coordinated step.

## 3. Connect editing services

The installer prompts privately for these two personal keys. Blank keeps an existing key.

| Connection | Purpose | Where to get it |
| --- | --- | --- |
| AssemblyAI | Transcripts, word timings and speaker labels | [AssemblyAI dashboard](https://www.assemblyai.com/dashboard) |
| Gemini | Audio/visual inspection and audits | [Google AI Studio](https://aistudio.google.com/apikey) |
| Editorial brain | Current shared editorial guidance | Included restricted team reader; no user signup |
| Codex or Claude Code | Editing reasoning and job execution | Sign into the selected CLI |

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

## 4. Optional connections — reuse the other onboarding work

Ask which brands the user edits and whether they want Frame/Monday delivery. Default to shorts.
Reuse the included profiles; don't ask users to rebuild the approved caption styles.

For delivery, → Use skill: [monday](../distribution/skills/monday/SKILL.md).
The shipped owner handles Adobe Frame OAuth login, the user's Monday token, editor initials,
and exact Frame folder/Monday board routes for each brand. Commands:

```sh
acq-edit delivery credentials
acq-edit delivery login
acq-edit delivery check
```

Read and save destination IDs using the owner's [route guide](../distribution/skills/monday/references/configuration.md).
Setup checks identity and routes only. It does not upload clips, create board items or grant
permission for future deliveries. A later request such as “push these clips to Frame and Monday”
authorizes that selected batch. Preserve the delivery ledger for recovery and revisions.

For Drive intake, use `rclone config` to sign into the user's own Drive, then record the remote
name. YouTube uses the installed `yt-dlp`; authenticated/private content needs the user's access.
These connections can be skipped for a local-file test. There is no publishing-account requirement.

## 5. Prove one real job, then use the review room

Show a short checklist with **configured / read-verified / pending / skipped** and any repair.
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

The other chat's `vibe-editing` onboarding is the source for the optional delivery interview;
ACQ Edit is the authoritative engine/runtime for this test. Do not install the old editing pipeline
alongside it. Read-only checks and offline tests do not certify a new Mac or Workbrew-managed deployment.
