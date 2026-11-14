package vn.vieedge.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineTransducerModelConfig
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.max

/**
 * The whole assistant on the phone: Silero VAD (400 ms endpoint) -> Zipformer-vi (sherpa-onnx, same model as the Pi) ->
 * [fast path | llama-server on NPU/GPU/CPU] -> sentence segmenter (first chunk after 5 words) -> normaliser -> Piper (sherpa-onnx) -> speaker.
 * Models live in <filesDir>/models (pushed with adb + run-as, not bundled). Every turn is timed like on the Pi and appended to turns.jsonl.
 */
class LocalAssistant(private val ctx: Context, private val ui: Ui) {
    interface Ui {
        fun status(t: String)
        fun state(s: String)
        fun partial(t: String)
        fun question(t: String)
        fun answer(t: String)
        /** Once per turn, in turn order; asked = false for a turn that showed no question (nothing was heard). */
        fun metrics(t: String, asked: Boolean)
        fun level(pk: Int)
        /** The answer comes from a vetted safety card (id), or from the "call 115" fallback (null). */
        fun safety(cardId: String?) {}
        /** The microphone is listening (true) or paused (false, after a tap or after a long silence). */
        fun listening(on: Boolean) {}
    }

    val modelsDir = File(ctx.filesDir, "models")
    // bench/eval_answer_style.py (345 test questions, 9B judge): a "just answer directly" prompt cut the "Mình không chắc"
    // openings from 252 to 21 of 345 but more than doubled made-up answers (21% -> 48% on spoken questions), so the honest
    // prompt stays: for a small model, saying "not sure" is what keeps it from inventing facts.
    private val system = "Bạn là VieEdge, trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy hoàn toàn trên thiết bị, không có internet. " +
        "Câu trả lời của bạn sẽ được đọc to bằng giọng nói, vì vậy hãy: trả lời ngắn gọn trong 1 đến 3 câu; dùng câu văn nói tự nhiên, thân thiện; " +
        "không dùng markdown, không gạch đầu dòng, không ký hiệu, không biểu tượng cảm xúc; viết số và đơn vị sao cho dễ đọc. " +
        "Nếu câu hỏi cần thông tin thời gian thực (thời tiết, tin tức, giá cả hôm nay, tỷ số) hoặc bạn không chắc chắn, " +
        "hãy nói thật là mình không chắc hoặc không có thông tin đó, tuyệt đối không bịa."
    /** The last exchanges (question, answer, time) so that "còn cái kia thì sao" makes sense; forgotten after 3 minutes. */
    private val history = ArrayDeque<Triple<String, String, Long>>()
    /** Exchanges kept as context (0 on CPU-only phones: every earlier exchange adds prompt tokens, about 8 tokens/s there). */
    var historyTurns = if (BuildConfig.CPU_ONLY) 0 else 2
    private val noAnswer = "Xin lỗi, mình chưa nghe rõ. Bạn nói lại được không?"

    private val llm = LlmHost(ctx)
    private val fast = FastPath(ctx)
    private var vad: Vad? = null
    private var asr: OfflineRecognizer? = null
    private var tts: OfflineTts? = null
    private var track: AudioTrack? = null
    private var rec: AudioRecord? = null
    private val running = AtomicBoolean(false)
    private val speaking = AtomicBoolean(false)
    private val pendingSpeech = AtomicInteger(0)
    @Volatile private var cancelled = false
    // interrupt() bumps epoch; audio queued by an older turn is dropped even after the next turn has reset `cancelled`
    // (a question typed while a card is read aloud must not wait behind the rest of the card)
    @Volatile private var epoch = 0
    @Volatile private var turnEpoch = 0
    @Volatile private var mutedUntil = 0L
    @Volatile private var framesWritten = 0L                    // frames written to the AudioTrack since it last started from zero
    private val turnExec = Executors.newSingleThreadExecutor()
    private val ttsExec = Executors.newSingleThreadExecutor()
    private val phraseCache = HashMap<String, FloatArray>()
    var fastPathEnabled = true
    var ragEnabled = true                               // offline Wikipedia lookup (needs models/rag/wiki_vi.sqlite)
    private var rag: Rag? = null
    var ackEnabled = false                              // play a short "Dạ." while the LLM thinks (perceived latency)
    var voiceDir = "tts/vits-piper-vi_VN-vais1000-medium"
    var endpointS = 0.4f
    var vadThreshold = 0.5f                             // Silero: higher = needs clearer speech
    var minSpeechS = 0.3f
    var minRms = 0.008f                                   // segments quieter than this (RMS, 0..1) are treated as noise
    var minChars = 3                                    // transcripts shorter than this are noise
    var useAgc = false                                  // AGC lifts the noise floor in silence and makes the VAD fire on it
    var firstWords = 7                                  // the first spoken chunk ends at the first pause, or after this many words (3 broke phrases in two)
    var ttsThreads = 4
    var asrThreads = 3
    var llmThreads = 4
    var hotwordsOn = true                               // biasing toward the safety words (beam search); off = greedy, a little faster
    /** Piper speed: 1.0 = model default; lower is slower (0.85 is easier to follow on a phone speaker). */
    var speechSpeed = 0.85f
        set(v) { if (v != field) { field = v; synchronized(phraseCache) { phraseCache.clear() }; if (running.get()) prewarmPhrases() } }
    var loudBoost = true                                // +9 dB loudness enhancer on the speaker (Piper is quiet on phone speakers)
    var idleTimeoutS = 30                               // stop listening after this long without speech (0 = never)
    @Volatile var listening = true
        private set
    @Volatile private var lastActivity = 0L
    private val ackPhrases = listOf("Dạ.", "Vâng.")
    private var ackIdx = 0
    @Volatile private var pttHeld = false
    @Volatile private var noiseFloor = 0.004f           // slow average of the RMS while nobody speaks; a real utterance must stand clearly above it
    private val pttBuf = ArrayList<FloatArray>()

