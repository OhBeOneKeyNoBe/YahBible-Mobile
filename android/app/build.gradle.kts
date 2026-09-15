plugins {
    id("com.android.application")
    id("com.chaquo.python") version "16.1.0"   // Python inside the APK: the FULL desktop engine
}

android {
    namespace = "me.realizeus.yahbible"
    compileSdk = 34

    defaultConfig {
        applicationId = "me.realizeus.yahbible"
        minSdk = 26
        targetSdk = 34
        // versionCode rises every shipped build (yyMMddNN) so Android installs updates OVER
        // the old app — keeping settings & downloads — and the version is visible on-device.
        versionCode = 26091501
        versionName = "0.2.20260915010"
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
