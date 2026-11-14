// Runs llama.cpp's server inside the app process (an exec'd child cannot see the vendor OpenCL / FastRPC libraries that Android only
// exposes to the app's own linker namespace). llama-server's entry points are exported by libllama-server-impl.so.
#include <jni.h>
#include <stdlib.h>
#include <string>
#include <vector>

int llama_server(int argc, char ** argv);
void llama_server_terminate();

extern "C" JNIEXPORT jint JNICALL Java_vn_vieedge_voice_LlmHost_nativeRun(JNIEnv * env, jclass, jobjectArray args) {
    std::vector<std::string> store;
    jsize n = env->GetArrayLength(args);
    for (jsize i = 0; i < n; i++) {
        jstring s = (jstring) env->GetObjectArrayElement(args, i);
        const char * c = env->GetStringUTFChars(s, nullptr);
        store.emplace_back(c);
        env->ReleaseStringUTFChars(s, c);
    }
    std::vector<char *> argv;
    for (auto & s : store) argv.push_back(s.data());
    argv.push_back(nullptr);
    return llama_server((int) n, argv.data());
}

extern "C" JNIEXPORT void JNICALL Java_vn_vieedge_voice_LlmHost_nativeStop(JNIEnv *, jclass) { llama_server_terminate(); }

extern "C" JNIEXPORT void JNICALL Java_vn_vieedge_voice_LlmHost_nativeSetenv(JNIEnv * env, jclass, jstring k, jstring v) {
    const char * ck = env->GetStringUTFChars(k, nullptr);
    const char * cv = env->GetStringUTFChars(v, nullptr);
    setenv(ck, cv, 1);
    env->ReleaseStringUTFChars(k, ck);
    env->ReleaseStringUTFChars(v, cv);
}
