# Mobile reliability review — 4 November 2026

The mobile screens, repositories and backend contracts were reviewed together. The fixes below are implemented, Flutter analysis is clean, all 55 mobile tests pass (including parsing captured live API data), and all 33 backend tests pass. This is code and automated verification; native Android release verification remains outstanding.

## Changes

- Every paginated request now has a total time limit and rejects repeating or invalid record IDs. Timeouts abort the HTTP request, including partially downloaded responses.
- Device JSON writes are serialized by file path across repository instances. Incident read/modify/write operations, guest imports and cloud backups also share locks, preventing overlapping screens or background backups from losing records.
- Incident conflicts no longer block unrelated backups. Incident options identifies conflicting records and offers **Keep both copies**, preserving local details/photos and the cloud version before backing up a separate local copy.
- Account restoration checks that its response still belongs to the current Supabase session. Late login responses cannot sign an already signed-out session back into the UI. Routine session verification retains the owner ID while verification is pending; garage, chat and companion requests reject unverified or changed account ownership.
- Authenticator selection falls back to an available factor if a saved selection disappears.
- Opening a published guide without exploration sections no longer sends an empty progress update that the backend rejects. Progress updates reject invalid section indexes; learning action buttons respect pending saves.
- Each vehicle selection sheet starts with an empty search, so a manufacturer search cannot hide model/year choices in subsequent sheets.
- Native 3D bridge initialization failures display the existing fallback instead of escaping an asynchronous callback.
- Family contacts are callable from emergency help, including offline. Failed family-contact saves keep the editor and its input open.
- Removed controls that claimed to change distance units or notifications but only saved unused preferences. The profile accurately describes kilometres and in-app service reminders. Background notifications and mile conversion are not implemented.
- Updated the learning screen's obsolete “account synchronization will be added later” text to describe the existing account-backed progress.

## Feature coverage

| Area | Reviewed functions | Verification |
| --- | --- | --- |
| App shell | Account entry, guest access, Home/My Car/Learn/Ask AI/Emergency navigation, account/vehicle changes | Five-tab widget flow; stale garage-response tests; rendered 390 × 844 screenshots |
| Accounts | Registration/login, restore, logout, recovery, confirmation, MFA enrollment/verification/removal | Screen rendering; account concurrency/sign-out tests; private endpoint authentication and input validation |
| Garage | Catalogue, add/edit/remove/select vehicle, odometer, contacts | Live catalogue; actual model parsing; form rendering; snapshot validation and save/reload failure tests |
| Maintenance | Item creation/editing, manufacturer/custom/history-only schedules, service records, dates/mileage/cost, deletion, spending, workshop batch recovery | Forms and workshop screens; route contracts/validation; garage and persistence tests |
| Learning | Categories, guides, exploration/quiz steps, completion/unread/recaps, weekly progress, related guides, manual links | Live categories and 31 guides parsed by the mobile repositories; reader screen; progress revision test; manuals for every supported vehicle |
| Chat | Session creation, request payload, reply parsing, retry/recovery, source images/manuals/videos, contextual learning and plans | Request/response regression tests, backend chat/source tests, API route mapping, tab rendering |
| Companion | Discovery, plan preview/save/reopen, saved guides/explanations/notes, note editing/removal, mechanic preparation | Screen rendering, route mapping/authentication, owner-change guard, existing backend tests |
| Emergency | Reviewed guides, downloads, cached media, progress, safety check, read-aloud, calls, location sharing, nearby providers/Maps | Live guide parsing; guide/download/help/safety/nearby screens; public nearby response and rate-limit tests; cached contact test |
| Incidents | Draft/autosave, past incident editing, photos/recovery, history, guest import/delete, optional cloud text backup, conflict recovery | File concurrency/corruption tests; draft-to-history test; backup serialization/conflict tests; form/history rendering |

Screen tests render 21 secondary screens at 360 × 800 using the bundled Inter and Material Icons fonts. They exercise layout and disposal; they do not constitute end-to-end success tests for every action in those screens.

## Live backend checks

Read-only requests succeeded for health, configuration, chat starters, catalogue, maintenance items, categories, guides, manuals, emergency contacts and emergency playbooks. The catalogue contains 10 vehicle variants, 92 maintenance items, 31 guides, six categories and six published emergency playbooks. Manual listings were checked for all 10 vehicle scopes (41 distinct documents). Guest requests to `/accounts/me` and `/mobile/me` correctly return 401.

The shared emergency directory is currently empty. The built-in 999 action and saved roadside/family contacts remain available. General-scope manuals are empty; vehicle-specific manual listings contain documents.

A representative published PDF downloaded successfully (88,417 bytes, valid PDF signature). All 41 uploaded emergency media files downloaded successfully and matched their declared byte lengths and SHA-256 digests.

Live account mutations, email recovery/confirmation delivery, MFA provider operations, paid Places searches and AI generation were not exercised against a real signed-in account in this pass. Their contracts and selected failure paths were tested with isolated fixtures/mocks. No live account records or published content were changed.

## Reproduce

From the repository root, with Flutter on PATH and the backend running:

```bash
.venv/bin/python scripts/check_mobile_api.py
.venv/bin/python -m unittest discover -s backend -p 'test_*.py'
cd mobile
flutter analyze --no-pub
ROADIE_LIVE_FIXTURE="$PWD/../output/mobile-audit/live-api.json" flutter test --no-pub
```

Without `ROADIE_LIVE_FIXTURE`, the live-data parser test is skipped; the other tests remain self-contained. Set `ROADIE_SCREENSHOTS` to a writable folder to capture the five main tabs during the screen test. Captures use test data and the desktop fallback for the native 3D viewer.

## Native release verification still required

`flutter doctor -v` reports no Android SDK and no connected Android phone/emulator on this Mac. An APK was not built or installed during this review. A device run is still required for secure storage/deep links, real login/MFA/recovery, camera and lost-picker recovery, permission-denied GPS flows, sharing/dialler/Maps, MP4 playback, offline English speech, and the Android WebView 3D model. Rebuild using the public API/Supabase settings in the operations guide before installing on the phone.

The current Android release configuration also uses the existing debug signing key. Distribution signing remains a separate release setup task. Automated checks reduce regression risk; they cannot establish that every function will remain error-free under all device, network and service conditions.
