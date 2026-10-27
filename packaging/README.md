# Homebrew / Workbrew release

The public `maddexritter-rgb/homebrew-acq` tap installs a hash-pinned source release through
Homebrew's standard downloader. No GitHub account or API token is required. Use the existing
Workbrew `brew` wrapper on managed Macs; company package policies still apply.

The formula installs shared tools but does not open editors, install user fonts, fetch team
assets, collect credentials or configure a particular user during package installation.
`acq-edit onboard guide` locates the installed workspace for Codex or Claude Code. The agent
follows the shared onboarding contract, and `acq-edit onboard` setup runs as the signed-in user.

Source is copied into a versioned per-user directory. Upgrades preserve previous runtimes,
projects and credentials. A new runtime requires explicit onboarding; Premiere panel replacement
is never automatic. Personal model-provider credentials stay local. The owner-authorized public
team bundle includes music, fonts, profiles and the restricted editorial-brain reader.

If repository visibility changes back to private, update download/authentication instructions
and the formula accordingly before promising new installations. Visibility changes do not revoke
previously downloaded releases or their embedded reader token. The old private download strategy
is retained as compatibility reference but is not used by the current public formula.
