# YahBible Mobile

**A free, fully‑offline scripture‑study app for Android.** No internet, no account, no server — the
whole study library (the KJV Bible, the Ten Commandments study, and the Repentance teaching) lives
inside the app.

## 📲 Download & install (free)

**[⬇️ Download the latest APK](https://github.com/OhBeOneKeyNoBe/YahBible-Mobile/releases/latest)**
&nbsp;·&nbsp; also on [Hugging Face](https://huggingface.co/OhBeOneKeyNoBe/YahBible-Mobile)

1. On your Android phone, download **`YahBible-v0.1-debug.apk`** from the link above.
2. Tap the file. If Android asks, allow **Install unknown apps** for your browser or Files app.
3. Open **YahBible** — that's it. It works with no internet.

*Requires Android 8.0 or newer. Free — no ads, no account, no tracking.*

---

## What's inside

| | |
|---|---|
| <img src="docs/screenshots/01-home.png" width="230"> | **Home** — the YahBible wordmark (א YahBible ת), the holy‑fish backdrop, and a rotating verse. Five tabs: Home · Bible · Study · Repent · News. |
| <img src="docs/screenshots/02-bible-reader.png" width="230"> | **The whole KJV Bible, offline** — all 66 books, 31,102 verses, bundled in the app. Book → chapter → reader, with verse highlighting. Every scripture reference anywhere in the app opens the reader at that verse. |
| <img src="docs/screenshots/03-commandment-qa.png" width="230"> | **The Ten Commandments, as questions** — each commandment opens as a study of clear questions: *“What is Adultery?”*, *“How do you keep this commandment?”*, and *“How is it broken?”* in each of the seven inward dimensions. |
| <img src="docs/screenshots/04-dimensions.png" width="230"> | **The seven dimensions** — 🔴 Physical · 🟠 Emotional · 🟡 Mental · 🟢 Ambitional · 🔵 Vocal · 🟣 Intentional · 🟪 Spiritual — each an accordion with examples, scripture, and how to keep it. |
| <img src="docs/screenshots/05-repentance-layers.png" width="230"> | **Where sin forms** — the person shown in seven nested layers, spirit at the core (violet) to flesh on the surface (scarlet). Tap a layer to open its dimension. |
| <img src="docs/screenshots/06-ladder.png" width="230"> | **The inward ladder** — a countdown 7→1, from the spirit down to the outward act, so you learn to see (and turn from) sin earlier. |
| <img src="docs/screenshots/07-counsel.png" width="230"> | **Seeking the Father’s Counsel** — three steps (Adoption · Counsel · Blessings), the full Lord’s Prayer, and *Seek Counsel in Prayer* as a guided flow. |
| <img src="docs/screenshots/08-news.png" width="230"> | **News & Updates** — a release‑notes and guided‑tour feed; the tab shows a dot until you’ve read what’s new. |

Plus a **draggable self‑cam overlay** (circle / green‑screen) for streaming.

---

## Also available

- 🖥️ **Desktop edition:** [YahBible on Hugging Face](https://huggingface.co/OhBeOneKeyNoBe/YahBible) — the same study, for Windows.
- 🌐 **The creator:** [RealizeUS.me/@yahwehtsidkenu](https://www.realizeus.me/@yahwehtsidkenu)

## About

YahBible is a free devotional and scripture‑study tool. The KJV text is public domain. All study
content is bundled offline so the app works anywhere, with no connection and no cost.

<details>
<summary>For developers</summary>

The app is a native Android WebView (`android/`) wrapping the offline web UI in `www/`. To build the
APK yourself you need JDK 17 and the Android SDK (platform‑34, build‑tools 34 — no NDK):

```bash
cd android
echo "sdk.dir=/path/to/Android/sdk" > local.properties
./gradlew assembleDebug     # -> app/build/outputs/apk/debug/app-debug.apk
```
</details>
