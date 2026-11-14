package vn.vieedge.voice

import android.content.Context
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Runs the same llama-server as on the Pi, built for Snapdragon (CPU / Adreno OpenCL / Hexagon NPU), inside the app process through a small JNI
 * shim (Android only exposes the vendor OpenCL / FastRPC libraries to the app's own linker namespace, not to an exec'd child), and streams
 * chat completions over localhost.
 */
class LlmHost(private val ctx: Context) {
    private var thread: Thread? = null
    private val http = OkHttpClient.Builder().readTimeout(0, TimeUnit.SECONDS).connectTimeout(2, TimeUnit.SECONDS).build()
    private val port = 8089
    var device = "none"
        private set

    /** device: "HTP0" (NPU), "GPUOpenCL" (Adreno), "none" (CPU). Returns an error text or null when the server answers /health. */
    fun start(model: File, device: String, ctxSize: Int = 2048, threads: Int = 4): String? {
        stop()
        this.device = device
        val dir = ctx.applicationInfo.nativeLibraryDir
        try { System.loadLibrary("vieedge_jni") } catch (e: UnsatisfiedLinkError) { return "Không nạp được libvieedge_jni: ${e.message}" }
        nativeSetenv("ADSP_LIBRARY_PATH", dir)
        nativeSetenv("GGML_OPENCL_KERNEL_CACHE_DIR", ctx.cacheDir.absolutePath)
        val args = mutableListOf("llama-server", "-m", model.absolutePath, "--host", "127.0.0.1", "--port", "$port", "-c", "$ctxSize",
            "-t", "$threads", "--no-webui", "--jinja", "--device", device)
        if (device != "none") args += listOf("-ngl", "99")
        var rc = Int.MIN_VALUE
        val t = Thread { rc = nativeRun(args.toTypedArray()) }.apply { name = "llama-server"; start() }
        thread = t
        val t0 = System.currentTimeMillis()
        while (System.currentTimeMillis() - t0 < 120_000) {
            if (!t.isAlive) return "llama-server thoát (mã $rc)"
            try {
                http.newCall(Request.Builder().url("http://127.0.0.1:$port/health").build()).execute().use { if (it.isSuccessful) return null }
            } catch (_: Exception) { /* not up yet */ }
            Thread.sleep(300)
        }
        return "llama-server không sẵn sàng sau 120 s"
    }

    fun stop() {
        if (thread?.isAlive == true) { nativeStop(); thread?.join(10_000) }
        thread = null
    }

    class Result(val text: String, val promptTokens: Int, val promptMs: Double, val predTokens: Int, val predMs: Double, val ttftMs: Double)

    /** Streams the answer; onToken is called for every piece. `cancel()` returning true aborts. */
    fun chat(messages: JSONArray, maxTokens: Int = 160, cancel: () -> Boolean = { false }, onToken: (String) -> Unit): Result {
        val body = JSONObject().put("messages", messages).put("stream", true).put("max_tokens", maxTokens).put("temperature", 0.3)
            .put("top_p", 0.9).put("cache_prompt", true).put("chat_template_kwargs", JSONObject().put("enable_thinking", false))
        val req = Request.Builder().url("http://127.0.0.1:$port/v1/chat/completions")
            .post(body.toString().toRequestBody("application/json".toMediaType())).build()
        val sb = StringBuilder(); var timings: JSONObject? = null; var ttft = -1.0
        val t0 = System.nanoTime()
        http.newCall(req).execute().use { r ->
            val src = r.body!!.source()
            while (!src.exhausted()) {
                val line = src.readUtf8Line() ?: break
                if (!line.startsWith("data:")) continue
                val d = line.removePrefix("data:").trim()
                if (d == "[DONE]") break
                val o = JSONObject(d)
                if (o.has("timings")) timings = o.getJSONObject("timings")
                val delta = o.optJSONArray("choices")?.optJSONObject(0)?.optJSONObject("delta")
                val ch = if (delta != null && !delta.isNull("content")) delta.getString("content") else ""
                if (ch.isNotEmpty()) {
                    if (ttft < 0) ttft = (System.nanoTime() - t0) / 1e6
                    sb.append(ch); onToken(ch)
                }
                if (cancel()) break
            }
        }
        val tm = timings
        return Result(sb.toString(), tm?.optInt("prompt_n") ?: 0, tm?.optDouble("prompt_ms") ?: 0.0, tm?.optInt("predicted_n") ?: 0,
            tm?.optDouble("predicted_ms") ?: 0.0, ttft)
    }

    companion object {
        @JvmStatic private external fun nativeRun(args: Array<String>): Int
        @JvmStatic private external fun nativeStop()
        @JvmStatic private external fun nativeSetenv(k: String, v: String)
    }
}
