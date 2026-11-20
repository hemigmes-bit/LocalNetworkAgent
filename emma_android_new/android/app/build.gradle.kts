// android/app/build.gradle.kts
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("dev.flutter.flutter-plugin")
    id("com.chaquo.python") version "14.0.0"
}

android {
    namespace = "com.emma.tutor"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.emma.tutor"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        
        // Chaquopy configuration
        python {
            version = "3.10"
            pip {
                install("requests", "beautifulsoup4", "lxml")
            }
            pip {
                install("torch", "torchaudio", "transformers")
            }
        }
        
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
        }
    }
    
    packagingOptions {
        resources {
            excludes += "/META-INF/*"
        }
    }
    
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib-jdk8:1.9.22")
    implementation("com.chaquo.python:python3:14.0.0")
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
}