# YahBible Mobile

The mobile edition of **YahBible** — the offline scripture‑study companion. A phone‑first,
fully‑offline web app (the `www/` UI) that is wrapped into a native Android shell for a real
installable app.

- 🖥️ Desktop edition: **YahBible** (GitHub: `OhBeOneKeyNoBe/YahBible`) · Hugging Face docs
- 🌐 [RealizeUS.me](https://www.realizeus.me/@yahwehtsidkenu)

## What it is (v0.1)

A self‑contained study app that works with **no internet and no desktop connection**:

- **Home** — the YahBible wordmark (א YahBible ת), the holy‑fish backdrop, and a rotating verse.
- **Study — the Ten Commandments** — each commandment read as questions (*"What is Adultery?"*,
  *"How do you keep this commandment?"*), the seven inward dimensions as accordions, the
  interactive **human‑dimension onion diagram**, and every insight section in source order.
- **Repentance** — its own category: what repentance is, the Regret‑vs‑Repentance distinction,
  the inward ladder, a turning stage per dimension, **Seek Counsel in Prayer** (the Matthew‑6
  flow), and the Lord's Prayer.
- **News & Updates** — the release‑notes / guided‑tour feed (the tab shows a dot until viewed).
- **Self‑cam overlay** — a draggable circular / green‑screen camera for TikTok screen‑share.

All study content is **bundled offline** (`www/data/*.js`, generated from the desktop edition's
single‑source JSON). Notes and reading progress will sync to your desktop (the Zion'iel Network
node = your PC) when it is reachable.

## Layout

```
YahBible-Mobile/
  www/                     ← the offline web UI (drops into the Android WebView shell)
    index.html
    app.css
    app.js
    data/                  ← bundled study content (commandments / repentance / news)
    assets/holy-fish.png
  android/                 ← native Android shell (added in the wrap step; forked from Zioniel.ai)
  README.md
```

## Run the web UI locally (desktop preview)

```
cd www
py -m http.server 41599 --bind 127.0.0.1
# open http://127.0.0.1:41599/  in a browser (use device toolbar / a phone width)
```

## Build the Android APK (toolchain step)

The `.apk` needs a one‑time Android toolchain: **JDK 17**, the **Android SDK + NDK**, and the
Rust Android targets. Once installed, the `www/` folder is copied into the shell's
`assets/web/` and built with Gradle. See `docs/BUILD_ANDROID.md` (added in the wrap step).

## Lineage

The Android shell is forked from the **Zion'iel Companion / Zioniel.ai** app
(`OhBeOneKeyNoBe/Zioniel.ai`), reusing its desktop‑pairing, WebView, and floating‑overlay
pieces. The internal source structure is proprietary; nothing in this public README exposes it.
