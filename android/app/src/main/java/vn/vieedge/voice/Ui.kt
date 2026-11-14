@file:OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)

package vn.vieedge.voice

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Call
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Menu
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/** One palette for light and dark: calm ink-blue ground, one accent, colour encodes the voice state; red only for emergencies. */
class Palette(val dark: Boolean) {
    val bg = if (dark) Color(0xFF0A1020) else Color(0xFFF3F5FA)
    val card = if (dark) Color(0xFF131C31) else Color.White
    val card2 = if (dark) Color(0xFF1A2540) else Color(0xFFEDF1F8)
    val line = if (dark) Color(0xFF243152) else Color(0xFFDCE3EF)
    val ink = if (dark) Color(0xFFEAF0FF) else Color(0xFF0E1A33)
    val muted = if (dark) Color(0xFF93A3C6) else Color(0xFF55627F)
    val faint = if (dark) Color(0xFF5E6E94) else Color(0xFF8B97B3)
    val accent = if (dark) Color(0xFF7391FF) else Color(0xFF2F5BEA)
    val accentSoft = if (dark) Color(0xFF1D2A52) else Color(0xFFE6ECFE)
    val onAccent = if (dark) Color(0xFF0A1020) else Color.White
    val listen = if (dark) Color(0xFF4CC9F0) else Color(0xFF0A8FBA)
    val think = if (dark) Color(0xFFF5C453) else Color(0xFFB7791F)
    val speak = if (dark) Color(0xFF6EE7B0) else Color(0xFF14895F)
    val sos = if (dark) Color(0xFFFF5D68) else Color(0xFFD92D3A)
    val sosSoft = if (dark) Color(0xFF3A1820) else Color(0xFFFDE8EA)
    val okSoft = if (dark) Color(0xFF12321F) else Color(0xFFE3F6EC)
    val warn = if (dark) Color(0xFFFFB04D) else Color(0xFFC2620A)
}

private val Body = FontFamily(Font(R.font.bevietnam_regular, FontWeight.Normal), Font(R.font.bevietnam_medium, FontWeight.Medium),
    Font(R.font.bevietnam_semibold, FontWeight.SemiBold), Font(R.font.bevietnam_bold, FontWeight.Bold))
private val Display = FontFamily(Font(R.font.bricolage, FontWeight.SemiBold, variationSettings = FontVariation.Settings(FontVariation.weight(650))),
    Font(R.font.bricolage, FontWeight.Bold, variationSettings = FontVariation.Settings(FontVariation.weight(750))))
private val Mono = FontFamily(Font(R.font.jetbrains_mono, FontWeight.Normal, variationSettings = FontVariation.Settings(FontVariation.weight(450))),
    Font(R.font.jetbrains_mono, FontWeight.SemiBold, variationSettings = FontVariation.Settings(FontVariation.weight(650))))

/** One chat bubble. `card` = id of the vetted safety card that answered, `fallback` = emergency without a card. */
class Msg(val role: String, text: String, live: Boolean = false) {
    var text by mutableStateOf(text)
    var live by mutableStateOf(live)
    var card by mutableStateOf<String?>(null)
    var fallback by mutableStateOf(false)
    var path by mutableStateOf("")                      // "nhanh" | "an toàn" | "" (LLM)
    val chips = mutableStateListOf<Pair<String, String>>()
}

/** Everything the screen shows; the activity writes into it from its callbacks. */
class UiModel {
    var cpuOnly by mutableStateOf(false)               // generic build: llama.cpp for plain ARMv8.0, no NPU/GPU backends
    var screen by mutableStateOf(0)                     // 0 = chat, 1 = safety guide, 2 = settings, 3 = history
    var mode by mutableStateOf(1)                       // 0 = connect to the Pi, 1 = run on this phone
    var host by mutableStateOf("")
    var models by mutableStateOf(listOf<String>())
    var model by mutableStateOf("")
    var device by mutableStateOf(0)
    var voice2 by mutableStateOf(0)                     // 0 = standard voice, 1 = fast voice (lower quality, ~0.2 s sooner)
    var rag by mutableStateOf(true)                     // offline Wikipedia lookup
    var ack by mutableStateOf(true)                     // instant "Dạ." while the model thinks
    var running by mutableStateOf(false)
    var loading by mutableStateOf(false)
    var status by mutableStateOf("Hỏi đáp bằng tiếng Việt, xử lý ngay trên điện thoại")
    var voice by mutableStateOf("idle")                 // idle | listening | thinking | speaking
    var level by mutableStateOf(0f)
    var link by mutableStateOf("Chưa kết nối")
    var online by mutableStateOf(false)                 // the phone has a network (shown only as information: nothing needs it)
    var draft by mutableStateOf("")
    var listening by mutableStateOf(false)              // hands-free microphone on
    var loud by mutableStateOf(true)                    // +9 dB on the speaker
    var speed by mutableStateOf(1)                      // 0 = slow, 1 = medium (default), 2 = model default
    var openCard by mutableStateOf<String?>(null)
    var reading by mutableStateOf<String?>(null)
    var query by mutableStateOf("")
    var group by mutableStateOf(0)
    var cards by mutableStateOf<SafetyCards?>(null)
    var assets by mutableStateOf(listOf<Pair<String, Boolean>>())   // model files present on the phone
    var last by mutableStateOf(listOf<Pair<String, String>>())     // metrics of the last turn
    val messages = mutableStateListOf<Msg>()
    var convId by mutableStateOf(0L)                    // conversation being shown (0 = new, not saved yet)
    val history = mutableStateListOf<Conv>()
    var saveHistory by mutableStateOf(true)
}

class Actions(val toggle: () -> Unit, val pttDown: () -> Unit, val pttUp: () -> Unit, val barge: () -> Unit, val refreshModels: () -> Unit,
              val ask: (String) -> Unit, val dial: (String) -> Unit, val read: (String, String) -> Unit, val stopRead: () -> Unit,
              val openUrl: (String) -> Unit, val mic: (Boolean) -> Unit, val loud: (Boolean) -> Unit,
              val speed: (Int) -> Unit, val newChat: () -> Unit,
              val openConv: (Long) -> Unit, val deleteConv: (Long) -> Unit, val clearHistory: () -> Unit, val setSaveHistory: (Boolean) -> Unit,
              val locate: () -> Unit, val locationSettings: () -> Unit, val copyText: (String) -> Unit, val sms: (String) -> Unit,
              val openMap: () -> Unit, val setMark: (Pair<Double, Double>?) -> Unit)

private val deviceNames = listOf("NPU", "GPU", "CPU")
private val groups = listOf("" to "Tất cả", "so_cuu" to "Sơ cứu", "thien_tai" to "Thiên tai", "sinh_ton" to "Sinh tồn")
private fun voiceName(s: String) = when (s) { "listening" -> "Đang nghe"; "thinking" -> "Đang nghĩ"; "speaking" -> "Đang nói"; else -> "Sẵn sàng" }
private fun groupName(g: String) = groups.firstOrNull { it.first == g }?.second ?: ""

