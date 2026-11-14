#!/usr/bin/env bash
# Builds libvieedge_jni.so with the Snapdragon toolchain image (NDK inside). Needs third_party/llama.cpp/pkg-android from docs/backend/snapdragon.
set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker-native}
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/..:/repo" -w /repo --platform linux/amd64 ghcr.io/snapdragon-toolchain/arm64-android:v0.7 bash -c '
  NDK=$(ls -d /opt/android-ndk-*); CXX=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang++
  $CXX -shared -fPIC -O2 -static-libstdc++ -o android/app/src/main/jniLibs/arm64-v8a/libvieedge_jni.so android/native/vieedge_jni.cpp \
       -L third_party/llama.cpp/pkg-android/llama.cpp/lib -lllama-server-impl -llog'
