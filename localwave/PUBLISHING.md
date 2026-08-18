# LocalWave update publishing pipeline

LocalWave updates are published as **pre-signed APKs**. The APK signing key is never stored in this repository and is never required by GitHub Actions.

## Trust model

A release is accepted by the publishing workflow only after all of these checks pass:

1. The staged Base64 parts reconstruct without error.
2. The reconstructed file is at most 100 MiB and has APK/ZIP magic.
3. Its SHA-256 exactly matches `READY.json`.
4. Android `apksigner` verifies the APK.
5. The signer certificate SHA-256 is exactly:
   `34d98c603a2a2c54777c0065ecc3e38c3a4162d4f37d09ae137d004654d39a72`
6. Android package ID is exactly `app.localwave.player`.
7. APK `versionCode` exactly matches the staged manifest.
8. `versionCode` is newer than the version currently advertised by `localwave/latest.json`.

Only after those checks does the workflow commit the APK under:

`localwave/releases/v<VERSION>/LocalWave-v<VERSION>.apk`

and replace `localwave/latest.json` with the new version, raw GitHub download URL, SHA-256, and release notes.

The Android app independently repeats its own download hash, package, version, and signing-certificate checks before opening PackageInstaller.

## Preparing a release

First build and sign the APK outside GitHub using the existing LocalWave release key.

Then run:

```bash
python3 localwave/tools/make_staging.py \
  /path/to/LocalWave-v0.2.2.apk \
  5 \
  0.2.2 \
  --notes "Release notes here"
```

This creates:

```text
localwave/staging/
├── parts/
│   ├── part-0000.b64
│   ├── part-0001.b64
│   └── ...
└── READY.json
```

Commit/upload **all `parts/part-*.b64` files first**. Commit/upload `READY.json` last. A push affecting `localwave/staging/READY.json` triggers `.github/workflows/publish-localwave-update.yml`.

The workflow publishes atomically and removes the staging directory in its own `[skip ci]` commit, preventing a cleanup-trigger loop.

## Why Base64 staging exists

The ChatGPT GitHub connector can reliably write UTF-8 repository files but does not expose GitHub Release binary-asset uploads. Base64 staging bridges that transport limitation. GitHub Actions reconstructs the exact already-signed APK, verifies it, and commits the real binary file. LocalWave itself downloads the final `.apk`; it never downloads or reconstructs the staging chunks.

## Dry-run test

Set `"dryRun": true` in `READY.json` to test the staging, reconstruction, SHA verification, repository write permission, and cleanup path without publishing an APK or modifying `latest.json`.

A successful dry run writes `localwave/pipeline-status.json`.