/** "qwen3.5-2b-vi-voice-Q4_0-imx.gguf" -> "Qwen3.5 2B · Q4_0 · imatrix" */
fun prettyModel(f: String): String {
    val s = f.removeSuffix(".gguf")
    val size = Regex("(\\d+(?:\\.\\d+)?)b", RegexOption.IGNORE_CASE).find(s)?.groupValues?.get(1)?.replace('.', ',')?.let { "${it}B" } ?: ""
    val quant = Regex("(Q\\d_[0-9A-Z_]+?|IQ\\d_[A-Z]+|F16)(?=-|$)").find(s)?.value ?: ""
    val family = if (s.startsWith("qwen3.5")) "Qwen3.5" else if (s.startsWith("qwen2.5")) "Qwen2.5" else if (s.startsWith("gemma")) "Gemma" else s.substringBefore('-')
    return listOf(family + if (size.isNotEmpty()) " $size" else "", quant, if ("imx" in s) "imatrix" else "").filter { it.isNotBlank() }.joinToString(" · ")
}

@Composable
fun App(m: UiModel, a: Actions) {
    val p = Palette(isSystemInDarkTheme())
    BackHandler(enabled = m.openCard != null || m.screen != 0) { if (m.openCard != null) { m.openCard = null; a.stopRead() } else m.screen = 0 }
    Box(Modifier.fillMaxSize().background(p.bg)) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            androidx.compose.animation.AnimatedContent(m.screen, transitionSpec = {
                (fadeIn(tween(220)) + slideInHorizontally(tween(260)) { if (targetState == 3 || initialState == 3) (if (targetState == 3) -it / 6 else it / 6) else if (targetState > initialState) it / 6 else -it / 6 }) togetherWith fadeOut(tween(160))
            }, label = "screen") { s ->
                when (s) {
                    0 -> ChatScreen(m, p, a)
                    1 -> Column { ScreenHeader("An toàn khi mất sóng", p) { m.screen = 0 }; SafetyScreen(m, p, a) }
                    3 -> Column { ScreenHeader("Lịch sử trò chuyện", p) { m.screen = 0 }; HistoryScreen(m, p, a) }
                    4 -> Column { ScreenHeader("Vị trí và bản đồ", p) { m.screen = 0 }; LocationScreen(m, p, a) }
                    else -> Column { ScreenHeader("Cài đặt", p) { m.screen = 0 }; SettingsScreen(m, p, a) }
                }
            }
        }
        AnimatedVisibility(m.openCard != null, enter = slideInVertically { it / 3 } + fadeIn(), exit = slideOutVertically { it / 3 } + fadeOut()) {
            m.cards?.byId(m.openCard)?.let { CardDetail(it, m, p, a) }
        }
    }
}

// ===================================================================== shared pieces
@Composable
private fun T(t: String, p: Palette, size: Int, font: FontFamily = Body, weight: FontWeight = FontWeight.Normal, modifier: Modifier = Modifier,
              color: Color = p.ink, center: Boolean = false, lines: Int = Int.MAX_VALUE, height: Float = 1.42f) =
    androidx.compose.material3.Text(t, modifier, color = color, fontFamily = font, fontWeight = weight, fontSize = size.sp, lineHeight = (size * height).sp,
        textAlign = if (center) TextAlign.Center else null, maxLines = lines, overflow = if (lines < Int.MAX_VALUE) TextOverflow.Ellipsis else TextOverflow.Clip)

@Composable
private fun Pill(t: String, p: Palette, dot: Color, strong: Boolean = false) {
    Row(Modifier.clip(RoundedCornerShape(50)).background(p.card).border(1.dp, p.line, RoundedCornerShape(50)).padding(horizontal = 11.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(7.dp).clip(CircleShape).background(dot))
        Spacer(Modifier.width(6.dp))
        T(t, p, 12, weight = if (strong) FontWeight.SemiBold else FontWeight.Medium, color = if (strong) p.ink else p.muted, lines = 1)
    }
}

@Composable
private fun Section(title: String, p: Palette, hint: String? = null, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(bottom = 14.dp)) {
        T(title.uppercase(), p, 11, weight = FontWeight.Bold, color = p.faint, modifier = Modifier.padding(start = 4.dp, bottom = 7.dp))
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(18.dp)).padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) { content() }
        if (hint != null) T(hint, p, 12, color = p.faint, modifier = Modifier.padding(start = 4.dp, top = 6.dp, end = 4.dp))
    }
}

@Composable
private fun Segmented(items: List<String>, selected: Int, p: Palette, enabled: Boolean = true, onPick: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(p.card2).padding(3.dp)) {
        items.forEachIndexed { i, label ->
            Box(Modifier.weight(1f).clip(RoundedCornerShape(10.dp)).background(if (selected == i) p.accent else Color.Transparent)
                .clickable(enabled) { onPick(i) }.padding(vertical = 9.dp), contentAlignment = Alignment.Center) {
                T(label, p, 13, weight = FontWeight.SemiBold, color = if (selected == i) p.onAccent else if (enabled) p.muted else p.faint, lines = 1)
            }
        }
    }
}

@Composable
private fun ToggleRow(title: String, sub: String, on: Boolean, p: Palette, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f).padding(end = 10.dp)) {
            T(title, p, 15, weight = FontWeight.SemiBold, color = if (enabled) p.ink else p.faint)
            T(sub, p, 12, color = p.muted)
        }
        Switch(on, onChange, enabled = enabled, colors = SwitchDefaults.colors(checkedTrackColor = p.accent, checkedThumbColor = Color.White,
            checkedBorderColor = p.accent, uncheckedTrackColor = p.card2, uncheckedBorderColor = p.line, uncheckedThumbColor = p.faint,
            disabledCheckedTrackColor = p.accent.copy(alpha = 0.45f), disabledCheckedThumbColor = Color.White))
    }
}

@Composable
private fun IconBtn(icon: ImageVector, desc: String, p: Palette, bg: Color, fg: Color, size: Dp = 44.dp, onClick: () -> Unit) {
    Box(Modifier.size(size).clip(CircleShape).background(bg).clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Icon(icon, desc, tint = fg, modifier = Modifier.size(size * 0.48f))
    }
}

@Composable
private fun CallButton(number: String, label: String, p: Palette, strong: Boolean, modifier: Modifier = Modifier, a: Actions) {
    Row(modifier.clip(RoundedCornerShape(14.dp)).background(if (strong) p.sos else p.sosSoft).clickable { a.dial(number) }
        .padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Rounded.Call, null, tint = if (strong) Color.White else p.sos, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Column {
            T(number, p, 17, Display, FontWeight.Bold, color = if (strong) Color.White else p.sos, height = 1.1f)
            T(label, p, 11, weight = FontWeight.Medium, color = if (strong) Color.White.copy(alpha = 0.9f) else p.sos, lines = 1, height = 1.2f)
        }
    }
}

