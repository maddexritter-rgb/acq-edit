# Versioned asset bundles

Skills and code remain in Git. Audio, fonts and profiles are installed into a separate versioned asset directory. The skill runtime pins that directory; music catalogs use relative paths and never fall back to a personal review folder.

Use `python3 scripts/asset_bundle.py build-local --music MUSIC_ROOT --decisions REVIEW_JSON --target NEW_DIRECTORY --version VERSION --font FONT --profile PROFILE` to prepare a local evaluation bundle. Only reviewed Keep entries with existing files are included. Missing approved files are recorded as unavailable. Existing approval, blacklist, acoustic and semantic evidence is retained; the builder does not approve tracks or grant redistribution rights.

Use `python3 scripts/asset_bundle.py install SOURCE NEW_DIRECTORY` to install a supplied bundle, and `verify DIRECTORY` to verify hashes. Pass that installed directory as `--assets` to engine installation. Doctor checks it through the runtime receipt before reporting local readiness.

Local evaluation bundles explicitly lack established redistribution rights. They must not be uploaded as team releases. A distributable release requires documented asset-specific permissions and notices. Native fonts may additionally require installation through their licensed provider. This tooling does not certify font licensing or editorial quality.

An owner's explicit authorization can establish music permission for a private team bundle. Record that authorization against the exact asset hashes in the release's private rights manifest; it does not grant permission for unrelated fonts or public redistribution. Preserve the old bundle and issue a new version rather than changing its signed inventory. A bundle containing fonts whose distribution permission is unresolved remains local-only even when its music is authorized.

## Private music download

The `music-2026.10.26.1` GitHub release supplies 112 approved music files with Keep
decisions, blacklist/rules, acoustic sections and semantic embeddings. It contains
no fonts or brand profiles. One catalog item with missing bytes remains explicitly
listed as unavailable in `asset-bundle.json`. Access requires repository membership.
This is a music asset release, not a declaration that the team pilot is complete.

From the repository checkout, download into a new directory:

```sh
mkdir -p .local/downloads/music-2026.10.26.1
gh release download music-2026.10.26.1 --repo maddexritter-rgb/acq-edit \
  --pattern 'acq-edit-music-2026.10.26.1.tar.gz' --pattern SHA256SUMS \
  --dir .local/downloads/music-2026.10.26.1
(cd .local/downloads/music-2026.10.26.1 && shasum -a 256 -c SHA256SUMS)
tar -xzf .local/downloads/music-2026.10.26.1/acq-edit-music-2026.10.26.1.tar.gz \
  -C .local/downloads/music-2026.10.26.1
python3 scripts/asset_bundle.py verify \
  .local/downloads/music-2026.10.26.1/acq-edit-music-2026.10.26.1
```

Use the verified bundle path as the asset root for a fresh music-skill installation.
It does not replace an existing complete bundle or supply required finishing fonts.
Existing installations retain their pinned asset root until explicitly upgraded.

Maintainers can issue a new private music-only bundle with
`asset_bundle.py build-private-music SOURCE NEW_DIRECTORY --version VERSION --authorization GRANT.json`.
The grant requires `scope: private-team-music`, `authorizedBy`, `date`, and `statement`.
The resulting `MUSIC_RIGHTS.json` binds that authorization to exact file hashes.
Keep these private asset manifests in the release bundle, outside Git history.

## New-Mac preview bundle

The onboarding release pins `team-assets-2026.10.27.2` by archive and manifest SHA-256.
It contains the approved music catalog plus 12 caption fonts, all three caption profiles,
owner installation authorization/notices, and the dedicated team read-only gateway reader.
No personal provider or delivery keys are included. The bundle is a private release asset,
not tracked source. `scripts/build_team_bundle.py` records the exact inputs and authorization;
it never uploads anything. `acq-edit onboard` downloads, verifies, safely extracts and installs it.
Commercial fonts retain their provider licensing requirements; owner-requested installation
packaging does not grant third-party redistribution rights. Old bundles remain immutable.
