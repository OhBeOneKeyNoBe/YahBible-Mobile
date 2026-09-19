plugins {
    id("com.android.application")
    id("com.chaquo.python") version "16.1.0"   // Python inside the APK: the FULL desktop engine
}

android {
    namespace = "me.realizeus.yahbible"
    compileSdk = 34

    defaultConfig {
        // YahBible v.2 — the ONE app. The full desktop engine + on-device AI are baked in;
        // this is the canonical id (me.realizeus.yahbible), so it installs OVER the retired
        // v1 "lite" app and the old side-by-side engine build, replacing them with a single
        // "YahBible" on the phone.
        applicationId = "me.realizeus.yahbible"
        minSdk = 26
        targetSdk = 34
        // versionCode rises every shipped build (yyMMddNN) so Android installs updates OVER
        // the old app — keeping settings & downloads — and the version is visible on-device.
        // 26091701 is higher than every prior lite (…26091427) and engine (26091509) build,
        // so v.2 lands as an update over whichever one is installed.
        versionCode = 26091803
        versionName = "2.4"   // complete interlinear everywhere (canon_fill bundled): titled Psalms, Numbers 16-17, NT doxologies
        ndk { abiFilters += listOf("arm64-v8a") }   // phones; keeps the APK lean
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // The web UI is already bundled in assets/web — do not compress it.
    androidResources {
        noCompress += listOf("js", "css", "html", "woff2", "png")
    }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        buildPython("py", "-3.12")
        pip {
            // taviel_updates (Origin-signed updates) needs it; Chaquopy ships a native wheel.
            install("cryptography")
        }
    }
}

dependencies {
    // On-device AI: MediaPipe LLM inference (LiteRT .task models — Tav'iel reasons offline)
    implementation("com.google.mediapipe:tasks-genai:0.10.35")
}