// ===================================================================== chat (home)
@Composable
private fun TopBar(m: UiModel, p: Palette, a: Actions) {
    Row(Modifier.fillMaxWidth().padding(start = 4.dp, end = 10.dp, top = 6.dp, bottom = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        IconBtn(Icons.Rounded.Menu, "Lịch sử trò chuyện", p, Color.Transparent, p.ink, 46.dp) { m.screen = 3 }
        Spacer(Modifier.width(4.dp))
        Column(Modifier.weight(1f)) {
            T("VieEdge", p, 20, Display, FontWeight.Bold, lines = 1, height = 1.2f)
            val sub = when {
                m.loading -> "Đang chuẩn bị…"
                m.running && m.voice != "idle" -> voiceName(m.voice)
                m.running && m.listening -> "Đang nghe"
                m.running -> "Sẵn sàng"
                else -> prettyModel(m.model).substringBefore(" · ").ifEmpty { "Trợ lý giọng nói" }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(6.dp).clip(CircleShape).background(if (m.running) stateColor(if (m.voice == "idle" && m.listening) "listening" else m.voice, p) else p.faint))
                Spacer(Modifier.width(6.dp))
                T(sub, p, 12, weight = FontWeight.Medium, color = p.muted, lines = 1, height = 1.2f)
            }
        }
        if (m.messages.isNotEmpty()) IconBtn(Icons.Rounded.Edit, "Cuộc trò chuyện mới", p, Color.Transparent, p.muted, 42.dp) { a.newChat() }
        Box(Modifier.size(42.dp).clip(CircleShape).clickable { m.screen = 1 }, contentAlignment = Alignment.Center) {
            Box(Modifier.size(30.dp).clip(CircleShape).background(p.sosSoft), contentAlignment = Alignment.Center) {
                Icon(Icons.Rounded.Warning, "Hướng dẫn an toàn", tint = p.sos, modifier = Modifier.size(17.dp))
            }
        }
        IconBtn(Icons.Rounded.LocationOn, "Vị trí và bản đồ", p, Color.Transparent, p.muted, 42.dp) { m.screen = 4 }
        IconBtn(Icons.Rounded.Settings, "Cài đặt", p, Color.Transparent, p.muted, 42.dp) { m.screen = 2 }
    }
}

private fun stateColor(s: String, p: Palette) = when (s) { "listening" -> p.listen; "thinking" -> p.think; "speaking" -> p.speak; else -> p.faint }

private fun greeting(): String {
    val h = java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY)
    return when (h) { in 5..10 -> "Chào buổi sáng"; in 11..13 -> "Chào buổi trưa"; in 14..17 -> "Chào buổi chiều"; else -> "Chào buổi tối" }
}

@Composable
private fun ChatScreen(m: UiModel, p: Palette, a: Actions) {
    Column(Modifier.fillMaxSize()) {
        TopBar(m, p, a)
        Box(Modifier.weight(1f).fillMaxWidth()) {
            androidx.compose.animation.Crossfade(m.messages.isEmpty(), animationSpec = tween(350), label = "home") { empty ->
                if (empty) Greeting(m, p) else Messages(m, p, a)
            }
        }
        Composer(m, p, a)
    }
}

@Composable
private fun Greeting(m: UiModel, p: Palette) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Aura(m, p, Modifier.fillMaxWidth().height(340.dp))
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 32.dp)) {
            T(greeting(), p, 30, Display, FontWeight.Bold, center = true, height = 1.15f)
            T(if (m.loading) "Đang chuẩn bị, chỉ vài giây thôi" else "Mình có thể giúp gì cho bạn?", p, 17, color = p.muted, center = true,
                modifier = Modifier.padding(top = 8.dp))
        }
    }
}

/** Soft moving colour field behind the greeting; it brightens and pulses with the voice. */
@Composable
private fun Aura(m: UiModel, p: Palette, modifier: Modifier) {
    val t by rememberInfiniteTransition(label = "aura").animateFloat(0f, 1000f, infiniteRepeatable(tween(1_000_000, easing = LinearEasing), RepeatMode.Restart), label = "t")
    var shown by remember { mutableStateOf(0f) }
    val active = m.running && (m.listening || m.voice != "idle")
    val c1 = if (active) stateColor(if (m.voice == "idle") "listening" else m.voice, p) else p.accent
    val c2 = if (p.dark) Color(0xFF8A5CF6) else Color(0xFF9B7BFF)
    Canvas(modifier) {
        shown += (m.level - shown) * 0.15f
        val w = size.width; val h = size.height
        val amp = if (active) 1f + shown * 0.6f else 1f
        val alpha = if (p.dark) 0.30f else 0.22f
        for ((i, c) in listOf(c1, c2, c1).withIndex()) {
            val ph = t * (0.18f + i * 0.07f) + i * 2.1f
            val cx = w / 2 + cos(ph) * w * 0.16f
            val cy = h / 2 + sin(ph * 1.3f) * h * 0.12f
            val r = w * (0.30f + 0.04f * sin(ph * 2f)) * amp
            drawCircle(Brush.radialGradient(listOf(c.copy(alpha = alpha), Color.Transparent), Offset(cx, cy), r), r, Offset(cx, cy))
        }
    }
}

@Composable
private fun Messages(m: UiModel, p: Palette, a: Actions) {
    val st = rememberLazyListState()
    LaunchedEffect(m.messages.size, m.messages.lastOrNull()?.text) { if (m.messages.isNotEmpty()) st.animateScrollToItem(m.messages.size - 1) }
    LazyColumn(Modifier.fillMaxSize(), st, contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)) {
        items(m.messages) { msg -> Message(msg, m, p, a) }
    }
}

@Composable
private fun Message(msg: Msg, m: UiModel, p: Palette, a: Actions) {
    if (msg.role == "me") {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
            Box(Modifier.fillMaxWidth(0.84f).wrapContentWidthEnd()) {
                Box(Modifier.align(Alignment.CenterEnd).clip(RoundedCornerShape(22.dp)).background(p.card2).padding(horizontal = 16.dp, vertical = 11.dp)) {
                    T(msg.text, p, 16)
                }
            }
        }
        return
    }
    val safety = msg.card != null || msg.fallback
    val card = m.cards?.byId(msg.card)
    Row(Modifier.fillMaxWidth().animateContentSize()) {
        Box(Modifier.padding(top = 3.dp).size(24.dp).clip(CircleShape).background(if (safety) p.sosSoft else p.accentSoft), contentAlignment = Alignment.Center) {
            if (safety) Icon(Icons.Rounded.Warning, null, tint = p.sos, modifier = Modifier.size(13.dp))
            else Box(Modifier.size(9.dp).clip(CircleShape).background(p.accent))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            if (safety) T(if (card != null) card.title else "Trường hợp chưa có hướng dẫn", p, 13, weight = FontWeight.Bold, color = p.sos,
                modifier = Modifier.padding(bottom = 4.dp))
            if (msg.live && msg.text == "…") TypingDots(p) else T(SafetyCards.display(msg.text), p, 16, height = 1.5f)
            if (safety) {
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val num = card?.call?.ifEmpty { null } ?: "115"
                    CallButton(num, callLabel(num), p, true, a = a)
                    if (card != null) Box(Modifier.height(52.dp).clip(RoundedCornerShape(14.dp)).border(1.dp, p.line, RoundedCornerShape(14.dp))
                        .clickable { m.openCard = card.id }.padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
                        T("Xem các bước", p, 14, weight = FontWeight.SemiBold, lines = 1)
                    } else CallButton("112", callLabel("112"), p, false, a = a)
                }
                LocationStrip(p, a, Modifier.padding(top = 10.dp))
            }
            if (msg.chips.isNotEmpty()) T(msg.chips.joinToString("  ·  ") { "${it.first} ${it.second}" }, p, 11, color = p.faint, lines = 1,
                modifier = Modifier.padding(top = 8.dp))
        }
    }
}

