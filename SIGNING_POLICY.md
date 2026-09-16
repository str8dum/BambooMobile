# X2D APK signing/update policy

All X2D test and audited APKs must use `.github/x2d-debug.keystore.b64` as the persistent Android debug signing key. Workflows install it as `$HOME/.android/debug.keystore` before building.

Every build must use a monotonically increasing Android `versionCode`. `scripts/apply_x2d_version_code.py` patches the generated Android Gradle file before the Tauri Android build.

Both workflows verify the finished APK certificate against the persistent keystore with `apksigner` and verify the packaged versionCode with `aapt`. A certificate or version mismatch fails CI and prevents a bad artifact from being published.

Changing or regenerating `.github/x2d-debug.keystore.b64` will break update compatibility and must not be done.
