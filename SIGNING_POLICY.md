# X2D APK update compatibility

The X2D workflows use `.github/x2d-debug.keystore.b64` as the persistent Android signing key and install it as `$HOME/.android/debug.keystore` before every build.

Every build receives a monotonically increasing Android `versionCode` via `scripts/apply_x2d_version_code.py`.

Before an APK artifact is uploaded, CI verifies both the APK signing certificate and packaged versionCode. If either check fails, the build fails instead of publishing an APK that cannot update the established installation.

Do not regenerate or replace `.github/x2d-debug.keystore.b64`; doing so changes the Android signing identity and requires an uninstall.