private fun Modifier.wrapContentWidthEnd() = this

@Composable
private fun TypingDots(p: Palette) {
    val t by rememberInfiniteTransition(label = "dots").animateFloat(0f, 1f, infiniteRepeatable(tween(900, easing = LinearEasing)), label = "d")
    Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        for (i in 0 until 3) {
            val ph = ((t + i * 0.18f) % 1f)
            Box(Modifier.size(7.dp).clip(CircleShape).background(p.muted.copy(alpha = 0.3f + 0.7f * (1f - kotlin.math.abs(ph * 2 - 1)))))
        }
    }
}

private fun callLabel(n: String) = when (n) { "115" -> "Cấp cứu"; "112" -> "Cứu nạn"; "114" -> "Cứu hỏa"; "113" -> "Công an"; "111" -> "Bảo vệ trẻ em"; else -> "Gọi" }

@Composable
private fun Composer(m: UiModel, p: Palette, a: Actions) {
    val voiceMode = m.running && (m.listening || m.voice != "idle")
    Box(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp)) {
        androidx.compose.animation.AnimatedContent(voiceMode, transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(180)) }, label = "composer") { voice ->
            if (voice) VoiceBar(m, p, a) else InputBar(m, p, a)
        }
    }
}

@Composable
private fun InputBar(m: UiModel, p: Palette, a: Actions) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(28.dp))
        .padding(start = 20.dp, end = 6.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.weight(1f).padding(vertical = 10.dp)) {
            if (m.draft.isEmpty()) T("Hỏi VieEdge", p, 16, color = p.faint, lines = 1)
            BasicTextField(m.draft, { m.draft = it }, maxLines = 4, cursorBrush = SolidColor(p.accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send), keyboardActions = KeyboardActions(onSend = { send(m, a) }),
                textStyle = TextStyle(color = p.ink, fontFamily = Body, fontSize = 16.sp), modifier = Modifier.fillMaxWidth())
        }
        if (m.draft.isNotBlank()) IconBtn(Icons.AutoMirrored.Rounded.Send, "Gửi", p, p.ink, p.bg, 46.dp) { send(m, a) }
        else Box(Modifier.size(46.dp).clip(CircleShape).background(p.ink).clickable(!m.loading) { if (m.running) a.mic(true) else a.toggle() },
            contentAlignment = Alignment.Center) {
            if (m.loading) Spinner(p.bg, 20.dp) else MicGlyph(p.bg, 22.dp)
        }
    }
}

@Composable
private fun VoiceBar(m: UiModel, p: Palette, a: Actions) {
    val c = stateColor(if (m.voice == "idle") "listening" else m.voice, p)
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(p.card).border(1.dp, c.copy(alpha = 0.55f), RoundedCornerShape(28.dp))
        .padding(start = 18.dp, end = 6.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Wave(m, c, Modifier.width(56.dp).height(28.dp))
        Spacer(Modifier.width(12.dp))
        T(when (m.voice) { "thinking" -> "Đang nghĩ…"; "speaking" -> "Đang trả lời"; else -> "Đang nghe" }, p, 15, weight = FontWeight.Medium,
            lines = 1, modifier = Modifier.weight(1f))
        if (m.voice == "speaking" || m.voice == "thinking")
            Box(Modifier.height(46.dp).clip(RoundedCornerShape(23.dp)).background(p.card2).clickable { a.barge() }.padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
                T("Ngắt", p, 14, weight = FontWeight.SemiBold)
            }
        Spacer(Modifier.width(6.dp))
        IconBtn(Icons.Rounded.Close, "Dừng nghe", p, p.ink, p.bg, 46.dp) { a.barge(); a.mic(false) }
    }
}

/** Five rounded bars that follow the microphone / speaker level. */
@Composable
private fun Wave(m: UiModel, c: Color, modifier: Modifier) {
    val t by rememberInfiniteTransition(label = "wave").animateFloat(0f, 1000f, infiniteRepeatable(tween(1_000_000, easing = LinearEasing), RepeatMode.Restart), label = "t")
    var shown by remember { mutableStateOf(0f) }
    Canvas(modifier) {
        shown += (m.level - shown) * 0.25f
        val n = 5; val gap = size.width / (n * 2f)
        for (i in 0 until n) {
            val base = when (m.voice) { "thinking" -> 0.25f + 0.2f * sin(t * 6f + i); "speaking" -> 0.3f + 0.5f * kotlin.math.abs(sin(t * 7f + i * 0.9f)); else -> 0.18f }
            val hgt = size.height * min(1f, base + shown * (0.6f + 0.4f * sin(t * 9f + i * 1.7f).let { kotlin.math.abs(it) }))
            val x = gap * (1 + i * 2)
            drawLine(c, Offset(x, size.height / 2 - hgt / 2), Offset(x, size.height / 2 + hgt / 2), gap * 0.9f, StrokeCap.Round)
        }
    }
}

@Composable
private fun Spinner(c: Color, size: Dp) {
    val t by rememberInfiniteTransition(label = "spin").animateFloat(0f, 360f, infiniteRepeatable(tween(900, easing = LinearEasing)), label = "r")
    Canvas(Modifier.size(size)) { drawArc(c, t, 270f, false, style = Stroke(this.size.width * 0.12f, cap = StrokeCap.Round)) }
}

private fun send(m: UiModel, a: Actions) { val q = m.draft.trim(); if (q.isNotEmpty()) { m.draft = ""; a.ask(q) } }

