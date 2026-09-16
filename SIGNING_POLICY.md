# X2D APK update compatibility

The X2D test and audited workflows use `.github/x2d-debug.keystore.b64` as the persistent Android signing key. The key is installed as `$HOME/.android/debug.keystore` before every build.

Every build receives a monotonically increasing Android `versionCode` using `scripts/apply_x2d_version_code.py`.

CI verifies the finished APK certificate with `apksigner` against the persistent keystore and verifies the packaged `versionCode` with `aapt` before uploading the artifact. A mismatch fails the workflow.

Never regenerate or replace `.github/x2d-debug.keystore.b64`. A different signing certificate cannot update an app installed with the established certificate.
