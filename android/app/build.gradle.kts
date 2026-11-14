plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "vn.vieedge.voice"
    compileSdk = 34
    defaultConfig {
        applicationId = "vn.vieedge.voice"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        ndk { abiFilters += "arm64-v8a" }          // MapLibre ships 4 ABIs; every native part of the app is arm64 only
    }
    packaging { jniLibs { useLegacyPackaging = true } }
    buildTypes { release { isMinifyEnabled = false } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    // snapdragon: llama.cpp built for ARMv8.7 with the Hexagon NPU and Adreno OpenCL backends (Galaxy Z Fold7 and similar);
    // generic: llama.cpp built for plain ARMv8.0, CPU only, for any other arm64 phone (TCL T506T, MediaTek Helio P22).
    flavorDimensions += "soc"
    productFlavors {
        create("snapdragon") { dimension = "soc"; buildConfigField("boolean", "CPU_ONLY", "false") }
        create("generic") { dimension = "soc"; buildConfigField("boolean", "CPU_ONLY", "true"); versionNameSuffix = "-generic" }
    }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.maplibre.gl:android-sdk:11.5.2")       // offline vector map (OpenFreeMap tiles)
    implementation(platform("androidx.compose:compose-bom:2024.09.03"))
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.sqlite:sqlite:2.4.0")
    implementation("com.github.requery:sqlite-android:3.35.5")   // SQLite with FTS5 (the system SQLite has no FTS5)
}