@Composable
private fun MicGlyph(c: Color, size: Dp) {
    Canvas(Modifier.size(size)) {
        val w = this.size.width; val mw = w * 0.2f; val mh = w * 0.5f
        drawRoundRect(c, Offset(w / 2 - mw, w * 0.06f), Size(mw * 2, mh), androidx.compose.ui.geometry.CornerRadius(mw))
        drawArc(c, 20f, 140f, false, Offset(w * 0.18f, w * 0.12f), Size(w * 0.64f, w * 0.64f), style = Stroke(w * 0.09f, cap = StrokeCap.Round))
        drawLine(c, Offset(w / 2, w * 0.76f), Offset(w / 2, w * 0.94f), w * 0.09f, StrokeCap.Round)
    }
}

@Composable
private fun ScreenHeader(title: String, p: Palette, onBack: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 16.dp, top = 6.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        IconBtn(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại", p, Color.Transparent, p.ink, 44.dp, onBack)
        T(title, p, 18, Display, FontWeight.Bold, lines = 1)
    }
}

// ===================================================================== history
@Composable
private fun HistoryScreen(m: UiModel, p: Palette, a: Actions) {
    var q by remember { mutableStateOf("") }
    val items = m.history.filter { q.isBlank() || SafetyCards.stripAccents(it.title.lowercase()).contains(SafetyCards.stripAccents(q.trim().lowercase())) }
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 4.dp).clip(RoundedCornerShape(50)).background(p.card).border(1.dp, p.line, RoundedCornerShape(50))
            .clickable { a.newChat(); m.screen = 0 }.padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.Add, null, tint = p.ink, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(10.dp))
            T("Cuộc trò chuyện mới", p, 15, weight = FontWeight.SemiBold)
        }
        if (m.history.size > 4) Row(Modifier.fillMaxWidth().padding(top = 10.dp).clip(RoundedCornerShape(50)).background(p.card2)
            .padding(horizontal = 16.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.Search, null, tint = p.faint, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(10.dp))
            Box(Modifier.weight(1f)) {
                if (q.isEmpty()) T("Tìm trong lịch sử", p, 15, color = p.faint, lines = 1)
                BasicTextField(q, { q = it }, singleLine = true, cursorBrush = SolidColor(p.accent),
                    textStyle = TextStyle(color = p.ink, fontFamily = Body, fontSize = 15.sp), modifier = Modifier.fillMaxWidth())
            }
        }
        if (m.history.isEmpty()) {
            Column(Modifier.fillMaxWidth().padding(top = 80.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                T("Chưa có cuộc trò chuyện nào", p, 16, weight = FontWeight.SemiBold, center = true)
                T(if (m.saveHistory) "Các câu bạn hỏi sẽ được lưu ở đây, chỉ trên máy này." else "Đang tắt lưu lịch sử trong Cài đặt.", p, 13,
                    color = p.muted, center = true, modifier = Modifier.padding(top = 6.dp))
            }
            return
        }
        LazyColumn(Modifier.fillMaxSize(), contentPadding = androidx.compose.foundation.layout.PaddingValues(top = 8.dp, bottom = 24.dp)) {
            var lastGroup = ""
            for (c in items) {
                val g = dayGroup(c.updated)
                if (g != lastGroup) { lastGroup = g; item(key = "h$g") { T(g, p, 12, weight = FontWeight.Bold, color = p.faint, modifier = Modifier.padding(start = 6.dp, top = 18.dp, bottom = 6.dp)) } }
                item(key = c.id) {
                    val sel = c.id == m.convId
                    Row(Modifier.fillMaxWidth().animateItem().clip(RoundedCornerShape(14.dp)).background(if (sel) p.card2 else Color.Transparent)
                        .clickable { a.openConv(c.id); m.screen = 0 }.padding(start = 12.dp, top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f).padding(vertical = 8.dp)) {
                            T(c.title, p, 15, weight = if (sel) FontWeight.SemiBold else FontWeight.Medium, lines = 1)
                            T(timeLabel(c.updated) + "  ·  " + "${c.msgs.length() / 2} câu hỏi", p, 12, color = p.faint, lines = 1)
                        }
                        IconBtn(Icons.Rounded.Delete, "Xóa", p, Color.Transparent, p.faint, 42.dp) { a.deleteConv(c.id) }
                    }
                }
            }
        }
    }
}

private fun dayGroup(t: Long): String {
    val cal = java.util.Calendar.getInstance(); val now = cal.clone() as java.util.Calendar
    cal.timeInMillis = t
    val days = ((now.apply { set(java.util.Calendar.HOUR_OF_DAY, 0); set(java.util.Calendar.MINUTE, 0); set(java.util.Calendar.SECOND, 0); set(java.util.Calendar.MILLISECOND, 0) }.timeInMillis - t) / 86_400_000L).let { if (t >= now.timeInMillis) -1 else it }
    return when { days < 0 -> "Hôm nay"; days < 1 -> "Hôm qua"; days < 7 -> "7 ngày qua"; else -> "Trước đó" }
}

private fun timeLabel(t: Long): String {
    val d = java.util.Date(t)
    return if (dayGroup(t) == "Hôm nay") java.text.SimpleDateFormat("HH:mm", java.util.Locale.ROOT).format(d)
    else java.text.SimpleDateFormat("dd/MM, HH:mm", java.util.Locale.ROOT).format(d)
}

// ===================================================================== location and offline map
/** Compact position line for emergencies: what to read out to 115, with copy / text-message buttons. */
@Composable
private fun LocationStrip(p: Palette, a: Actions, modifier: Modifier = Modifier) {
    val f = LocationHub.fix
    val live = f != null && System.currentTimeMillis() - f.time < 60_000
    Column(modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(14.dp)).padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.LocationOn, null, tint = if (live) p.speak else p.warn, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            T(when { !LocationHub.permitted -> "Chưa cho phép định vị"; f == null -> "Đang tìm vị trí GPS…"; live -> "Vị trí của bạn"; else -> "Vị trí gần nhất (${LocationHub.ageText(f)})" },
                p, 13, weight = FontWeight.Bold, color = p.muted, modifier = Modifier.weight(1f))
            if (f != null) T("±${f.acc.toInt()} m", p, 12, Mono, color = p.faint)
        }
        if (f != null) T(LocationHub.coords(f), p, 18, Mono, FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!LocationHub.permitted) SmallBtn("Bật định vị", p, true) { a.locate() }
            else if (f != null) {
                SmallBtn("Chép tọa độ", p, false) { a.copyText(LocationHub.shareText(f)) }
                SmallBtn("Nhắn vị trí", p, false) { a.sms(LocationHub.shareText(f)) }
            }
            SmallBtn("Bản đồ", p, false) { a.openMap() }
        }
    }
}

@Composable
private fun SmallBtn(label: String, p: Palette, strong: Boolean, onClick: () -> Unit) {
    Box(Modifier.clip(RoundedCornerShape(50)).background(if (strong) p.accent else p.card2).clickable(onClick = onClick).padding(horizontal = 12.dp, vertical = 8.dp)) {
        T(label, p, 13, weight = FontWeight.SemiBold, color = if (strong) p.onAccent else p.ink, lines = 1)
    }
}

