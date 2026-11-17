# Android app

The Flutter app provides maintenance records, learning guides, AI chat, and roadside assistance. It connects to the Mac backend through Tailscale.

If the app is already installed, start the backend using the [main README](../README.md), connect Tailscale on the phone, and open MyRoadie. Flutter and USB are only needed when building or installing the app.

## Set up development

Install Flutter with **Dart >=3.11.5 and <4.0.0**, Android Studio with the Android SDK, and JDK 17. Add Flutter to `PATH`.

```bash
flutter doctor -v
flutter doctor --android-licenses
```

Connect an Android phone with USB debugging enabled, or start an Android emulator. Check it with `flutter devices`.

The launcher reads these public settings from the root [app.config.json](../app.config.json):

- `API_BASE_URL`: Mac backend HTTPS address, without the dashboard's `:8443` port.
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

On Windows, the mobile launcher also needs a root `.venv`. Use Python 3.12 from the OCR setup, or your existing environment. If `.venv` does not exist, create it from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install python-dotenv
```

Then install the Flutter packages and run:

```powershell
Push-Location mobile
flutter pub get
Pop-Location
.\start-mobile.cmd
```

On a Mac with the main Python environment already installed, use `.venv/bin/python scripts/run.py mobile`. Add `-d DEVICE_ID` to either launcher if needed. The launchers pass the public settings to Flutter automatically.

## Build an APK

Run this PowerShell block from the project root:

```powershell
$publicConfig = Get-Content app.config.json -Raw | ConvertFrom-Json
Push-Location mobile
try {
    flutter pub get
    flutter build apk --release `
        "--dart-define=API_BASE_URL=$($publicConfig.API_BASE_URL)" `
        "--dart-define=SUPABASE_URL=$($publicConfig.SUPABASE_URL)" `
        "--dart-define=SUPABASE_PUBLISHABLE_KEY=$($publicConfig.SUPABASE_PUBLISHABLE_KEY)"
} finally {
    Pop-Location
}
```

The APK is `mobile/build/app/outputs/flutter-apk/app-release.apk`. Install it with `adb install -r` followed by that path, or transfer it to the phone.

The current Gradle configuration signs release builds with the debug key. Configure a release key before distributing the app, and keep the same key when updating an existing installation.

## Live logs

Rebuild and run the updated Flutter app to enable its `MOBILE` source header; an older installed APK may still appear as `UNKNOWN`. Debug builds log actual HTTP outcomes through the shared API client and Supabase transport. Each line has an anonymous guest/authentication session label. It changes on sign-in/sign-out and is not persisted. Release builds do not print these debug logs.

On the Mac, use `./scripts/logs.sh --mobile` from the project root. Requests reaching FastAPI appear even without a USB connection. To also see timeouts, connection failures, external downloads, and direct Supabase requests:

1. Install Android SDK platform-tools on the Mac and put `adb` on `PATH`.
2. Connect the phone to the Mac by USB or an already paired Android wireless-debugging connection. Authorise debugging on the phone; check `adb devices`.
3. Run the same viewer command. If multiple devices are connected, add `--device DEVICE_ID`. Use `--adb /full/path/to/adb` if it is not on `PATH`.

Alternatively, `.venv/bin/python scripts/run.py mobile` on the Mac records Flutter output in `output/logs/mobile.log`, which the viewer also follows. Flutter running on Windows does not automatically send its console output to the Mac.

Without a Mac debug connection, requests that fail before FastAPI and requests to external services are invisible to the laptop viewer. Native plugin/WebView traffic is not automatically intercepted. No remote logging service is used. Disable debug tracing with `--dart-define=DEV_LOGGING=false` when launching/building if needed.

## Useful checks

- Rebuild after changing any of the three public settings. Do not pass `.env` or the service-role key to Flutter.
- Protected account features require confirmed email and TOTP MFA. The Android Auth redirect is `myroadie://auth/callback`.
- If a connection fails, open `API_BASE_URL/health` on the phone with Tailscale connected.
- Check login, chat, source images, location, camera access, and offline emergency content on a real device after a release build.
