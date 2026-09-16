# X2D APK update compatibility

All X2D APKs are signed with the persistent repository key `.github/x2d-debug.keystore.b64`, installed as `$HOME/.android/debug.keystore` before the Android build.

Every build gets a monotonically increasing Android `versionCode` through `scripts/apply_x2d_version_code.py`.

Before publishing, CI uses `apksigner` to verify the APK certificate matches the persistent key and `aapt` to verify the packaged versionCode. Any mismatch fails the workflow, so an incorrectly signed or stale-version APK is not published.

Do not regenerate, replace, or remove `.github/x2d-debug.keystore.b64`; Android cannot install an APK signed by a different certificate over an existing installation.