@Composable
private fun LocationScreen(m: UiModel, p: Palette, a: Actions) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    LaunchedEffect(Unit) { a.locate(); OfflineMap.refresh(ctx) }
    val f = LocationHub.fix
    val live = f != null && System.currentTimeMillis() - f.time < 60_000
    var follow by remember { mutableStateOf(1) }
    var km by remember { mutableStateOf(1) }
    var msg by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        // satellite status: the question "is there GPS here?" answered on the spot
        val (label, color) = when {
            !LocationHub.permitted -> "Chưa cho phép định vị" to p.sos
            !LocationHub.enabled -> "Định vị đang tắt trong cài đặt máy" to p.sos
            live && LocationHub.satsUsed > 0 -> "Có GPS: ${LocationHub.satsUsed} vệ tinh" to p.speak
            live -> "Vị trí gần đúng, chưa bắt được GPS" to p.warn
            else -> "Đang tìm vệ tinh… thấy ${LocationHub.satsSeen}, đang dùng ${LocationHub.satsUsed}" to p.warn
        }
        Row(Modifier.fillMaxWidth().padding(top = 4.dp).clip(RoundedCornerShape(16.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(16.dp)).padding(14.dp),
            verticalAlignment = Alignment.CenterVertically) {
            T(label, p, 16, weight = FontWeight.Bold, color = color, modifier = Modifier.weight(1f))
        }
        if (!LocationHub.permitted || !LocationHub.enabled) Row(Modifier.padding(top = 8.dp)) {
            SmallBtn(if (!LocationHub.permitted) "Cho phép định vị" else "Mở cài đặt định vị", p, true) { if (!LocationHub.permitted) a.locate() else a.locationSettings() }
        }
        if (f != null) Column(Modifier.padding(top = 12.dp)) {
            T(LocationHub.coords(f), p, 24, Mono, FontWeight.SemiBold)
            T("${LocationHub.dms(f.lat, "B", "N")}  ${LocationHub.dms(f.lon, "Đ", "T")}", p, 13, Mono, color = p.muted)
            T("Sai số ±${f.acc.toInt()} m" + (f.alt?.let { " · cao ${it.toInt()} m so với mực nước biển" + (f.altAcc?.let { a -> " (±${a.toInt()} m)" } ?: "") } ?: "") +
                " · ${LocationHub.ageText(f)}", p, 13, color = p.muted)
            Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SmallBtn("Chép tọa độ", p, false) { a.copyText(LocationHub.shareText(f)) }
                SmallBtn("Nhắn vị trí", p, false) { a.sms(LocationHub.shareText(f)) }
                SmallBtn("Gọi 115", p, true) { a.dial("115") }
            }
            T("Khi gọi 115 hoặc 112, đọc dãy số trên cho tổng đài viên.", p, 12, color = p.faint, modifier = Modifier.padding(top = 6.dp))
        }
        // map
        Box(Modifier.padding(top = 14.dp).fillMaxWidth().height(300.dp).clip(RoundedCornerShape(16.dp)).border(1.dp, p.line, RoundedCornerShape(16.dp))) {
            MapPanel(Modifier.fillMaxSize(), f?.lat, f?.lon, LocationHub.mark, follow)
            if (f != null) Box(Modifier.align(Alignment.BottomEnd).padding(10.dp).size(44.dp).clip(CircleShape).background(p.card).clickable { follow++ },
                contentAlignment = Alignment.Center) { Icon(Icons.Rounded.LocationOn, "Về vị trí của tôi", tint = p.accent, modifier = Modifier.size(22.dp)) }
        }
        T("Bản đồ © OpenStreetMap, © OpenMapTiles, OpenFreeMap", p, 10, color = p.faint, modifier = Modifier.padding(top = 4.dp))
        // saved point
        Section("Điểm đánh dấu", p, "Đánh dấu chỗ để xe, lều trại hay điểm hẹn trước khi đi; lúc quay lại máy chỉ khoảng cách và hướng, không cần mạng.") {
            val mk = LocationHub.mark
            if (mk != null && f != null) T(LocationHub.toMark(f, mk), p, 16, weight = FontWeight.Bold)
            else if (mk != null) T(String.format(java.util.Locale.ROOT, "%.5f, %.5f", mk.first, mk.second), p, 15, Mono)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (f != null) SmallBtn(if (mk == null) "Đánh dấu chỗ này" else "Đánh dấu lại chỗ này", p, true) { a.setMark(f.lat to f.lon) }
                if (mk != null) SmallBtn("Xóa điểm", p, false) { a.setMark(null) }
            }
        }
        // offline areas
        Section("Bản đồ ngoại tuyến", p, "Tải trước khi đi vào vùng không có sóng. Mỗi lần tải tối đa 3.000 mảnh hoặc 50 MB theo điều khoản của OpenFreeMap.") {
            val sizes = listOf(10, 25, 50)
            T("Khu vực quanh vị trí hiện tại", p, 13, weight = FontWeight.SemiBold, color = p.muted)
            Segmented(sizes.map { "$it km" }, km, p) { km = it }
            if (f != null) {
                val n = OfflineMap.estimate(OfflineMap.bounds(f.lat, f.lon, sizes[km]))
                T("Khoảng $n mảnh bản đồ cho vùng ${sizes[km]} × ${sizes[km]} km", p, 12, color = if (n > OfflineMap.MAX_TILES) p.sos else p.muted)
                Row { SmallBtn(if (OfflineMap.busy) "Đang tải…" else "Tải bản đồ vùng này", p, !OfflineMap.busy) {
                    if (!OfflineMap.busy) msg = OfflineMap.download(ctx, f.lat, f.lon, sizes[km], "Quanh ${LocationHub.coords(f)}")
                } }
            } else T("Cần vị trí GPS để chọn vùng tải.", p, 12, color = p.muted)
            (msg ?: OfflineMap.progress)?.let { T(it, p, 13, color = p.muted) }
            OfflineMap.areas.forEach { ar ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        T(ar.name, p, 14, weight = FontWeight.Medium, lines = 1)
                        T("${ar.km} km · ${ar.tiles} mảnh · ${"%.1f".format(ar.bytes / 1e6)} MB" + if (ar.done) "" else " · chưa xong", p, 12, color = p.muted)
                    }
                    IconBtn(Icons.Rounded.Delete, "Xóa vùng", p, Color.Transparent, p.faint, 40.dp) { OfflineMap.delete(ctx, ar.id) }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

// ===================================================================== safety guide
@Composable
private fun SafetyScreen(m: UiModel, p: Palette, a: Actions) {
    val all = m.cards?.cards ?: emptyList()
    val q = SafetyCards.stripAccents(SafetyCards.normVi(m.query))
    val g = groups[m.group].first
    val shown = all.filter { (g.isEmpty() || it.group == g) && (q.isEmpty() || SafetyCards.stripAccents(SafetyCards.normVi(it.title + " " + it.say)).contains(q)) }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Column(Modifier.padding(top = 4.dp)) {
                T("Sơ cứu và ứng phó thiên tai, lưu sẵn trên máy, mở được cả khi không có sóng.", p, 13, color = p.muted, modifier = Modifier.padding(bottom = 12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CallButton("115", "Cấp cứu y tế", p, true, Modifier.weight(1f), a)
                    CallButton("112", "Cứu nạn, cứu hộ", p, true, Modifier.weight(1f), a)
                }
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CallButton("114", "Cứu hỏa", p, false, Modifier.weight(1f), a)
                    CallButton("113", "Công an", p, false, Modifier.weight(1f), a)
                }
                LocationStrip(p, a, Modifier.padding(top = 10.dp))
                Row(Modifier.fillMaxWidth().padding(top = 14.dp).clip(RoundedCornerShape(14.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(14.dp))
                    .padding(horizontal = 12.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.Search, null, tint = p.faint, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Box(Modifier.weight(1f)) {
                        if (m.query.isEmpty()) T("Tìm: rắn cắn, bỏng, lũ quét…", p, 14, color = p.faint, lines = 1)
                        BasicTextField(m.query, { m.query = it }, singleLine = true, cursorBrush = SolidColor(p.accent),
                            textStyle = TextStyle(color = p.ink, fontFamily = Body, fontSize = 15.sp), modifier = Modifier.fillMaxWidth())
                    }
                    if (m.query.isNotEmpty()) Icon(Icons.Rounded.Close, "Xóa", tint = p.faint, modifier = Modifier.size(20.dp).clickable { m.query = "" })
                }
                Box(Modifier.padding(top = 10.dp, bottom = 4.dp)) { Segmented(groups.map { it.second }, m.group, p) { m.group = it } }
                T("${shown.size} hướng dẫn", p, 12, weight = FontWeight.Bold, color = p.faint, modifier = Modifier.padding(start = 4.dp, top = 4.dp))
            }
        }
        items(shown, key = { it.id }) { c ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(16.dp))
                .clickable { m.openCard = c.id }.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                GroupBadge(c.group, p)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    T(c.title, p, 15, weight = FontWeight.SemiBold, lines = 1)
                    T(SafetyCards.display(c.say), p, 12, color = p.muted, lines = 2)
                }
                Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = p.faint)
            }
        }
        item {
            T("Thông tin tham khảo, viết lại từ nguồn chính thống; không thay thế nhân viên y tế. Khi có nguy hiểm, hãy gọi 115 hoặc 112.",
                p, 12, color = p.faint, center = true, modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp))
        }
    }
}

