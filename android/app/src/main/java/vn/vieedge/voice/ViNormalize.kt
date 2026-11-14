package vn.vieedge.voice

/** Compact port of src/vieedge/tts/vi_normalize.py: numbers, decimals, percents, a few units/abbreviations, markdown removal. */
object ViNormalize {
    private val DIGITS = listOf("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
    private val SCALES = listOf("", "nghìn", "triệu", "tỷ")

    private fun readTwo(n: Int, full: Boolean): String {
        val tens = n / 10; val unit = n % 10
        if (tens == 0) return if (unit == 0) "" else (if (full) "linh " else "") + DIGITS[unit]
        if (tens == 1) return when (unit) { 0 -> "mười"; 5 -> "mười lăm"; else -> "mười " + DIGITS[unit] }
        val head = DIGITS[tens] + " mươi"
        return when (unit) { 0 -> head; 1 -> "$head mốt"; 4 -> "$head tư"; 5 -> "$head lăm"; else -> head + " " + DIGITS[unit] }
    }

    private fun readThree(n: Int, full: Boolean): String {
        val h = n / 100; val rest = n % 100
        if (h == 0 && !full) return readTwo(rest, false)
        var out = DIGITS[h] + " trăm"
        if (rest != 0) out += " " + readTwo(rest, true)
        return out
    }

    fun numberToWords(n0: Long): String {
        if (n0 < 0) return "âm " + numberToWords(-n0)
        if (n0 < 10) return DIGITS[n0.toInt()]
        if (n0 < 100) return readTwo(n0.toInt(), false)
        val groups = ArrayList<Int>(); var n = n0
        while (n > 0) { groups.add((n % 1000).toInt()); n /= 1000 }
        if (groups.size > SCALES.size) return n0.toString().map { DIGITS[it - '0'] }.joinToString(" ")
        val parts = ArrayList<String>()
        for (i in groups.size - 1 downTo 0) {
            val g = groups[i]; if (g == 0) continue
            parts.add((readThree(g, full = i != groups.size - 1) + " " + SCALES[i]).trim())
        }
        return parts.joinToString(" ").ifBlank { "không" }
    }

    private fun digitsToWords(s: String) = s.filter { it.isDigit() }.map { DIGITS[it - '0'] }.joinToString(" ")

    private val UNITS = linkedMapOf(
        "km/h" to "ki lô mét trên giờ", "km" to "ki lô mét", "cm" to "xen ti mét", "mm" to "mi li mét", "kg" to "ki lô gam",
        "°C" to "độ xê", "°" to "độ", "GB" to "gi ga bai", "MB" to "mê ga bai", "GHz" to "gi ga héc", "kW" to "ki lô oát",
        "m" to "mét", "g" to "gam", "l" to "lít", "h" to "giờ", "s" to "giây",
    )
    private val ABBREV = linkedMapOf(
        "TP.HCM" to "thành phố Hồ Chí Minh", "TP. HCM" to "thành phố Hồ Chí Minh", "TP." to "thành phố", "HCM" to "Hồ Chí Minh",
        "VN" to "Việt Nam", "UBND" to "ủy ban nhân dân", "THPT" to "trung học phổ thông", "v.v." to "vân vân", "AI" to "ây ai",
        "CPU" to "xê pê u", "GPU" to "gờ pê u", "NPU" to "nờ pê u", "USB" to "u ét bê", "Wi-Fi" to "oai phai", "OK" to "ô kê",
    )
    private val SYMBOLS = mapOf("&" to " và ", "+" to " cộng ", "=" to " bằng ", "~" to " khoảng ", "×" to " nhân ", "÷" to " chia ", "–" to ", ", "—" to ", ")

    fun stripMarkdown(t0: String): String {
        var t = t0
        t = t.replace(Regex("```.*?```", RegexOption.DOT_MATCHES_ALL), " ")
        t = t.replace(Regex("`([^`]*)`"), "$1")
        t = t.replace(Regex("\\[([^\\]]+)\\]\\([^)]*\\)"), "$1")
        t = t.replace(Regex("https?://\\S+"), " ")
        t = t.replace(Regex("(?m)^\\s{0,3}#{1,6}\\s*"), "")
        t = t.replace(Regex("(?m)^\\s*(?:[-*+•]|\\d+[.)])\\s+"), "")
        t = t.replace(Regex("(\\*\\*|__|\\*|_|~~)(.+?)\\1"), "$2")
        return t.replace("*", " ").replace("#", " ")
    }

    fun normalize(text: String): String {
        var t = stripMarkdown(text)
        for ((k, v) in ABBREV) t = t.replace(k, v)
        // percentages and numbers with units
        t = Regex("(\\d+(?:[.,]\\d+)?)\\s?%").replace(t) { number(it.groupValues[1]) + " phần trăm" }
        val unitRe = Regex("(\\d+(?:[.,]\\d+)?)\\s?(" + UNITS.keys.sortedByDescending { it.length }.joinToString("|") { Regex.escape(it) } + ")(?![\\p{L}])")
        t = unitRe.replace(t) { number(it.groupValues[1]) + " " + UNITS[it.groupValues[2]] }
        t = Regex("\\d{1,3}(?:\\.\\d{3})+|\\d+(?:,\\d+)?").replace(t) { number(it.value) }
        for ((k, v) in SYMBOLS) t = t.replace(k, v)
        return t.replace(Regex("\\s+"), " ").trim()
    }

    private fun number(s: String): String {
        if (',' in s) {                                    // Vietnamese decimal comma
            val (i, f) = s.split(',', limit = 2)
            val fr = f.trimEnd('0').ifEmpty { "0" }
            val right = if (fr.length <= 2 && !fr.startsWith("0")) numberToWords(fr.toLong()) else digitsToWords(fr)
            return numberToWords(i.replace(".", "").toLong()) + " phẩy " + right
        }
        if ('.' in s && !Regex("\\d{1,3}(\\.\\d{3})+").matches(s)) {
            val (i, f) = s.split('.', limit = 2)
            val fr = f.trimEnd('0').ifEmpty { "0" }
            val right = if (fr.length <= 2 && !fr.startsWith("0")) numberToWords(fr.toLong()) else digitsToWords(fr)
            return numberToWords(i.toLong()) + " phẩy " + right
        }
        val d = s.replace(".", "")
        return if (d.length > 12) digitsToWords(d) else numberToWords(d.toLong())
    }
}
