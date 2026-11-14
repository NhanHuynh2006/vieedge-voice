package vn.vieedge.voice

/** Port of tts/segmenter.py: LLM tokens in, speakable chunks out. The first chunk is cut after `firstMaxWords` words (lower first-audio latency). */
class Segmenter(private val firstMin: Int = 8, private val minChars: Int = 12, private val maxChars: Int = 120, private val firstMaxWords: Int = 5) {
    private var buf = StringBuilder()
    private var emitted = 0
    private val abbr = Regex("(?:TP|Tp|GS|PGS|TS|ThS|BS|KS|Q|P|v\\.v|St|Mr|Mrs|Dr|vd|VD)\\.$")
    private val stop = Regex("[.!?…;:\\n]+(?=\\s|$)|\\n")

    private fun cut(): Int {
        val b = buf.toString()
        val limit = if (emitted == 0) firstMin else minChars
        for (m in stop.findAll(b)) {
            val end = m.range.last + 1
            if (end >= b.length && !b.endsWith("\n")) continue
            if (b.substring(0, end).trim().length < limit) continue
            if (m.value.startsWith(".") && abbr.containsMatchIn(b.substring(0, m.range.first + 1))) continue
            return end
        }
        if (emitted == 0 && firstMaxWords > 0 && b.endsWith(" ") && b.trim().split(Regex("\\s+")).size >= firstMaxWords) return b.length
        if (emitted == 0 || b.length > maxChars) {
            for (m in Regex(",(?=\\s)").findAll(b)) {
                val need = if (emitted == 0) firstMin else maxChars / 2
                if (b.substring(0, m.range.last + 1).trim().length >= need) return m.range.last + 1
            }
        }
        return -1
    }

    fun push(text: String): List<String> {
        buf.append(text)
        val out = ArrayList<String>()
        while (true) {
            val i = cut(); if (i < 0) break
            val b = buf.toString()
            val chunk = b.substring(0, i).trim(); buf = StringBuilder(b.substring(i))
            if (chunk.isNotEmpty()) { out.add(chunk); emitted++ }
        }
        return out
    }

    fun flush(): List<String> {
        val c = buf.toString().trim(); buf = StringBuilder()
        return if (c.isEmpty()) emptyList() else { emitted++; listOf(c) }
    }
}
