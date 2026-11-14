package vn.vieedge.voice

import android.content.Context
import org.json.JSONObject
import java.text.Normalizer
import java.util.Calendar

/**
 * Answers that do not need the LLM: the vetted safety cards first (see SafetyCards), then a small set of everyday
 * phrases (assets/faq_phone.jsonl: greetings, thanks, who are you...), the clock (time and date) and the Hoàng Sa /
 * Trường Sa fact. The Go2 robot-dog rules of the earlier project are not used on the phone.
 * Several wordings per answer: the same greeting is not repeated word for word every time.
 */
class FastPath(ctx: Context) {
    data class Hit(val say: String, val intent: String, val source: String)

    val safety: SafetyCards? = SafetyCards.load(ctx)
    private val faq = HashMap<String, Pair<List<String>, String>>()
    private val faqTok = ArrayList<Triple<Set<String>, List<String>, String>>()
    private val turn = HashMap<String, Int>()

    init {
        runCatching {
            ctx.assets.open("faq_phone.jsonl").bufferedReader().useLines { ls ->
                ls.filter { it.isNotBlank() }.forEach {
                    val j = JSONObject(it); val intent = j.getString("intent")
                    val says = j.getJSONArray("say").let { a -> (0 until a.length()).map { i -> a.getString(i) } }
                    val qs = j.getJSONArray("q")
                    for (i in 0 until qs.length()) { val q = norm(qs.getString(i)); faq[q] = says to intent; faqTok.add(Triple(q.split(" ").toSet(), says, intent)) }
                }
            }
        }
    }

    private fun pick(says: List<String>, intent: String): String { val i = turn.getOrDefault(intent, 0); turn[intent] = i + 1; return says[i % says.size] }

    fun lookup(text: String): Hit? {
        val t = norm(text.replace(Regex("[^\\p{L}\\p{N}\\s]"), " ")).replace(Regex("^(oi|a|da|vang|uh|um|u) "), "")
        if (t.isEmpty()) return null
        safety?.match(text)?.let { m -> return Hit(m.say, m.card?.id ?: "no-card", if (m.card != null) "safety" else "safety-fallback") }
        clock(t)?.let { return Hit(it, "dong_ho", "faq") }
        if (listOf("toi dang o dau", "minh dang o dau", "vi tri cua toi", "vi tri cua minh", "vi tri hien tai", "toa do", "dinh vi", "gps", "day la dau", "o dau day").any { " $it " in " $t " }) {
            val f = LocationHub.fix
            return Hit(if (f == null) "Mình chưa lấy được vị trí GPS. Hãy ra chỗ thoáng nhìn thấy bầu trời và chờ một lúc, GPS không cần sóng điện thoại."
                else LocationHub.spoken(f), "vi_tri", "faq")
        }
        if (("hoang sa" in t || "truong sa" in t) && listOf("cua ai", "cua nuoc nao", "nuoc nao", "thuoc", "cua viet nam", "chu quyen", "cua trung quoc", "la cua").any { it in t })
            return Hit("Quần đảo Hoàng Sa và quần đảo Trường Sa là lãnh thổ của Việt Nam. Hoàng Sa thuộc thành phố Đà Nẵng, Trường Sa thuộc tỉnh Khánh Hòa.", "chu_quyen", "faq")
        faq[t.removeSuffix(" nhe").removeSuffix(" nha").removeSuffix(" a").trim()]?.let { return Hit(pick(it.first, it.second), it.second, "faq") }
        val words = t.split(" ").toSet()
        if (words.size in 2..7) {
            var best: Triple<Set<String>, List<String>, String>? = null; var score = 0.0
            for (e in faqTok) {
                val j = words.intersect(e.first).size.toDouble() / words.union(e.first).size
                if (j > score) { score = j; best = e }
            }
            if (best != null && score >= 0.8) return Hit(pick(best.second, best.third), best.third, "faq-fuzzy")
        }
        return null
    }

    /** "Mấy giờ rồi", "hôm nay thứ mấy / ngày mấy": read from the phone's clock. */
    private fun clock(t: String): String? {
        val c = Calendar.getInstance()
        val askTime = listOf("may gio", "gio la may", "bay gio la", "gio may").any { it in t } && "may gio thi" !in t && "may gio sang" !in t && "mo cua" !in t
        val askDate = listOf("hom nay ngay", "hom nay la ngay", "hom nay thu", "hom nay la thu", "ngay bao nhieu", "hom nay mung").any { it in t }
        if (!askTime && !askDate) return null
        if (askTime && t.split(" ").size > 6) return null
        val h = c.get(Calendar.HOUR_OF_DAY); val m = c.get(Calendar.MINUTE)
        val part = when (h) { in 0..3 -> "đêm"; in 4..10 -> "sáng"; in 11..12 -> "trưa"; in 13..17 -> "chiều"; else -> "tối" }
        val h12 = if (h % 12 == 0) 12 else h % 12
        val time = "Bây giờ là $h12 giờ" + (if (m > 0) " $m phút" else "") + " $part."
        val dow = listOf("Chủ nhật", "thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy")[c.get(Calendar.DAY_OF_WEEK) - 1]
        val date = "Hôm nay là $dow, ngày ${c.get(Calendar.DAY_OF_MONTH)} tháng ${c.get(Calendar.MONTH) + 1} năm ${c.get(Calendar.YEAR)}."
        return if (askTime && askDate) "$time $date" else if (askTime) time else date
    }

    companion object {
        fun norm(s: String): String {
            val d = s.lowercase().replace("đ", "d")
            return Normalizer.normalize(d, Normalizer.Form.NFD).filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }
                .replace(Regex("\\s+"), " ").trim()
        }
    }
}
