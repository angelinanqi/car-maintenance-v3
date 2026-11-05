# MyRoadie mobile artwork

`branding/` contains the app icon source (`roadie_logo.png`) and the full logo
used on the account screen (`roadie_full_logo.png`).

`mascots/` contains mobile-only artwork:

- `roadie_chatbot.png`: AI screen and assistant message avatars.
- `roadie_mascot.png`: transparent companion illustration for empty history and
  learning completion (originally `roadie_mascot_nobg.png`).

Compact mascot placements use the logo so the character stays legible at small
sizes. Images retain their aspect ratio and are not cropped by Flutter.

Production assets were copied from the supplied Roadie folder; the originals
remain there. Concept and colour reference sheets are not bundled. The opaque
mascot variant and unused word-only logo are also not bundled. Artwork is owned
by the mobile app here; future web/admin branding can share the logo and
word-only logo without sharing the mobile mascot assets.

The current mobile project targets Android. To regenerate its five launcher
icon sizes after replacing the source logo, run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File mobile/scripts/generate_launcher_icons.ps1
```
