# LocalWave Update Channel

This folder is the public stable update feed for the LocalWave Android music player.

## Feed

`latest.json` is read by LocalWave over HTTPS. The app compares `versionCode` with its installed version.

Before an update is handed to Android's PackageInstaller, LocalWave verifies:

1. The downloaded APK SHA-256 matches `latest.json`.
2. The APK package name is `app.localwave.player`.
3. The APK version is newer than the installed version.
4. The downloaded APK is signed by the same certificate as the installed LocalWave app.

Current LocalWave signing certificate SHA-256:

`34:D9:8C:60:3A:2A:2C:54:77:7C:00:65:EC:C3:E3:8C:3A:41:62:D4:F3:7D:09:AE:13:7D:00:46:54:D3:9A:72`

## Publishing a future update

1. Build and sign the new APK with the existing LocalWave signing key.
2. Increment Android `versionCode`.
3. Upload the signed APK as a GitHub Release asset at the URL used in `latest.json`.
4. Compute the signed APK SHA-256.
5. Update `latest.json` only after the APK asset is live.

Never commit the LocalWave private signing key or its password to this repository.
