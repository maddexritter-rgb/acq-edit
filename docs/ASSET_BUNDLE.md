# Versioned asset bundles

Skills and code remain in Git. Audio, fonts and profiles are installed into a separate versioned asset directory. The skill runtime pins that directory; music catalogs use relative paths and never fall back to a personal review folder.

Use `python3 scripts/asset_bundle.py build-local --music MUSIC_ROOT --decisions REVIEW_JSON --target NEW_DIRECTORY --version VERSION --font FONT --profile PROFILE` to prepare a local evaluation bundle. Only reviewed Keep entries with existing files are included. Missing approved files are recorded as unavailable. Existing approval, blacklist, acoustic and semantic evidence is retained; the builder does not approve tracks or grant redistribution rights.

Use `python3 scripts/asset_bundle.py install SOURCE NEW_DIRECTORY` to install a supplied bundle, and `verify DIRECTORY` to verify hashes. Pass that installed directory as `--assets` to engine installation. Doctor checks it through the runtime receipt before reporting local readiness.

Local evaluation bundles explicitly lack established redistribution rights. They must not be uploaded as team releases. A distributable release requires documented asset-specific permissions and notices; authenticated release delivery remains pending that inventory. Native fonts may additionally require installation through their licensed provider. This tooling does not certify font licensing or editorial quality.
