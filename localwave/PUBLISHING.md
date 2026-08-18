# LocalWave update publishing pipeline

LocalWave updates are published as **pre-signed APKs**. The APK signing key is never stored in this repository and is never required by GitHub Actions.

## Trust model

A release is accepted by the publishing workflow only after all of these checks pass:

1. Staged transport data reconstructs without error.
2. The unsigned build artifact and compressed signing tail each match their advertised SHA-256 values.
3. The reconstructed signed APK SHA-256 exactly matches `READY.json`.
4. Android `apksigner` verifies the reconstructed APK.
5. The signer certificate SHA-256 is exactly:
   `34d98c603a2a2c54777c0065ecc3e38c3a4162d4f37d09ae137d004654d39a72`
6. Android package ID is exactly `app.localwave.player`.
7. APK `versionCode` exactly matches the staged manifest.
8. `versionCode` is newer than the version currently advertised by `localwave/latest.json`.

Only after those checks does the workflow commit the APK under:

`localwave/releases/v<VERSION>/LocalWave-v<VERSION>.apk`

and replace `localwave/latest.json` with the new version, raw GitHub download URL, SHA-256, and release notes.

The Android app independently repeats its own download hash, package, version, and signing-certificate checks before opening PackageInstaller.

## Normal transport

Normal releases use `transportMode: unsigned-artifact-tail`.

The unsigned aligned APK comes from the private GitHub Actions build artifact and is independently SHA-256 checked. Local signing is then represented by a small gzip-compressed signed tail plus the exact common-prefix byte count. GitHub reconstructs the signed APK as:

`unsigned_apk[:prefixBytes] + gzip_decompress(signed_tail)`

The final result must match the expected signed APK SHA-256 and pass `apksigner`, certificate pinning, package-ID, and version checks before publication.

This keeps the LocalWave private signing key completely outside GitHub while avoiding transport of the entire signed APK through text tooling.

## Fallback transport

`full-base64` remains supported as a fallback for small payloads and dry-run testing.

## Release trigger

Upload all staging payload files first. Create `localwave/staging/READY.json` last. A push affecting that file triggers `.github/workflows/publish-localwave-update.yml`.

The workflow publishes atomically and removes the entire staging directory in its own `[skip ci]` commit, preventing a cleanup-trigger loop.

## Dry-run test

Set `"dryRun": true` in `READY.json` to test staging, reconstruction, SHA verification, repository write permission, and cleanup without publishing an APK or modifying `latest.json`.

A successful dry run writes `localwave/pipeline-status.json`.
