# X2D APK update compatibility

All X2D APKs use the persistent repository signing key `.github/x2d-debug.keystore.b64`.

Every build receives a monotonically increasing Android `versionCode` using `scripts/apply_x2d_version_code.py`.

The workflows verify the finished APK with `apksigner`, compare its SHA-256 signing-certificate digest to the persistent keystore, and verify the packaged `versionCode` with `aapt` before publishing. A mismatch fails CI.

Never regenerate, replace, or remove the persistent keystore. Android update compatibility depends on keeping this certificate unchanged.