@Composable
private fun GroupBadge(group: String, p: Palette, size: Dp = 38.dp) {
    val (bg, fg) = when (group) { "so_cuu" -> p.sosSoft to p.sos; "thien_tai" -> p.accentSoft to p.accent; else -> p.okSoft to p.speak }
    Box(Modifier.size(size).clip(RoundedCornerShape(12.dp)).background(bg), contentAlignment = Alignment.Center) {
        when (group) {
            "so_cuu" -> Canvas(Modifier.size(size * 0.46f)) {          // first-aid cross
                val w = this.size.width; val k = w * 0.34f
                drawRoundRect(fg, Offset((w - k) / 2, 0f), Size(k, w), androidx.compose.ui.geometry.CornerRadius(k * 0.25f))
                drawRoundRect(fg, Offset(0f, (w - k) / 2), Size(w, k), androidx.compose.ui.geometry.CornerRadius(k * 0.25f))
            }
            "thien_tai" -> Icon(Icons.Rounded.Warning, null, tint = fg, modifier = Modifier.size(size * 0.52f))
            else -> Icon(Icons.Rounded.Home, null, tint = fg, modifier = Modifier.size(size * 0.52f))
        }
    }
}

@Composable
private fun CardDetail(c: SafetyCards.Card, m: UiModel, p: Palette, a: Actions) {
    val steps = SafetyCards.display(c.say).split(Regex("(?<=\\.)\\s+")).map { it.trim().replaceFirstChar { ch -> ch.uppercase() } }.filter { it.length > 1 }
    Column(Modifier.fillMaxSize().background(p.bg).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconBtn(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại", p, Color.Transparent, p.ink) { m.openCard = null; a.stopRead() }
            T(groupName(c.group), p, 13, weight = FontWeight.Bold, color = p.muted, modifier = Modifier.weight(1f))
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                GroupBadge(c.group, p, 46.dp); Spacer(Modifier.width(12.dp))
                T(c.title, p, 24, Display, FontWeight.Bold, height = 1.2f, modifier = Modifier.weight(1f))
            }
            Row(Modifier.padding(top = 14.dp, bottom = 16.dp).height(56.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val reading = m.reading == c.id
                Row(Modifier.fillMaxSize().weight(1f).clip(RoundedCornerShape(14.dp)).background(if (reading) p.card2 else p.accent)
                    .clickable { if (reading) a.stopRead() else a.read(c.id, c.say) }.padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center) {
                    Icon(if (reading) Icons.Rounded.Close else Icons.Rounded.PlayArrow, null, tint = if (reading) p.ink else p.onAccent, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    T(if (reading) "Dừng đọc" else "Đọc to", p, 15, weight = FontWeight.Bold, color = if (reading) p.ink else p.onAccent)
                }
                if (c.call.isNotEmpty()) CallButton(c.call, callLabel(c.call), p, true, Modifier.fillMaxSize().weight(1f), a = a)
            }
            LocationStrip(p, a, Modifier.padding(bottom = 16.dp))
            steps.forEachIndexed { i, s ->
                Row(Modifier.fillMaxWidth().padding(bottom = 10.dp)) {
                    Box(Modifier.size(26.dp).clip(CircleShape).background(if (c.group == "so_cuu") p.sosSoft else p.accentSoft), contentAlignment = Alignment.Center) {
                        T("${i + 1}", p, 13, Mono, FontWeight.SemiBold, color = if (c.group == "so_cuu") p.sos else p.accent)
                    }
                    Spacer(Modifier.width(12.dp))
                    T(s, p, 16, modifier = Modifier.weight(1f).padding(top = 1.dp))
                }
            }
            T("NGUỒN", p, 11, weight = FontWeight.Bold, color = p.faint, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
            c.sources.forEach { id ->
                val (name, url) = m.cards?.sourceNames?.get(id) ?: (id to "")
                Column(Modifier.fillMaxWidth().padding(bottom = 8.dp).clip(RoundedCornerShape(12.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(12.dp))
                    .clickable(url.isNotEmpty()) { a.openUrl(url) }.padding(12.dp)) {
                    T(name, p, 13, weight = FontWeight.Medium)
                    if (url.isNotEmpty()) T(url.removePrefix("https://").removePrefix("www."), p, 11, Mono, color = p.accent, lines = 1)
                }
            }
            T("Nội dung viết lại bằng lời của nhóm từ các nguồn trên, chưa được nhân viên y tế duyệt. Đây là thông tin tham khảo khi chưa có trợ giúp; khi nguy hiểm, hãy gọi 115.",
                p, 12, color = p.faint, modifier = Modifier.padding(top = 6.dp, bottom = 24.dp))
        }
    }
}

// ===================================================================== settings
@Composable
private fun SettingsScreen(m: UiModel, p: Palette, a: Actions) {
    val locked = m.running
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        if (locked) Row(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 14.dp).clip(RoundedCornerShape(14.dp)).background(p.card).border(1.dp, p.line, RoundedCornerShape(14.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            T("Trợ lý đang chạy. Tắt để đổi mô hình, bộ xử lý, giọng.", p, 13, color = p.muted, modifier = Modifier.weight(1f))
            Box(Modifier.clip(RoundedCornerShape(50)).background(p.sosSoft).clickable { a.toggle() }.padding(horizontal = 12.dp, vertical = 7.dp)) {
                T("Tắt trợ lý", p, 13, weight = FontWeight.Bold, color = p.sos)
            }
        } else Spacer(Modifier.height(4.dp))
        if (m.mode == 1) {
            Section("Mô hình ngôn ngữ", p, "Mô hình 2 tỉ trả lời tốt hơn (điểm 4,17 so với 3,63) nhưng chậm hơn khoảng 0,3 s.") {
                if (m.models.isEmpty()) T("Chưa có file .gguf trong thư mục mô hình.", p, 14, color = p.warn)
                m.models.forEach { f ->
                    val on = f == m.model
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(if (on) p.accentSoft else p.card2).clickable(!locked) { m.model = f }
                        .padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(18.dp).clip(CircleShape).border(2.dp, if (on) p.accent else p.faint, CircleShape), contentAlignment = Alignment.Center) {
                            if (on) Box(Modifier.size(9.dp).clip(CircleShape).background(p.accent))
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            T(prettyModel(f), p, 14, weight = if (on) FontWeight.SemiBold else FontWeight.Medium, lines = 1)
                            T(f, p, 11, Mono, color = p.faint, lines = 1)
                        }
                        if ("2b" in f && "Q4_0" in f && "imx" in f) Box(Modifier.clip(RoundedCornerShape(50)).background(p.okSoft).padding(horizontal = 8.dp, vertical = 3.dp)) {
                            T("Đề xuất", p, 11, weight = FontWeight.Bold, color = p.speak)
                        }
                    }
                }
                T("Bộ xử lý", p, 13, weight = FontWeight.SemiBold, color = p.muted)
                if (m.cpuOnly) T("CPU (bản dành cho mọi điện thoại arm64; bản Snapdragon mới có NPU và GPU)", p, 14, color = p.muted)
                else Segmented(listOf("NPU Hexagon", "GPU Adreno", "CPU"), m.device, p, !locked) { m.device = it }
            }
            Section("Giọng và cách trả lời", p) {
                T("Giọng đọc", p, 13, weight = FontWeight.SemiBold, color = p.muted)
                Segmented(listOf("Giọng chuẩn", "Giọng nhanh"), m.voice2, p, !locked) { m.voice2 = it }
                T("Tốc độ đọc", p, 13, weight = FontWeight.SemiBold, color = p.muted)
                Segmented(listOf("Chậm", "Vừa", "Nhanh"), m.speed, p) { a.speed(it) }
                ToggleRow("Tra cứu Wikipedia", "Giảm thông tin sai (0,52 xuống 0,30), chậm thêm khoảng 0,06 s", m.rag, p, !locked) { m.rag = it }
                ToggleRow("Xác nhận tức thì \"Dạ.\"", "Nghe phản hồi sau khoảng 0,5 s trong lúc mô hình nghĩ", m.ack, p, !locked) { m.ack = it }
                ToggleRow("Tăng âm lượng", "Phát ra loa ngoài, thêm 9 dB cho dễ nghe; nút âm lượng của máy chỉnh được", m.loud, p) { a.loud(it) }
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f).padding(end = 10.dp)) {
                        T("Hướng dẫn an toàn", p, 15, weight = FontWeight.SemiBold)
                        T("Câu khẩn cấp được trả lời bằng hướng dẫn có nguồn, không để mô hình tự viết", p, 12, color = p.muted)
                    }
                    Box(Modifier.clip(RoundedCornerShape(50)).background(p.okSoft).padding(horizontal = 10.dp, vertical = 5.dp)) { T("Luôn bật", p, 12, weight = FontWeight.Bold, color = p.speak) }
                }
            }
            Section("Dữ liệu trên máy", p) {
                m.assets.forEach { (name, ok) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(8.dp).clip(CircleShape).background(if (ok) p.speak else p.sos))
                        Spacer(Modifier.width(10.dp))
                        T(name, p, 14, modifier = Modifier.weight(1f))
                        T(if (ok) "có" else "thiếu", p, 13, weight = FontWeight.SemiBold, color = if (ok) p.speak else p.sos)
                    }
                }
            }
        }
        Section("Lịch sử trò chuyện", p, "Chỉ lưu trong bộ nhớ của ứng dụng trên máy này, không gửi đi đâu.") {
            ToggleRow("Lưu lịch sử", "${m.history.size} cuộc trò chuyện đã lưu", m.saveHistory, p) { a.setSaveHistory(it) }
            var confirm by remember { mutableStateOf(false) }
            if (m.history.isNotEmpty()) Box(Modifier.clip(RoundedCornerShape(50)).background(if (confirm) p.sos else p.sosSoft)
                .clickable { if (confirm) { a.clearHistory(); confirm = false } else confirm = true }.padding(horizontal = 14.dp, vertical = 8.dp)) {
                T(if (confirm) "Chạm lần nữa để xóa hết" else "Xóa toàn bộ lịch sử", p, 13, weight = FontWeight.Bold, color = if (confirm) Color.White else p.sos)
            }
        }
        if (m.last.isNotEmpty()) Section("Lượt gần nhất", p, "Tính từ lúc bạn nói xong, gồm thời gian chờ ngắt câu.") {
            m.last.forEach { (k, v) ->
                Row { T(k, p, 14, color = p.muted, modifier = Modifier.weight(1f)); T(v, p, 14, Mono, FontWeight.SemiBold) }
            }
        }
        Section("Giới thiệu", p) {
            T("VieEdge Voice", p, 16, Display, FontWeight.Bold)
            T("Trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy hoàn toàn trên máy: giọng nói không rời điện thoại, dùng được khi mất mạng.", p, 13, color = p.muted)
            T("Hướng dẫn an toàn: ${m.cards?.cards?.size ?: 0} thẻ, phiên bản ${m.cards?.version ?: "–"}.", p, 13, color = p.muted)
            T("Huỳnh Lê Thành Nhân, Nguyễn Đoàn Hoàng Ngân · HCMUTE", p, 12, color = p.faint)
        }
        Spacer(Modifier.height(10.dp))
    }
}
