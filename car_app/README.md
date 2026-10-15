# Android app

Flutter app for vehicle maintenance, learning guides, emergency assistance, and
scoped AI chat. Guests can use bundled emergency guides and local incident records.
Accounts enable personal vehicles, maintenance records, progress, and chat.

## Run

Install Flutter with Dart compatible with `^3.11.5` and Android SDK tools.
Start the backend using the [root setup](../README.md), then run from this directory:

```powershell
flutter pub get
flutter devices
flutter run -d <android-device-id> --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` reaches the host backend from a standard Android emulator. For a physical
phone, use a reachable LAN address with `BACKEND_HOST=0.0.0.0`, or configure
`adb reverse` for USB access. `API_BASE_URL` is supplied at build time; Flutter does
not read the root `.env`. Release account access requires HTTPS.

## Check and build

```powershell
flutter analyze
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

APK: `build/app/outputs/flutter-apk/app-debug.apk`.

AI requires the backend and RAG service. Nearby workshop search requires connectivity
and a backend `GOOGLE_PLACES_API_KEY`; bundled emergency guides work offline.
