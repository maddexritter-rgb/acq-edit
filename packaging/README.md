# Homebrew / Workbrew release

The private `maddexritter-rgb/homebrew-acq` tap installs a versioned source release.
Use the existing `brew` wrapper on Workbrew machines. Do not install a second Homebrew.
The formula installs shared tools but does not open editors, install user fonts, fetch
team assets, collect credentials or configure a particular user during package installation.
`acq-edit onboard` performs those steps in the signed-in user's account.

The tap authenticates release downloads using GitHub's API. Ordinary Homebrew installs can use
`gh auth login`; all Workbrew-managed package installs (including interactive ones) need the admin's secret
`HOMEBREW_GITHUB_API_TOKEN` with read-only Contents access to the release repository.
Private tap discovery additionally requires the Workbrew GitHub integration to have access
to the tap. Account/organization policies may require administrator provisioning.
See https://workbrew.com/docs/authenticate-private-formula-artifacts .

Never include personal keys in a formula. Each user signs into their own media and delivery
services. The private team bundle carries only the preauthorized restricted brain reader.

Release source is installed under libexec, copied once into a versioned per-user directory,
and never executed with mutable editor state inside a Homebrew Cellar. Upgrades preserve
previous runtime directories, project files and credentials. A new runtime requires explicit
onboarding. Premiere panel replacement is never automatic.
