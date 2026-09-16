# X2D APK update compatibility

All X2D APKs use the persistent signing key `.github/x2d-debug.keystore.b64` and an increasing Android `versionCode`.

CI verifies the finished APK certificate with `apksigner` against that persistent key and verifies the packaged versionCode with `aapt` before publishing. A mismatch fails the workflow.

Do not regenerate or replace the persistent signing key. Android requires the same certificate for in-place updates.
