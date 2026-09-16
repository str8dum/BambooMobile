# X2D APK update compatibility

The X2D build pipeline uses `.github/x2d-debug.keystore.b64` as its persistent Android signing identity and forces an increasing Android `versionCode` with `scripts/apply_x2d_version_code.py`.

Before publishing, CI verifies the finished APK certificate against that key using `apksigner` and verifies the packaged versionCode using `aapt`. A mismatch fails the workflow.

Never replace or regenerate the persistent signing key. Android requires the same signing certificate for in-place APK updates.
