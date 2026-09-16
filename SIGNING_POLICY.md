# X2D APK update compatibility

X2D builds use `.github/x2d-debug.keystore.b64` as the persistent signing identity and an increasing Android `versionCode`. CI verifies both the completed APK certificate and packaged versionCode before uploading an artifact. Never regenerate or replace the signing key.
