# Update ACQ Edit without losing work

Ask the existing Claude Code or Codex chat to update the installation. The agent handles
commands; no terminal or second agent login is required.

For Homebrew/Workbrew, use the existing package manager to update the tap and upgrade
`maddexritter-rgb/acq/acq-edit`. Then read the new package's onboarding guide and resume each
installed engine using the saved settings. A package upgrade alone does not replace every
registered engine runtime or skill link. Preserve credentials, assets, original footage,
projects and feedback. Refresh receipt-owned discovery links with `--update-owned` and verify
scope: personal for Claude, workspace for Codex unless the user chose otherwise.
If the prior runtime has local edits, preserve it and explain the exact conflict before moving links.
For Google Drive, use drive-status; reuse a valid connection, otherwise guide drive-login
in the browser and verify the connection. Google permission does not follow from Adobe login.

## Team customization

Editing clips and changing project-specific settings does not require changing toolkit code.
Keep those in the project/configuration locations outside the installed package.

For changes to skills, helpers or toolkit code, use a separate Git fork/branch with commits.
Keep the main ACQ repository as upstream, fetch its updates, and merge or rebase them into
the custom branch with conflict review and tests. Changes do not automatically return to
Maddex's repository; send a pull request if they should be shared. Never force-reset or discard
uncommitted changes to make an update pass. Capture changes from an installed runtime before
moving to a maintained fork; do not edit Homebrew's Cellar or verified materialized skills in place.

Release installations deliberately verify code hashes. Custom forks must regenerate and validate
the affected distribution manifests using the repository contributor workflow, then use a fresh
runtime; never disable hash checks to accept customized code. Shared editorial-brain publication
permissions are separate and are not granted by changing local skills.

## Prompt for an existing teammate

> Update my existing ACQ Edit installation to preview.17 or newer from
> https://github.com/maddexritter-rgb/acq-edit. Handle the update in this Claude Code chat;
> do not open another agent session, require a Claude CLI login, or send me to a terminal.
> Detect whether I use Homebrew/Workbrew or a Git checkout and follow that update path.
> Preserve keys, footage, projects, feedback and local customizations. If local code is
> modified, preserve it on a branch/backup and explain any merge conflict; do not reset it.
> Read the new installed package's onboarding guide, resume the selected engine runtimes
> with my saved settings, and refresh only toolkit-owned skill links.
> Register and check exactly edit, assembly-design, horizontal-to-vertical, caption-clips,
> music and monday for Claude using personal scope and --update-owned. Keep unrelated
> skills intact. Verify the actual slash menu; if it needs refreshing, guide me to reopen
> the current app session without launching another CLI. Don't claim menu visibility from
> filesystem checks alone.
> Set up Google Drive link intake through the repository: check drive-status, reuse my
> connection if valid, otherwise run drive-login and guide my Google sign-in in the browser.
> Verify the connection and tell me when I can paste a file/folder link. Private footage
> requires permission on the Google account I connect. Never ask me to paste OAuth tokens.
> Confirm the version, selected editor, six skill registration results, Drive connection
> result, and any remaining blocker. Don't render or upload a test clip without asking.
