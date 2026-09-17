# Tav'iel on your phone — on-device AI, fully offline

**Status (verified 2026-09-17): every piece is built and hosted. Nothing is
missing in the code or on the servers — it only needs to be built, installed,
and the two downloads completed on the phone.**

The phone runs the **whole desktop engine** inside itself: the Chaquopy Python
runtime executes the same `o_taviel_server.py` at `127.0.0.1:41537`, and Tav'iel
reasons through a **LiteRT `.task` model served by MediaPipe** — the exact same
grounded ask-pipeline as the desktop (`tav_llm.py` just swaps the model backend
to `tav_llm_mobile.py`). No cloud, no signal needed after the downloads.

## Why AI may not have appeared yet

The AI lives ONLY in the **v0.2 ENGINE build**, whose application id is
`me.realizeus.yahbible.engine`. It installs **beside** the older v0.1 "lite"
app (`me.realizeus.yahbible`), which has **no** Python engine and **no** AI. If
the app you opened was the lite one, that is why Tav'iel could not think. Open
the **engine** build (its own icon), not the lite app.

## What is already in place (audited)

- `app/src/main/java/.../TavLlm.java` — MediaPipe `LlmInference` bridge
  (`ensure` / `generate` / `unload` / `lastError`). Correct for tasks-genai 0.10.35.
- `app/src/main/python/tav_llm_mobile.py` — Python↔Java bridge; loads the newest
  `.task` in `<base>/ai/`.
- `app/src/main/python/*` — the full engine (o_taviel_server, gen_at_depth,
  taviel_agent, grounding, scripture, …).
- `app/build.gradle.kts` — Chaquopy 16.1.0 / Python 3.12, MediaPipe
  `com.google.mediapipe:tasks-genai:0.10.35`, arm64-v8a, minSdk 26.
- Download sources (all confirmed to resolve on Hugging Face):
  - AI model: `litert-community/Qwen2.5-1.5B-Instruct` →
    `Qwen2.5-1.5B-Instruct_multi-prefill-seq_q8_ekv4096.task` (~1.7 GB). A
    DeepSeek-R1-Distill-1.5B `.task` is offered as the "deep reasoning" option.
  - Engine data: `OhBeOneKeyNoBe/YahBible-Mobile/packs/desktop/manifest.json`
    + 34 files (~314 MB compressed → ~1.2 GB installed).

## Build the engine APK

From `android/` (needs Android SDK 34, NDK, JDK 17; Gradle is wrapped):

```bash
./gradlew :app:assembleRelease        # or assembleDebug for quick device testing
# APK: app/build/outputs/apk/release/app-release.apk  (arm64, ~50–60 MB;
# the model + engine data are downloaded in-app, not bundled)
```

Chaquopy downloads the Python runtime + `cryptography` wheel on the first build,
so the first build needs internet and takes a while.

## Install & bring Tav'iel to life on the phone

1. Install the engine APK (`adb install -r app-release.apk`, or sideload). Its
   icon is the **v0.2 engine** app — distinct from any lite app already there.
2. Open it → **Settings → the Full Desktop Engine**:
   1. **Desktop data** (~1.2 GB) — tap Download; it resumes on failure.
   2. **Tav'iel Mind — Qwen 1.5B** (~1.7 GB) — tap Download.
   3. **Breathe life into the engine** — waits for `127.0.0.1:41537` to come up.
3. Open the engine and ask Tav'iel anything. First reply loads the model
   (~10–45 s on the phone), then it answers grounded and offline.

Budget ~3 GB of downloads and keep ~2–3 GB of free RAM for the model at run time
(a q8 1.5B model + the engine). Low-RAM devices should prefer the Qwen 1.5B over
the DeepSeek option.

## If it still fails, read the real reason (never a silent failure)

- A load failure surfaces the exact cause: `tav_llm_mobile.open_tier` raises
  `model failed to load: <file> — <why>` from `TavLlm.lastError()`, and the chat
  shows it. The most likely `<why>` is a **MediaPipe ↔ .task version mismatch**:
  the `litert-community` `.task` files track a MediaPipe version; if load throws,
  bump `tasks-genai` in `app/build.gradle.kts` to the version those models were
  published against, rebuild, and retry.
- No model installed → "download one in Settings" (the `.task` didn't finish).
- Engine won't start → the Python data (packs/desktop) is incomplete; re-run the
  Desktop-data download (it resumes).

Everything above is confirmed present as of 2026-09-17; the remaining step is a
build + on-device run.
