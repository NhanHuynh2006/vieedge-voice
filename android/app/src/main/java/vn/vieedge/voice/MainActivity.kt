package vn.vieedge.voice

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import kotlin.math.max

/**
 * The phone is the microphone and the speaker of the Pi ("Kết nối Pi"), or runs the whole assistant itself ("Chạy trên máy", see LocalAssistant).
 *   microphone (16 kHz mono, VOICE_COMMUNICATION source = hardware echo cancellation) --> ws://<pi>:8000/audio
 *   speech (int16 at the rate announced by the Pi)                                   <-- ws://<pi>:8000/audio
 *   transcript, answer and the push-to-talk / interrupt commands                      <-> ws://<pi>:8000/ws
 * Plain ws:// on the local network: no certificate warning, unlike the browser page.
 */
class MainActivity : ComponentActivity() {
    private val client = OkHttpClient.Builder().pingInterval(15, TimeUnit.SECONDS).build()
    private val ui = Handler(Looper.getMainLooper())
    private val model = UiModel()

    private var audioWs: WebSocket? = null
    private var ctlWs: WebSocket? = null
    private var rec: AudioRecord? = null
    private var track: AudioTrack? = null
    @Volatile private var running = false
    @Volatile private var generation = 0
    private var local: LocalAssistant? = null
    private var liveMe: Msg? = null
    private var liveBot: Msg? = null
    // bot messages whose turn has not reported its timing yet, oldest first: a new question can arrive while the previous
    // answer is still being read aloud, and that turn's metrics must go to its own message, not to the new one
    private val awaiting = ArrayDeque<Msg>()
    private var lastPi: Msg? = null
    private val speeds = listOf(0.75f, 0.85f, 1.0f)
    @Volatile private var micOn = true
    private var piEnhancer: android.media.audiofx.LoudnessEnhancer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        volumeControlStream = android.media.AudioManager.STREAM_MUSIC     // volume keys change the assistant's speaker volume
        model.host = (getPreferences(MODE_PRIVATE).getString("host", "") ?: "").filter { it.isLetterOrDigit() || it == '.' || it == '-' || it == ':' }
        val prefs = getPreferences(MODE_PRIVATE)
        model.mode = 1                                     // the phone runs everything itself; the Pi path stays in code only
        model.cards = SafetyCards.load(this)
        LocationHub.init(this)
        model.online = isOnline()
        model.device = if (BuildConfig.CPU_ONLY) 2 else prefs.getInt("device", 0)      // the generic build has only the CPU backend
        model.cpuOnly = BuildConfig.CPU_ONLY
        refreshModels()
        model.voice2 = prefs.getInt("voice2", 0); model.ack = prefs.getBoolean("ack", true)
        // on a CPU-only phone the retrieved passage costs 10 to 15 s of prompt processing (TCL T506T), so it starts off
        model.rag = prefs.getBoolean("rag", !BuildConfig.CPU_ONLY)
        model.loud = prefs.getBoolean("loud", true)
        model.speed = prefs.getInt("speed", 1)
        // phones with less than 6 GB of RAM start with the 0.8B model (the 2B one needs about 1.5 GB and is slow on old CPUs)
        val ramGb = (getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager).let { am -> android.app.ActivityManager.MemoryInfo().also { am.getMemoryInfo(it) }.totalMem / 1e9 }
        val first = if (ramGb < 6) listOf("0.8b", "2b") else listOf("2b", "0.8b")
        model.model = prefs.getString("model", null)?.takeIf { it in model.models }
            ?: first.firstNotNullOfOrNull { k -> model.models.firstOrNull { k in it } } ?: model.models.firstOrNull() ?: ""
        refreshAssets()
        model.saveHistory = prefs.getBoolean("save_history", true)
        model.history.addAll(history.load())
        setContent {
            App(model, Actions(toggle = { toggle() },
                pttDown = { if (!model.running) model.status = "Bật micro trước, rồi giữ nút để nói." else if (model.mode == 1) local?.pttStart() else sendCmd("""{"cmd":"ptt","down":true}""") },
                pttUp = { if (model.running) { if (model.mode == 1) local?.pttStop() else sendCmd("""{"cmd":"ptt","down":false}""") } },
                barge = { if (!model.running) model.status = "Chưa có gì để ngắt." else if (model.mode == 1) local?.bargeIn() else sendCmd("""{"cmd":"barge_in"}""") },
                refreshModels = { refreshModels(); refreshAssets() },
                ask = { q -> askQuestion(q) },
                dial = { n -> runCatching { startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:$n"))) } },
                read = { id, text -> model.reading = id; localAssistant().also { it.loudBoost = model.loud; it.speechSpeed = speeds[model.speed] }.readAloud(text) },
                mic = { on -> if (on && !model.running) { listenOnStart = true; toggle() } else if (model.mode == 1) local?.setListening(on) else { micOn = on; model.listening = on; model.status = if (on) "Đang nghe. Cứ nói tự nhiên." else "Đã tạm dừng micro." } },
                loud = { on -> model.loud = on; getPreferences(MODE_PRIVATE).edit().putBoolean("loud", on).apply(); local?.setLoud(on); piEnhancer?.setTargetGain(if (on) 900 else 0) },
                speed = { s -> model.speed = s; getPreferences(MODE_PRIVATE).edit().putInt("speed", s).apply(); local?.speechSpeed = speeds[s] },
                stopRead = { if (model.reading != null) { model.reading = null; local?.stopReading() } },
                newChat = { if (model.running) local?.bargeIn(); local?.clearHistory(); liveBot = null; model.messages.clear(); model.convId = 0L },
                openConv = { id -> model.history.firstOrNull { it.id == id }?.let { c ->
                    if (model.running) local?.bargeIn(); liveBot = null
                    local?.clearHistory(); model.messages.clear(); model.messages.addAll(History.decode(c.msgs)); model.convId = c.id } },
                deleteConv = { id -> model.history.removeAll { it.id == id }; if (model.convId == id) { model.messages.clear(); model.convId = 0L }; history.save(model.history) },
                clearHistory = { model.history.clear(); history.clear() },
                setSaveHistory = { on -> model.saveHistory = on; getPreferences(MODE_PRIVATE).edit().putBoolean("save_history", on).apply() },
                openUrl = { u -> runCatching { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(u))) } },
                locate = { locate() },
                locationSettings = { runCatching { startActivity(android.content.Intent(android.provider.Settings.ACTION_LOCATION_SOURCE_SETTINGS)) } },
                copyText = { s -> (getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager).setPrimaryClip(android.content.ClipData.newPlainText("Vị trí", s))
                    android.widget.Toast.makeText(this, "Đã chép vị trí", android.widget.Toast.LENGTH_SHORT).show() },
                sms = { s -> runCatching { startActivity(android.content.Intent(android.content.Intent.ACTION_SENDTO, android.net.Uri.parse("smsto:")).putExtra("sms_body", s)) } },
                openMap = { model.openCard = null; model.screen = 4 },
                setMark = { pt -> LocationHub.setMark(this, pt) }))
        }
        handleTestIntent()
    }

    /** adb test hook: am start -n vn.vieedge.voice/.MainActivity --es model X.gguf --es device HTP0 --es wavs /path/a.wav,/path/b.wav */
    private fun handleTestIntent() {
        if (intent?.getBooleanExtra("sqltest", false) == true) {
            Thread {
                val out = StringBuilder()
                try {
                    val db = io.requery.android.database.sqlite.SQLiteDatabase.create(null)
                    db.rawQuery("select sqlite_version()", null).use { it.moveToFirst(); out.append("sqlite ").append(it.getString(0)) }
                    db.execSQL("create virtual table t using fts5(x, tokenize='unicode61 remove_diacritics 2')")
                    db.execSQL("insert into t values ('Hà Nội là thủ đô của Việt Nam')")
                    db.rawQuery("select count(*) from t where t match 'thu do'", null).use { it.moveToFirst(); out.append(" match_no_diacritics=").append(it.getInt(0)) }
                } catch (e: Throwable) { out.append(" ERROR ").append(e.message) }
                android.util.Log.i("VieEdge", "SQLTEST $out")
            }.start()
            return
        }
        intent?.getStringExtra("safety_eval")?.let { name ->   // parity check with bench/eval_safety.py: files/<name> jsonl with "q" per line
            Thread {
                val sc = SafetyCards.load(this)
                val inp = java.io.File(filesDir, name); val outF = java.io.File(filesDir, "safety_eval_out.jsonl")
                var n = 0; val t0 = System.nanoTime()
                outF.bufferedWriter().use { w ->
                    inp.forEachLine { line ->
                        if (line.isBlank()) return@forEachLine
                        val q = org.json.JSONObject(line).getString("q"); val m = sc?.match(q)
                        val got = if (m == null) "khong" else (m.card?.id ?: "du_phong")
                        w.write(org.json.JSONObject().put("q", q).put("got", got).put("key", m?.key ?: "").toString()); w.newLine(); n++
                    }
                }
                android.util.Log.i("VieEdge", "SAFETY done n=$n version=${sc?.version} us_per_q=${(System.nanoTime() - t0) / 1000 / maxOf(n, 1)}")
            }.start()
            return
        }
        val wavs = intent?.getStringExtra("wavs") ?: return
        val modelName = intent.getStringExtra("model") ?: ""
        val device = intent.getStringExtra("device") ?: "HTP0"
        model.mode = 1; model.model = modelName; model.running = true; model.link = "Trên máy (đang tự thử)"
        model.device = listOf("HTP0", "GPUOpenCL", "none").indexOf(device).coerceAtLeast(0)
        model.status = "Đang chạy bài thử tự động bằng adb, màn hình sẽ tự cập nhật."
        Thread {
            val l = localAssistant()
            running = true
            intent.getStringExtra("voice")?.let { l.voiceDir = "tts/$it" }
            l.ackEnabled = intent.getBooleanExtra("ack", false)
            l.ragEnabled = intent.getBooleanExtra("rag", true)
            l.historyTurns = intent.getIntExtra("history", l.historyTurns)
            l.llmThreads = intent.getIntExtra("llmthreads", l.llmThreads)
            l.endpointS = intent.getFloatExtra("endpoint", 0.4f)
            l.firstWords = intent.getIntExtra("words", 3)
            l.vadThreshold = intent.getFloatExtra("vad", l.vadThreshold); l.minSpeechS = intent.getFloatExtra("minspeech", l.minSpeechS)
            l.minRms = intent.getFloatExtra("minrms", l.minRms); l.minChars = intent.getIntExtra("minchars", l.minChars)
            l.useAgc = intent.getBooleanExtra("agc", l.useAgc)
            l.ttsThreads = intent.getIntExtra("ttsthreads", 4)
            l.asrThreads = intent.getIntExtra("asrthreads", l.asrThreads); l.hotwordsOn = intent.getBooleanExtra("hotwords", l.hotwordsOn)
            val repeat = intent.getIntExtra("repeat", 1)
            val power = intent.getBooleanExtra("power", false)
            if (power) powerLog(l, 60)
            val t0 = System.currentTimeMillis()
            val err = l.start(modelName, device)
            android.util.Log.i("VieEdge", "TEST start model=$modelName device=$device err=$err load_s=${(System.currentTimeMillis() - t0) / 1000.0}")
            val listen = intent.getIntExtra("listen", 0)
            if (err == null && intent.getBooleanExtra("stagebench", false)) {
                Thread.sleep(intent.getIntExtra("warm", 12) * 1000L)
                val r = l.benchStages(wavs.split(',')).put("load_s", (System.currentTimeMillis() - t0) / 1000.0)
                runCatching { java.io.File(filesDir, "stagebench.json").writeText(r.toString()) }
                android.util.Log.i("VieEdge", "STAGEBENCH $r")
            } else if (err == null && listen > 0) {
                java.io.File(filesDir, "segments.jsonl").delete()
                Thread.sleep(listen * 1000L)
            } else if (err == null) {
                Thread.sleep(intent.getIntExtra("warm", 12) * 1000L)       // let the phrase cache fill (--ei warm 1: ask right after start)
                for (r in 0 until repeat) for (w in wavs.split(',')) {
                    l.testWav(w)
                    val last = runCatching { java.io.File(filesDir, "turns.jsonl").readLines().lastOrNull() }.getOrNull()   // null: segment ignored
                    android.util.Log.i("VieEdge", "TEST turn wav=$w $last")
                }
            }
            powerRun = false
            android.util.Log.i("VieEdge", "TEST done")
        }.start()
    }

    /** Battery power while the phone is NOT charging: `phase` label + samples of current (µA) and voltage (mV) every second into files/power.csv. */
    private val bm by lazy { getSystemService(BATTERY_SERVICE) as android.os.BatteryManager }
    @Volatile private var powerPhase = "idle"
    @Volatile private var powerRun = false
    private fun powerLog(l: LocalAssistant, idleSeconds: Int) {
        val f = java.io.File(filesDir, "power.csv"); f.writeText("t_s,phase,current_ua,voltage_mv,level,temp_dc,status\n")
        // wait (up to 15 min) until the charger is unplugged: charging current would hide the phone's real consumption
        for (w in 0 until 900) {
            val st = registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))?.getIntExtra("status", 0)
            if (st != 2 && st != 5) break
            post { model.status = "Chờ rút sạc để đo công suất… (${900 - w} s)" }
            Thread.sleep(1000)
        }
        powerRun = true; powerPhase = "idle"
        Thread {
            val t0 = System.currentTimeMillis()
            while (powerRun) {
                val i = android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED)
                val b = registerReceiver(null, i)
                f.appendText("${(System.currentTimeMillis() - t0) / 1000},$powerPhase,${bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)}," +
                    "${b?.getIntExtra("voltage", 0)},${b?.getIntExtra("level", 0)},${b?.getIntExtra("temperature", 0)},${b?.getIntExtra("status", 0)}\n")
                Thread.sleep(1000)
            }
        }.start()
        Thread.sleep(idleSeconds * 1000L)
        powerPhase = "assistant"
    }

    private fun post(block: () -> Unit) = ui.post { block() }

    private fun isOnline(): Boolean = runCatching {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
        cm.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
    }.getOrDefault(false)

    /** Which model files are on the phone, for the settings screen. */
    private fun refreshAssets() {
        val d = localAssistant().modelsDir
        fun has(rel: String) = java.io.File(d, rel).exists()
        model.assets = listOf(
            "Nhận dạng giọng nói (Zipformer)" to has("stt/zipformer-vi/encoder-epoch-20-avg-10.int8.onnx"),
            "Phát hiện giọng nói (Silero)" to has("vad/silero_vad.onnx"),
            "Giọng đọc chuẩn" to has("tts/vits-piper-vi_VN-vais1000-medium"),
            "Giọng đọc nhanh" to has("tts/vits-piper-vi_VN-vivos-x_low"),
            "Wikipedia offline" to has("rag/wiki_vi.sqlite"),
            "Mô hình ngôn ngữ (${model.models.size} file)" to model.models.isNotEmpty(),
            "Hướng dẫn an toàn (${model.cards?.cards?.size ?: 0} thẻ)" to (model.cards != null))
    }

    // ------------------------------------------------------------------ on-device assistant callbacks
    private val localUi = object : LocalAssistant.Ui {
        override fun status(t: String) { post { model.status = t } }
        override fun state(s: String) { post { model.voice = s; if (s == "idle") model.reading = null } }
        override fun partial(t: String) { }
        override fun question(t: String) { post {
            if (pendingEcho == t && liveBot != null) { pendingEcho = null; awaiting.addLast(liveBot!!); return@post }      // already shown while the models were loading
            pendingEcho = null
            model.messages.add(Msg("me", t)); liveBot = Msg("bot", "…", true).also { model.messages.add(it); awaiting.addLast(it) } } }
        override fun listening(on: Boolean) { post { model.listening = on } }
        override fun safety(cardId: String?) { post { liveBot?.let { if (cardId != null) it.card = cardId else it.fallback = true } } }
        override fun answer(t: String) { post { (liveBot ?: Msg("bot", t).also { model.messages.add(it); liveBot = it }).text = t } }
        override fun metrics(t: String, asked: Boolean) { post {
            if (asked) awaiting.removeFirstOrNull()?.let { it.live = false; setChips(it, t); if (it === liveBot) liveBot = null }
            saveConversation() } }
        override fun level(pk: Int) { post { model.level = minOf(1f, pk / 9000f) } }
    }

    private val history by lazy { History(filesDir) }

    /** Store the conversation on screen (after each finished answer), newest first. */
    private fun saveConversation() {
        if (!model.saveHistory || model.messages.none { it.role == "me" }) return
        val msgs = History.encode(model.messages)
        val now = System.currentTimeMillis()
        val c = model.history.firstOrNull { it.id == model.convId }
            ?: Conv(now, "", now, msgs).also { model.convId = it.id }
        c.msgs = msgs; c.updated = now
        c.title = model.messages.first { it.role == "me" }.text.trim().replaceFirstChar { it.uppercase() }.take(80)
        model.history.remove(c); model.history.add(0, c)
        while (model.history.size > History.MAX) model.history.removeAt(model.history.size - 1)
        history.save(model.history)
    }

    private fun setChips(msg: Msg, t: String) {
        msg.chips.clear()
        fun sec(s: String) = s.removeSuffix(" ms").toDoubleOrNull()?.let { "%.2f s".format(it / 1000) } ?: "–"
        val first = Regex("Tiếng đầu tiên: ([^ ]+ ms|–)").find(t)?.groupValues?.get(1)
        val real = Regex("câu trả lời thật: ([^ ]+ ms|–)").find(t)?.groupValues?.get(1)
        val tok = Regex("(\\d+) token/s").find(t)?.groupValues?.get(1)
        val path = when { msg.card != null || msg.fallback -> "hướng dẫn an toàn"; "đường nhanh" in t -> "đường nhanh"; else -> "mô hình ngôn ngữ" }
        if (first != null) msg.chips.add("tiếng đầu" to sec(first))
        if (real != null && real != first) msg.chips.add("trả lời" to sec(real))
        if (tok != null) msg.chips.add("tốc độ" to "$tok tok/s")
        model.last = listOfNotNull(first?.let { "Tiếng đầu tiên" to sec(it) }, real?.let { "Câu trả lời thật" to sec(it) }, tok?.let { "Tốc độ sinh" to "$it token/s" }, "Đường xử lý" to path)
    }

    private fun localAssistant() = local ?: LocalAssistant(this, localUi).also { local = it }

    private fun refreshModels() {
        val l = localAssistant()
        model.models = l.llmFiles()
        if (model.model !in model.models) model.model = model.models.firstOrNull() ?: ""
        if (model.models.isEmpty()) model.status = "Chép file .gguf vào ${l.modelsDir}/llm/ bằng adb."
    }

    // ------------------------------------------------------------------ start / stop
    private fun askQuestion(q: String) {
        if (!model.running) {
            pending = q; pendingEcho = q; listenOnStart = false
            model.messages.add(Msg("me", q)); liveBot = Msg("bot", "…", true).also { model.messages.add(it) }; toggle()
        } else if (model.mode == 1) local?.askText(q) else sendCmd(JSONObject().put("cmd", "ask").put("text", q).toString())
    }

    /** adb test hook: am start -n vn.vieedge.voice/.MainActivity --es ask "câu hỏi" (types a question as if from the keyboard). */
    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent); setIntent(intent)
        intent.getStringExtra("ask")?.let { model.screen = 0; askQuestion(it) }
        // adb hook for screenshots without tapping: --ei screen 0..4 (chat, safety guide, settings, history, location), --es card <id>
        intent.getIntExtra("screen", -1).takeIf { it >= 0 }?.let { model.openCard = null; model.screen = it }
        intent.getStringExtra("card")?.let { model.openCard = it }
    }

    private var pending: String? = null       // a typed question sent before the models were loaded
    private var listenOnStart = true
    private var pendingEcho: String? = null

    private fun toggle() {
        if (running) { stop("Đã tắt."); return }
        if (model.mode == 0 && model.host.isBlank()) { model.status = "Nhập địa chỉ IP của Pi trước."; return }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1)
        } else start()
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<String>, results: IntArray) {
        if (code == 2) { LocationHub.start(this); return }
        if (results.isNotEmpty() && results[0] == PackageManager.PERMISSION_GRANTED) start() else model.status = "Cần cho phép micro."
    }

    /** GPS on (asks for permission the first time). The position is shown on every emergency answer and spoken on request. */
    private fun locate() {
        if (!LocationHub.has(this)) requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), 2)
        else LocationHub.start(this)
    }

    override fun onStart() { super.onStart(); if (LocationHub.has(this)) LocationHub.start(this) }
    override fun onStop() { super.onStop(); if (!running) LocationHub.stop() }   // keep GPS while the assistant is on

    private fun start() {
        getPreferences(MODE_PRIVATE).edit().putBoolean("loud", model.loud).putInt("mode", model.mode).putInt("device", model.device).putString("model", model.model).putInt("voice2", model.voice2).putBoolean("ack", model.ack).putBoolean("rag", model.rag).apply()
        running = true; model.running = true; model.online = isOnline()
        awaiting.clear()                                        // no turn can be in flight before the models are loaded
        if (model.mode == 1) {
            val l = localAssistant()
            val dev = listOf("HTP0", "GPUOpenCL", "none")[model.device]
            val name = model.model
            l.voiceDir = if (model.voice2 == 1) "tts/vits-piper-vi_VN-vivos-x_low" else "tts/vits-piper-vi_VN-vais1000-medium"
            l.ackEnabled = model.ack
            l.ragEnabled = model.rag
            l.loudBoost = model.loud; l.speechSpeed = speeds[model.speed]
            model.link = "Trên máy"; model.status = "Đang nạp mô hình…"; model.loading = true
            Thread {
                val err = try { l.start(name, dev) } catch (e: Throwable) { "Lỗi: ${e.javaClass.simpleName} ${e.message}" }
                post { model.loading = false }
                if (err != null) { pending = null; post { liveBot?.let { if (it.text == "…") model.messages.remove(it) }; liveBot = null }; stop(err) }
                else {
                    if (!listenOnStart) l.setListening(false)
                    pending?.let { q -> pending = null; l.askText(q) }
                }
            }.start()
            return
        }
        val ip = model.host.filter { it.isLetterOrDigit() || it == '.' || it == '-' || it == ':' }   // keyboards may add a trailing comma or space
        model.host = ip
        getPreferences(MODE_PRIVATE).edit().putString("host", ip).apply()
        val gen = ++generation
        model.status = "Đang kết nối tới $ip…"; model.link = "Đang nối"
        ctlWs = client.newWebSocket(Request.Builder().url("ws://$ip:8000/ws").build(), ctlListener(gen))
        audioWs = client.newWebSocket(Request.Builder().url("ws://$ip:8000/audio").build(), audioListener(gen))
    }

    private fun stop(msg: String) {
        running = false
        generation++
        runCatching { local?.stop() }
        runCatching { audioWs?.close(1000, null) }; runCatching { ctlWs?.close(1000, null) }
        audioWs = null; ctlWs = null
        runCatching { rec?.stop() }; runCatching { rec?.release() }; rec = null
        runCatching { track?.stop() }; runCatching { track?.release() }; track = null
        post { model.running = false; model.loading = false; model.voice = "idle"; model.level = 0f; model.status = msg; model.link = "Chưa kết nối" }
    }

    private fun lost(gen: Int, why: String) {
        if (!running || gen != generation) return
        stop("Mất kết nối ($why). Đang nối lại…")
        ui.postDelayed({ if (!running) toggle() }, 2000)
    }

    private fun sendCmd(json: String) { ctlWs?.send(json) }

    // ------------------------------------------------------------------ Pi audio socket
    private fun audioListener(gen: Int) = object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            val j = JSONObject(text)
            when (j.optString("type")) {
                "hello" -> { micOn = true; post { model.listening = true }; startPlayback(j.getInt("rate")); startCapture(j.optInt("mic_rate", 16000), gen); post { model.status = "Đã kết nối. Hãy nói tiếng Việt."; model.link = "Pi · ." + model.host.trim().substringAfterLast('.') } }
                "error" -> stop(j.optString("message"))
            }
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            track?.write(bytes.toByteArray(), 0, bytes.size)             // blocking write paces us to the audio clock
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = lost(gen, t.message ?: "lỗi mạng")
        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = lost(gen, "đóng")
    }

    private fun startPlayback(rate: Int) {
        val min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val t = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
            .setBufferSizeInBytes(max(min, rate / 5 * 2)).setTransferMode(AudioTrack.MODE_STREAM)
            .setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY).build()
        t.write(ByteArray(rate / 25 * 2), 0, rate / 25 * 2)
        t.play()
        track = t
        piEnhancer = runCatching { android.media.audiofx.LoudnessEnhancer(t.audioSessionId).apply { setTargetGain(if (model.loud) 900 else 0); enabled = true } }.getOrNull()
    }

    @Suppress("MissingPermission")
    private fun startCapture(rate: Int, gen: Int) {
        val frame = rate / 50 * 2                              // 20 ms of int16 = the Pi's period
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val r = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, max(min, frame * 8))
        if (r.state != AudioRecord.STATE_INITIALIZED) { stop("Không mở được micro."); return }
        if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(r.audioSessionId)?.enabled = true
        if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(r.audioSessionId)?.enabled = true
        r.startRecording(); rec = r
        Thread {
            val buf = ByteArray(frame); var lastUi = 0L
            while (running && gen == generation) {
                var n = 0
                while (n < frame && running) { val k = r.read(buf, n, frame - n); if (k <= 0) break; n += k }
                if (n < frame) break
                if (micOn) audioWs?.send(buf.toByteString(0, frame)) else java.util.Arrays.fill(buf, 0.toByte())
                val now = System.currentTimeMillis()
                if (now - lastUi > 50) {
                    var pk = 0
                    for (i in 0 until frame step 2) pk = max(pk, abs(((buf[i + 1].toInt() shl 8) or (buf[i].toInt() and 0xFF)).toShort().toInt()))
                    lastUi = now; post { model.level = minOf(1f, pk / 9000f) }
                }
            }
        }.apply { name = "mic"; priority = Thread.MAX_PRIORITY; start() }
    }

    // ------------------------------------------------------------------ transcript from the Pi
    private fun ctlListener(gen: Int) = object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            val j = JSONObject(text)
            post {
                when (j.optString("type")) {
                    "hello", "state" -> model.voice = j.optString("state")
                    "partial" -> { val m = liveMe ?: Msg("me", "", true).also { model.messages.add(it); liveMe = it }; m.text = j.optString("text") }
                    "final" -> {
                        val t = j.optString("text")
                        val m = liveMe ?: Msg("me", "").also { model.messages.add(it) }
                        m.live = false; m.text = t.ifBlank { "(không nghe rõ)" }; liveMe = null
                        liveBot?.let { if (it.text == "…") model.messages.remove(it) }          // a previous turn that never got an answer
                        liveBot = if (t.isBlank()) null else Msg("bot", "…", true).also { model.messages.add(it) }
                    }
                    "token" -> { val m = liveBot ?: Msg("bot", "").also { model.messages.add(it); liveBot = it }; m.text = (if (m.text == "…") "" else m.text) + j.optString("text") }
                    "answer_done" -> { liveBot?.let { it.text = j.optString("text"); it.live = false; lastPi = it }; liveBot = null }
                    "reflex" -> {
                        val m = liveBot ?: Msg("bot", "").also { model.messages.add(it) }; m.text = j.optString("text"); m.live = false
                        when (j.optString("source")) { "safety" -> m.card = j.optString("intent"); "safety-fallback" -> m.fallback = true }
                        lastPi = m; liveBot = null
                    }
                    "turn" -> {
                        val target = lastPi ?: model.messages.lastOrNull { it.role == "bot" }
                        target?.chips?.clear()
                        val mm = j.optJSONObject("metrics")
                        mm?.optDouble("first_audio_ms")?.takeIf { !it.isNaN() }?.let { target?.chips?.add("tiếng đầu" to "%.2f s".format(it / 1000)) }
                        j.optJSONObject("meta")?.optDouble("llm_tok_s")?.takeIf { !it.isNaN() && it > 0 }?.let { target?.chips?.add("tốc độ" to "%.0f tok/s".format(it)) }
                        lastPi = null
                    }
                }
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = lost(gen, t.message ?: "lỗi mạng")
    }

    override fun onDestroy() { stop(""); super.onDestroy() }
}
