# Set up ACQ Edit on a new Mac

Open this repo in Codex or Claude Code and say:

> Set up ACQ Edit for me. Follow docs/ONBOARDING.md, ask one question at a time,
> save my progress, and use only this repository's editing skills.

The agent does the setup; you sign in and enter your own keys in private terminal prompts.
There is no separate Anthropic or OpenAI API key requirement. Use your signed-in Codex or
Claude Code account. Never paste API keys into the chat.

## 1. Install through Homebrew or Workbrew

If Workbrew is already installed, use its existing `brew` command. Do not install another
Homebrew or bypass the managed command. Your admin may need to allow the private tap.

```sh
brew install gh
gh auth login
gh auth setup-git
brew tap maddexritter-rgb/acq https://github.com/maddexritter-rgb/homebrew-acq.git
brew install maddexritter-rgb/acq/acq-edit
acq-edit version
```

For ordinary Homebrew, sign into a GitHub account with access to both private repositories
(`acq-edit` and `homebrew-acq`). Release downloads use that GitHub authentication.

**Workbrew private-package authentication:** Workbrew runs installations as its service user.
The editor's `gh auth login` does not by itself authenticate that service user. An admin must
connect/allow the private tap and configure its read-only release-download credential as
described in [packaging](../packaging/README.md). This applies to interactive Workbrew installs
too, not just fleet deployment. [Workbrew's authentication guide](https://workbrew.com/docs/authenticate-private-formula-artifacts).

If that private tap has not been provisioned, use the supported user-checkout installation:
Workbrew installs the standard dependencies, while your own GitHub login downloads the private
source and assets. This does not need a shared credential in Workbrew:

```sh
brew install gh git
gh auth login
gh auth setup-git
gh repo clone maddexritter-rgb/acq-edit
cd acq-edit
brew bundle --file=Brewfile
export PATH="$(brew --prefix node@24)/bin:$(brew --prefix python@3.11)/bin:$PATH"
python3.11 scripts/onboard.py filmcraft codex
```

Use `premiere` / `claude` instead when those are the selected tools. In this source flow, run
`node dist/cli.js serve` for the review room and `python3.11 scripts/onboard.py status` to resume
setup. The agent can run these from the checkout; no global launcher is required. Never bypass
company restrictions: if a policy blocks any required dependency or source access, ask the admin.

For a source checkout instead, run `brew bundle --file=Brewfile`, add Homebrew's `node@24`
`bin` directory to PATH if Node is not found, then `python3.11 scripts/onboard.py filmcraft codex`.
The source installation uses `node dist/cli.js` in place of `acq-edit` for service commands.

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

Onboarding downloads the hash-pinned private bundle: 112 approved music files and indexes,
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
