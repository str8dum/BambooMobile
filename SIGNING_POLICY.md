# X2D APK update compatibility

X2D APKs use `.github/x2d-debug.keystore.b64` as the persistent signing identity. Each build also receives an increasing Android versionCode through `scripts/apply_x2d_version_code.py`.

CI verifies the completed APK signing certificate with `apksigner` against that key and verifies its packaged versionCode with `aapt` before publishing. Any mismatch fails the build.

Never replace or regenerate the persistent signing key; Android requires the same certificate for an in-place update.