    fun llmFiles(): List<String> = File(modelsDir, "llm").listFiles { f -> f.name.endsWith(".gguf") }?.map { it.name }?.sorted() ?: emptyList()

    /** Loads everything and starts listening. Returns an error text, or null when ready. */
    fun start(llmName: String, device: String): String? {
        if (running.get()) return null
        val vadF = File(modelsDir, "vad/silero_vad.onnx")
        val zip = File(modelsDir, "stt/zipformer-vi")
        val voice = File(modelsDir, voiceDir)
        val voiceOnnx = voice.listFiles { f -> f.name.endsWith(".onnx") }?.firstOrNull()?.name ?: "missing.onnx"
        val gguf = File(modelsDir, "llm/$llmName")
        for (f in listOf(vadF, File(zip, "encoder-epoch-20-avg-10.int8.onnx"), File(voice, voiceOnnx), gguf))
            if (!f.exists()) return "Thiếu file ${f.relativeTo(modelsDir)} trong ${modelsDir.absolutePath}"
        ui.status("Đang tải mô hình nhận dạng và tổng hợp giọng nói…")
        runCatching { track?.stop(); track?.release() }; track = null; runCatching { tts?.free() }; tts = null
        vad = Vad(null, VadModelConfig(SileroVadModelConfig(model = vadF.absolutePath, threshold = vadThreshold, minSilenceDuration = endpointS,
            minSpeechDuration = minSpeechS, windowSize = 512, maxSpeechDuration = 20f), sampleRate = 16000, numThreads = 1))
        asr = OfflineRecognizer(null, OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 16000, featureDim = 80),
            modelConfig = OfflineModelConfig(
                transducer = OfflineTransducerModelConfig(encoder = "${zip.absolutePath}/encoder-epoch-20-avg-10.int8.onnx",
                    decoder = "${zip.absolutePath}/decoder-epoch-20-avg-10.int8.onnx", joiner = "${zip.absolutePath}/joiner-epoch-20-avg-10.int8.onnx"),
                tokens = "${zip.absolutePath}/tokens.txt", numThreads = asrThreads, modelingUnit = "bpe", bpeVocab = bpeVocabFile()),
            // contextual biasing toward the safety cards' words (bench/eval_hotwords.py: score 1.0 chosen on held-out v2,
            // VIVOS WER unchanged); the model itself is not modified (its licence forbids derivatives)
            decodingMethod = if (hotwordsOn && hotwordsFile() != null) "modified_beam_search" else "greedy_search", maxActivePaths = 4,
            hotwordsFile = if (hotwordsOn) hotwordsFile() ?: "" else "", hotwordsScore = 1.0f))
        tts = OfflineTts(null, OfflineTtsConfig(OfflineTtsModelConfig(
            vits = OfflineTtsVitsModelConfig(model = "${voice.absolutePath}/$voiceOnnx", tokens = "${voice.absolutePath}/tokens.txt",
                dataDir = "${voice.absolutePath}/espeak-ng-data"), numThreads = ttsThreads)))
        openTrack(tts!!.sampleRate())
        File(modelsDir, "rag/wiki_vi.sqlite").takeIf { it.exists() && ragEnabled }?.let { f -> rag = runCatching { Rag(f) }.getOrNull() }
        ui.status("Đang khởi động mô hình ngôn ngữ ($device)…")
        llm.start(gguf, device, threads = llmThreads)?.let { return it }
        warmup()
        running.set(true)
        listening = true; lastActivity = System.currentTimeMillis(); ui.listening(true)
        startCapture()
        prewarmPhrases()
        val where = when (device) { "HTP0" -> "NPU"; "GPUOpenCL" -> "GPU"; else -> "CPU" }
        ui.state("idle"); ui.status("Cứ nói tự nhiên hoặc nhập câu hỏi. Mô hình chạy trên $where, không cần mạng.")
        return null
    }

    fun stop() {
        running.set(false)
        runCatching { rec?.stop() }; runCatching { rec?.release() }; rec = null
        runCatching { track?.stop() }; runCatching { track?.release() }; track = null
        llm.stop()
        runCatching { rag?.close() }; rag = null
        runCatching { vad?.release() }; runCatching { asr?.release() }; runCatching { tts?.free() }
        vad = null; asr = null; tts = null
        ui.state("idle")
    }

    /** Test hook (adb): runs a 16 kHz mono 16-bit WAV through the whole pipeline as if it had just been spoken. */
    /** Per-stage speed on this phone (adb hook --ez stagebench true): speech recognition and speech synthesis real-time factor,
     *  safety matching time. Same inputs on every phone, so the numbers compare devices, not inputs. */
    fun benchStages(wavs: List<String>): JSONObject {
        val out = JSONObject()
        val a = asr ?: return out.put("error", "asr not loaded")
        val asrMs = ArrayList<Double>(); var audioS = 0.0
        for (w in wavs) {
            val b = File(w).readBytes(); val n = (b.size - 44) / 2
            val x = FloatArray(n) { i -> ((b[44 + 2 * i].toInt() and 0xFF) or (b[45 + 2 * i].toInt() shl 8)).toShort() / 32768f }
            val t0 = System.nanoTime(); val st = a.createStream(); st.acceptWaveform(x, 16000); a.decode(st); a.getResult(st); st.release()
            asrMs.add((System.nanoTime() - t0) / 1e6); audioS += n / 16000.0
        }
        out.put("asr_ms_per_utt", asrMs.sorted()[asrMs.size / 2]).put("asr_rtf", asrMs.sum() / 1000 / audioS).put("asr_n", wavs.size)
        val t = tts ?: return out
        val sentences = listOf("Gọi một một lăm ngay và giữ người bị nạn nằm yên.", "Rửa vết thương bằng xà phòng và nước sạch, rồi che lại bằng vải sạch.",
            "Thủ đô của Nhật Bản là Tô ki ô, một thành phố rất đông dân.", "Khi có động đất, hãy quỳ xuống, che đầu và bám chắc vào bàn.",
            "Không chườm đá, không tắm nước lạnh, không lau cồn cho người đang sốt.")
        val ttsMs = ArrayList<Double>(); var ttsAudio = 0.0
        for (s in sentences) {
            val t0 = System.nanoTime(); val g = t.generate(ViNormalize.normalize(s), 0, speechSpeed)
            ttsMs.add((System.nanoTime() - t0) / 1e6); ttsAudio += g.samples.size.toDouble() / g.sampleRate
        }
        out.put("tts_ms_per_sentence", ttsMs.sorted()[ttsMs.size / 2]).put("tts_rtf", ttsMs.sum() / 1000 / ttsAudio)
        fast.safety?.let { sc ->
            val qs = sc.cards.map { it.title } + sc.cards.map { "Làm sao khi bị " + it.title.lowercase() }
            val t0 = System.nanoTime(); repeat(5) { qs.forEach { q -> sc.match(q) } }
            out.put("safety_ms_per_q", (System.nanoTime() - t0) / 1e6 / (5 * qs.size))
        }
        return out
    }

    fun testWav(path: String) {
        val b = File(path).readBytes()
        val n = (b.size - 44) / 2
        val x = FloatArray(n) { i -> ((b[44 + 2 * i].toInt() and 0xFF) or (b[45 + 2 * i].toInt() shl 8)).toShort() / 32768f }
        val tEnd = System.nanoTime() - (endpointS * 1e9).toLong()   // same convention as live capture
        val done = java.util.concurrent.CountDownLatch(1)
        turnExec.execute { runTurn(x, tEnd); ttsExec.execute { done.countDown() } }
        done.await(60, java.util.concurrent.TimeUnit.SECONDS)
        Thread.sleep(600)
    }

    /** Hold-to-talk: interrupts the assistant, records while held, answers when released. */
    /** Hands-free listening on or off; the models stay loaded so turning it back on is instant. */
    fun setListening(on: Boolean) {
        listening = on; lastActivity = System.currentTimeMillis(); vad?.reset()
        if (!on && !speaking.get()) ui.state("idle")
        ui.listening(on)
        ui.status(if (on) "Đang nghe. Cứ nói tự nhiên; chạm micro để dừng." else "Đã tạm dừng micro. Chạm để nói tiếp.")
    }

    fun pttStart() {
        if (!running.get()) return
        bargeIn(); synchronized(pttBuf) { pttBuf.clear() }
        vad?.reset(); pttHeld = true; ui.state("listening"); ui.status("Đang ghi âm, thả nút khi nói xong.")
    }

    fun pttStop() {
        if (!pttHeld) return
        pttHeld = false
        val x = synchronized(pttBuf) { val n = pttBuf.sumOf { it.size }; val out = FloatArray(n); var o = 0; for (c in pttBuf) { c.copyInto(out, o); o += c.size }; pttBuf.clear(); out }
        if (x.size < 4800) { ui.state("idle"); ui.status("Quá ngắn, hãy giữ nút lâu hơn."); return }
        ui.status("Đang xử lý…")
        val tEnd = System.nanoTime()
        turnExec.execute { runTurn(x, tEnd, ptt = true) }
    }

    /** A typed question (noisy place, or when speaking is not possible). */
    fun askText(text: String) {
        if (!running.get() || text.isBlank()) return
        interrupt()
        val tStart = System.nanoTime()
        turnExec.execute {
            cancelled = false; turnEpoch = epoch; speaking.set(true); ui.state("thinking")
            answerText(text.trim(), JSONObject().put("typed", true), tStart)
        }
    }

    /** Reads a text aloud (a safety card opened in the guide), loading only the voice when the assistant is not running. */
    fun readAloud(text: String) {
        ttsExec.execute {
            if (tts == null) {
                val voice = File(modelsDir, voiceDir)
                val onnx = voice.listFiles { f -> f.name.endsWith(".onnx") }?.firstOrNull() ?: run { ui.status("Thiếu giọng đọc trong ${voice.absolutePath}"); return@execute }
                tts = OfflineTts(null, OfflineTtsConfig(OfflineTtsModelConfig(vits = OfflineTtsVitsModelConfig(model = onnx.absolutePath,
                    tokens = "${voice.absolutePath}/tokens.txt", dataDir = "${voice.absolutePath}/espeak-ng-data"), numThreads = ttsThreads)))
                openTrack(tts!!.sampleRate())
            }
        }
        cancelled = false; turnEpoch = epoch
        speak(text, JSONObject(), System.nanoTime(), fastKind = "card")
        ttsExec.execute { if (!running.get()) ui.state("idle") }
    }

    fun stopReading() { interrupt() }

    val safetyCards: SafetyCards? get() = fast.safety

    fun bargeIn() { interrupt(); ui.status("Đã ngắt lời.") }

    /** "Cuộc trò chuyện mới": forget the previous exchanges. */
    fun clearHistory() { synchronized(history) { history.clear() } }

    private fun interrupt() {
        cancelled = true; epoch++
        runCatching { track?.pause(); track?.flush(); track?.play() }
        framesWritten = 0L                                      // flush resets the playback head
        pendingSpeech.set(0); speaking.set(false); mutedUntil = System.currentTimeMillis() + 300
        ui.state("idle")
    }

    // ------------------------------------------------------------------ audio in
    @Suppress("MissingPermission")
    private fun startCapture() {
        val min = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val r = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, 16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, max(min, 16000))
        if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(r.audioSessionId)?.enabled = true
        if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(r.audioSessionId)?.enabled = true
        if (r.state != AudioRecord.STATE_INITIALIZED) {           // no microphone permission, or the mic is held by another app
            runCatching { r.release() }; ui.status("Không mở được micro. Hãy cho phép quyền micro, vẫn có thể gõ câu hỏi."); return
        }
        r.startRecording(); rec = r
        Thread {
            val buf = ShortArray(512); val f = FloatArray(512); var lastUi = 0L
            while (running.get()) {
                var n = 0
                while (n < 512 && running.get()) { val k = r.read(buf, n, 512 - n); if (k <= 0) break; n += k }
                if (n < 512) break
                var pk = 0; var e = 0.0
                for (i in 0 until 512) { f[i] = buf[i] / 32768f; pk = max(pk, kotlin.math.abs(buf[i].toInt())); e += f[i] * f[i] }
                if (vad?.isSpeechDetected() != true && !speaking.get()) noiseFloor = noiseFloor * 0.98f + 0.02f * kotlin.math.sqrt(e / 512).toFloat()
                val now = System.currentTimeMillis()
                if (now - lastUi > 60) { lastUi = now; ui.level(pk) }
                val v = vad ?: break
                if (pttHeld) { synchronized(pttBuf) { pttBuf.add(f.copyOf()) }; continue }   // push-to-talk: record while the button is held, bypass the VAD
                if (!listening) { v.reset(); continue }                                  // microphone paused by the user or by the silence timeout
                if (speaking.get() || pendingSpeech.get() > 0) lastActivity = now
                if (idleTimeoutS > 0 && now - lastActivity > idleTimeoutS * 1000L) {
                    setListening(false); ui.status("Tạm dừng nghe sau $idleTimeoutS giây không có câu hỏi. Chạm micro để nói tiếp."); continue
                }
                if (speaking.get() || now < mutedUntil) { v.reset(); continue }       // mute while the assistant talks (echo guard)
                v.acceptWaveform(f)
                if (v.isSpeechDetected()) ui.state("listening")
                while (!v.empty()) {
                    val seg = v.front(); v.pop()
                    val tEnd = System.nanoTime() - (endpointS * 1e9).toLong()                // the VAD fires `endpointS` after the last speech
                    turnExec.execute { runTurn(seg.samples, tEnd) }
                }
            }
        }.apply { name = "mic"; priority = Thread.MAX_PRIORITY; start() }
    }

    // ------------------------------------------------------------------ one turn
    private fun runTurn(samples: FloatArray, tSpeechEnd: Long, ptt: Boolean = false) {
        cancelled = false; turnEpoch = epoch
        speaking.set(true)
        ui.state("thinking")
        fun ms(t: Long) = (t - tSpeechEnd) / 1e6
        val m = JSONObject()
        val a = asr ?: return
        val st = a.createStream()
        st.acceptWaveform(samples, 16000); a.decode(st)
        val text = a.getResult(st).text.trim().lowercase(); st.release()
        var ss = 0.0; for (v in samples) ss += v * v
        val rms = kotlin.math.sqrt(ss / maxOf(samples.size, 1))
        m.put("stt_ms", ms(System.nanoTime())); m.put("utt_s", samples.size / 16000.0); m.put("rms", rms).put("noise_floor", noiseFloor.toDouble())
        // a loud room (TV, rain, people) raises the noise floor; an emergency question must never be thrown away as noise
        val urgent = text.isNotBlank() && fast.safety?.match(text) != null
        if (!ptt && !urgent && (rms < maxOf(minRms, minOf(2.5f * noiseFloor, 0.03f)) || text.replace(" ", "").length < minChars)) {          // background noise that the VAD let through: ignore silently
            runCatching { File(ctx.filesDir, "segments.jsonl").appendText(JSONObject().put("text", text).put("rms", rms).put("dur", samples.size / 16000.0).put("ignored", true).toString() + "\n") }
            speaking.set(false); ui.state("idle"); return
        }
        if (!ptt && text.isNotBlank() && text.trim().split(Regex("\\s+")).size < 2 && fast.lookup(text) == null) {   // a lone "ừ"/"alo": not a question
            runCatching { File(ctx.filesDir, "segments.jsonl").appendText(JSONObject().put("text", text).put("rms", rms).put("dur", samples.size / 16000.0).put("ignored", true).put("why", "one word").toString() + "\n") }
            speaking.set(false); ui.state("idle"); return
        }
        runCatching { File(ctx.filesDir, "segments.jsonl").appendText(JSONObject().put("text", text).put("rms", rms).put("dur", samples.size / 16000.0).put("ignored", false).toString() + "\n") }
        lastActivity = System.currentTimeMillis()          // a real question: restart the silence timeout
        ui.partial("—")
        if (text.isBlank()) { speak(noAnswer, m, tSpeechEnd, fastKind = "repeat"); finishTurn("", noAnswer, m, tSpeechEnd, asked = false); return }
        answerText(text, m, tSpeechEnd)
    }

    /** Everything after speech recognition: safety cards / fast path, else RAG + LLM; used by spoken and typed questions. */
    private fun answerText(text: String, m: JSONObject, tSpeechEnd: Long) {
        fun ms(t: Long) = (t - tSpeechEnd) / 1e6
        val q = text.replaceFirstChar { it.uppercase() }
        ui.question(q)
        val hit = if (fastPathEnabled) fast.lookup(text) else null
        if (hit != null) {
            m.put("fast", hit.source).put("intent", hit.intent)
            if (hit.source.startsWith("safety")) ui.safety(if (hit.source == "safety") hit.intent else null)
            ui.answer(hit.say)
            speak(hit.say, m, tSpeechEnd, fastKind = "fast")
            finishTurn(q, hit.say, m, tSpeechEnd); return
        }
        val ctx = rag?.let { r -> val t0 = System.nanoTime(); val c = runCatching { r.context(q) }.getOrNull(); m.put("rag_ms", (System.nanoTime() - t0) / 1e6); m.put("rag_used", c != null); c }
        val user = if (ctx != null) "Thông tin tham khảo: $ctx\nCâu hỏi: $q\nNếu thông tin không liên quan, hãy nói bạn không chắc." else q
        val msgs = JSONArray().put(JSONObject().put("role", "system").put("content", system))
        val now = System.currentTimeMillis()
        synchronized(history) {
            while (history.isNotEmpty() && now - history.first().third > 180_000) history.removeFirst()
            for ((hq, ha, _) in history) { msgs.put(JSONObject().put("role", "user").put("content", hq)); msgs.put(JSONObject().put("role", "assistant").put("content", ha)) }
        }
        msgs.put(JSONObject().put("role", "user").put("content", user))
        if (ackEnabled) { m.put("ack", true); speak(ackPhrases[ackIdx++ % ackPhrases.size], m, tSpeechEnd, fastKind = "ack") }
        m.put("llm_request_ms", ms(System.nanoTime()))
        val seg = Segmenter(firstMaxWords = firstWords); val ans = StringBuilder(); var first = true; var started = false
        // the "Dạ." acknowledgement was already spoken: a leading "Dạ," / "Vâng," of the answer would be said twice
        fun strip() { if (ackEnabled) Regex("^\\s*(Dạ vâng|Dạ|Vâng)[,.!]?\\s+").find(ans)?.let { ans.delete(0, it.range.last + 1) } }
        fun out(cs: List<String>) { for (c in cs) { if (first) { m.put("first_chunk_ms", ms(System.nanoTime())); first = false }; speak(c, m, tSpeechEnd) } }
        val r = try {
            llm.chat(msgs, cancel = { cancelled }) { tok ->
                ans.append(tok)
                if (!started) {
                    if (ans.length < 12) return@chat                         // wait a moment: is it "Dạ, ..." ?
                    started = true; strip(); ui.answer(ans.toString()); out(seg.push(ans.toString()))
                } else { ui.answer(ans.toString()); out(seg.push(tok)) }
            }
        } catch (e: Exception) { ui.status("Lỗi LLM: ${e.message}"); null }
        if (r != null) {
            if (!started) { strip(); ui.answer(ans.toString()); out(seg.push(ans.toString())) }
            out(seg.flush())
            m.put("ttft_ms", r.ttftMs).put("llm_prompt_n", r.promptTokens).put("llm_prompt_ms", r.promptMs).put("llm_pred_n", r.predTokens)
            if (r.predMs > 0) m.put("llm_tok_s", r.predTokens * 1000.0 / r.predMs)
        }
        if (ans.isNotBlank() && !cancelled) synchronized(history) { history.addLast(Triple(q, ans.toString().trim(), System.currentTimeMillis())); while (history.size > historyTurns) history.removeFirst() }
        finishTurn(q, ans.toString(), m, tSpeechEnd)
    }

    private fun finishTurn(q: String, a: String, m: JSONObject, tSpeechEnd: Long, asked: Boolean = true) {
        val e = turnEpoch
        ttsExec.execute {
            // after the last chunk has been played: the 3 s buffer may still hold audio, wait until it has come out
            val trk = track; val t0 = System.currentTimeMillis()
            while (trk != null && !cancelled && e == epoch && (trk.playbackHeadPosition.toLong() and 0xffffffffL) < framesWritten && System.currentTimeMillis() - t0 < 4000) Thread.sleep(20)
            mutedUntil = System.currentTimeMillis() + 400
            speaking.set(false)
            m.put("turn_total_ms", (System.nanoTime() - tSpeechEnd) / 1e6)
            runCatching { File(ctx.filesDir, "turns.jsonl").appendText(JSONObject().put("q", q).put("a", a).put("m", m).toString() + "\n") }
            val fa = m.optDouble("first_audio_ms", -1.0); val aa = m.optDouble("answer_audio_ms", -1.0)
            ui.metrics("Tiếng đầu tiên: " + (if (fa >= 0) "%.0f ms".format(fa) else "–") + "   câu trả lời thật: " + (if (aa >= 0) "%.0f ms".format(aa) else "–") +
                (if (m.has("llm_tok_s")) "   ${"%.0f".format(m.getDouble("llm_tok_s"))} token/s" else "") + (if (m.has("fast")) "   (đường nhanh)" else ""), asked)
            ui.state("idle")
        }
    }

    // ------------------------------------------------------------------ audio out
    private var enhancer: android.media.audiofx.LoudnessEnhancer? = null

    fun setLoud(on: Boolean) { loudBoost = on; runCatching { enhancer?.setTargetGain(if (on) 900 else 0) } }

    private fun openTrack(rate: Int) {
        framesWritten = 0L
        val min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT)
        track = AudioTrack.Builder()
            // media stream on the loudspeaker: the voice-call stream is quiet and may go to the earpiece
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
            .setBufferSizeInBytes(max(min, rate * 4 * 3))   // 3 s: synthesis of the next sentence overlaps playback, no gap.setTransferMode(AudioTrack.MODE_STREAM)
            .setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY).build().also { it.play() }
        track?.let { tr -> runCatching { enhancer?.release() }; enhancer = runCatching { android.media.audiofx.LoudnessEnhancer(tr.audioSessionId).apply { setTargetGain(if (loudBoost) 900 else 0); enabled = true } }.getOrNull() }
    }

    /** Queues one chunk of text for the speaker; metrics get first_audio_ms (first sound of the turn) and answer_audio_ms (first sound of the answer). */
    private fun speak(text: String, m: JSONObject, tSpeechEnd: Long, fastKind: String? = null) {
        pendingSpeech.incrementAndGet(); ui.state("speaking")
        val e = turnEpoch
        ttsExec.execute {
            try {
                if (cancelled || e != epoch) return@execute
                val t = tts ?: return@execute
                val trk = track ?: return@execute
                val norm = ViNormalize.normalize(text)
                var marked = false
                fun play(x: FloatArray) {
                    if (cancelled || e != epoch) return
                    if (!marked) {
                        marked = true
                        val v = (System.nanoTime() - tSpeechEnd) / 1e6 + 20      // + output buffer start-up
                        if (!m.has("first_audio_ms")) m.put("first_audio_ms", v)
                        if (fastKind != "ack" && !m.has("answer_audio_ms")) m.put("answer_audio_ms", v)
                    }
                    // small blocks: a long pre-synthesised card stops within ~0.25 s when the user asks something else
                    var off = 0
                    while (off < x.size && !cancelled && e == epoch) {
                        val n = minOf(4096, x.size - off)
                        trk.write(x, off, n, AudioTrack.WRITE_BLOCKING); framesWritten += n; off += n
                    }
                }
                val cached = synchronized(phraseCache) { phraseCache[norm] }
                val (head, tail) = splitFirst(norm)
                val headCached = if (cached == null && tail.isNotEmpty())
                    synchronized(phraseCache) { phraseCache[head] } ?: if (fastKind != null) diskGet(head)?.also { x -> synchronized(phraseCache) { phraseCache[head] = x } } else null
                else null
                if (cached != null) play(cached)
                else if (headCached != null) {
                    // pre-synthesised first sentence plays at once; the rest is synthesised while it plays
                    play(headCached)
                    val parts = arrayListOf(headCached)
                    t.generateWithCallback(tail, 0, speechSpeed) { s -> if (cancelled || e != epoch) 0 else { play(s); parts.add(s); 1 } }
                    if (fastKind != null && !cancelled && e == epoch) synchronized(phraseCache) { phraseCache[norm] = parts.reduce { a, b -> a + b } }
                }
                else {
                    val parts = ArrayList<FloatArray>()
                    t.generateWithCallback(norm, 0, speechSpeed) { s -> if (cancelled || e != epoch) 0 else { play(s); parts.add(s); 1 } }
                    if (fastKind != null && parts.isNotEmpty() && e == epoch) synchronized(phraseCache) { phraseCache[norm] = parts.reduce { a, b -> a + b } }
                }
            } finally { pendingSpeech.decrementAndGet() }
        }
    }

    /** bpe.vocab (token + score per line, from bpe.model) for hotword tokenisation; shipped in assets. */
    private fun bpeVocabFile(): String {
        val f = File(ctx.filesDir, "bpe.vocab")
        if (!f.exists()) runCatching { ctx.assets.open("bpe.vocab").use { i -> f.outputStream().use { i.copyTo(it) } } }
        return f.absolutePath
    }

    /** One upper-case phrase per line (the BPE pieces are upper case): every key phrase and combination word of the cards. */
    private fun hotwordsFile(): String? {
        val sc = fast.safety ?: return null
        if (!File(bpeVocabFile()).exists()) return null
        val words = LinkedHashSet<String>()
        for (c in sc.cards) { words.addAll(c.keys); c.combos.forEach { g -> g.forEach { ws -> ws.filter { it.length >= 3 }.forEach { words.add(it) } } } }
        val f = File(ctx.filesDir, "hotwords.txt")
        f.writeText(words.joinToString("\n") { it.uppercase() } + "\n")
        return f.absolutePath
    }

    /** First sentence of a normalised text (cut after . ! ? ;), and the rest. */
    private fun splitFirst(norm: String): Pair<String, String> {
        val m = Regex("[.!?;]\\s+").find(norm) ?: return norm to ""
        return norm.substring(0, m.range.first + 1) to norm.substring(m.range.last + 1)
    }

    /** Pre-synthesised audio on disk, per voice and speed: files/tts_cache/<voice>_<speed>/<sha1 of the text>.f32 */
    private fun cacheFile(norm: String): File {
        val dir = File(ctx.filesDir, "tts_cache/${File(voiceDir).name}_${"%.2f".format(java.util.Locale.ROOT, speechSpeed)}")
        val h = java.security.MessageDigest.getInstance("SHA-1").digest(norm.toByteArray()).joinToString("") { "%02x".format(it) }
        return File(dir, "$h.f32")
    }

    private fun diskGet(norm: String): FloatArray? = runCatching {
        val f = cacheFile(norm); if (!f.exists()) return null
        val b = java.nio.ByteBuffer.wrap(f.readBytes()).order(java.nio.ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        FloatArray(b.remaining()).also { b.get(it) }
    }.getOrNull()

    private fun diskPut(norm: String, x: FloatArray) {
        runCatching {
            val f = cacheFile(norm); f.parentFile?.mkdirs()
            val bb = java.nio.ByteBuffer.allocate(x.size * 4).order(java.nio.ByteOrder.LITTLE_ENDIAN); bb.asFloatBuffer().put(x)
            val tmp = File(f.parentFile, f.name + ".tmp"); tmp.writeBytes(bb.array()); tmp.renameTo(f)
        }
    }

    private fun prewarmPhrases() {
        Thread {
            val t = tts ?: return@Thread
            runCatching {
                // safety cards first: their first sentence is ready in memory, so the answer starts with no synthesis wait
                // (kept on disk too, so after the first launch they are in memory within a fraction of a second)
                fast.safety?.let { sc ->
                    val heads = sc.phrases().map { splitFirst(ViNormalize.normalize(it)).first }.distinct()
                    for (head in heads) diskGet(head)?.let { x -> synchronized(phraseCache) { phraseCache.putIfAbsent(head, x) } }
                    for (head in heads) {
                        if (synchronized(phraseCache) { phraseCache.containsKey(head) }) continue
                        val g = t.generate(head, 0, speechSpeed)
                        synchronized(phraseCache) { phraseCache[head] = g.samples }
                        diskPut(head, g.samples)
                    }
                }
                ctx.assets.open("faq_phone.jsonl").bufferedReader().useLines { ls ->
                    ls.filter { it.isNotBlank() }.flatMap { l -> JSONObject(l).getJSONArray("say").let { a -> (0 until a.length()).map { a.getString(it) } } }.distinct().forEach { s ->
                        val norm = ViNormalize.normalize(s)
                        if (synchronized(phraseCache) { phraseCache.containsKey(norm) }) return@forEach
                        val g = t.generate(norm, 0, speechSpeed)
                        synchronized(phraseCache) { phraseCache[norm] = g.samples }
                    }
                }
                for (a in ackPhrases) { val an = ViNormalize.normalize(a); synchronized(phraseCache) { phraseCache[an] = t.generate(an, 0, speechSpeed).samples } }
                val n = ViNormalize.normalize(noAnswer)
                synchronized(phraseCache) { phraseCache[n] = t.generate(n, 0, speechSpeed).samples }
            }
        }.apply { name = "prewarm"; priority = Thread.MIN_PRIORITY; start() }
    }

    private fun warmup() {
        val msgs = JSONArray().put(JSONObject().put("role", "system").put("content", system)).put(JSONObject().put("role", "user").put("content", "Xin chào"))
        runCatching { llm.chat(msgs, maxTokens = 8) { } }
    }
}
