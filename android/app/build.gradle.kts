plugins {
    id("com.android.application")
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
        versionCode = 26091423
        versionName = "0.1.20260914230"
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

dependencies {
    // Intentionally dependency-free: a bare WebView on the framework Material theme,
    // so the APK builds with only the Android Gradle Plugin (no AndroidX fetch needed).
}
