package vn.vieedge.voice

import io.requery.android.database.sqlite.SQLiteDatabase
import java.io.File
import java.text.Normalizer

/**
 * Offline Vietnamese Wikipedia (SQLite FTS5, BM25) — Kotlin port of src/vieedge/rag/index.py. The system SQLite has no FTS5, so this uses the
 * requery build. The same database file as on the Pi (rag/wiki_vi.sqlite) is used; `remove_diacritics 2` leaves "đ" alone, so queries do too.
 */
class Rag(path: File) {
    private val db: SQLiteDatabase = SQLiteDatabase.openDatabase(path.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
    private val nRows: Long
    private val hasVocab: Boolean

    init {
        var n = 0L; var v = false
        runCatching {
            db.rawQuery("SELECT count(*) FROM chunks_docsize", null).use { it.moveToFirst(); n = it.getLong(0) }
            db.rawQuery("SELECT 1 FROM sqlite_master WHERE name='vocab'", null).use { v = it.moveToFirst() }
        }
        nRows = n; hasVocab = v
    }

    class Hit(val title: String, val text: String, val score: Double)

    fun close() = db.close()

    // ------------------------------------------------------------------ text helpers
    private val token = Regex("[0-9a-zà-ỹđ]+", RegexOption.IGNORE_CASE)
    private val stop = ("là của và có không được cho với trong một những các này đó khi thì mà bị đã sẽ đang cũng như để từ ra vào lên xuống nên rồi vậy nhỉ nhé ạ ơi " +
        "bạn mình tôi em anh chị hỏi gì sao nào ai đâu bao nhiêu mấy thế làm hay hoặc nhưng nếu vì tại do bởi theo về trên dưới giữa sau trước lại còn chỉ rất quá lắm " +
        "hơn nhất đều cả mọi mỗi nữa luôn thật biết nói cần muốn phải thể nghĩa giúp xin vui lòng giải thích cho_biết tại_sao vì_sao thế_nào như_thế_nào").split(" ").toSet()

    private fun stripMarks(s: String): String {
        val d = Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD).filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }
        return Normalizer.normalize(d, Normalizer.Form.NFC)
    }

    private fun syllables(text: String): List<String> = token.findAll(Normalizer.normalize(text.lowercase(), Normalizer.Form.NFC)).map { it.value }.toList()

    private fun queryTerms(q: String): Pair<List<String>, List<String>> {
        val raw = syllables(q); val keep = raw.map { stripMarks(it) }
        val isStop = raw.map { it in stop || it.length < 2 }
        val content = keep.filterIndexed { i, _ -> !isStop[i] }.distinct()
        val pairs = (0 until keep.size - 1).filter { !isStop[it] && !isStop[it + 1] }.map { "${keep[it]} ${keep[it + 1]}" }.distinct()
        return content to pairs
    }

    private fun docFreq(terms: List<String>): Map<String, Int> {
        if (!hasVocab || terms.isEmpty()) return emptyMap()
        val out = HashMap<String, Int>()
        db.rawQuery("SELECT term, doc FROM vocab WHERE term IN (${terms.joinToString(",") { "?" }})", terms.toTypedArray()).use { c -> while (c.moveToNext()) out[c.getString(0)] = c.getInt(1) }
        return out
    }

    private fun ftsQuery(question: String, df: Map<String, Int>, maxTerms: Int = 6, maxDfFrac: Double = 0.02): String? {
        var (content, pairs) = queryTerms(question)
        if (df.isNotEmpty() && nRows > 0) {
            val rare = content.filter { (df[it] ?: 0) in 1..(maxDfFrac * nRows).toInt() }
            content = (rare.ifEmpty { content }).sortedBy { df[it] ?: 0 }.take(maxTerms)
            pairs = pairs.filter { p -> p.split(" ").all { it in content || (df[it] ?: 0) <= maxDfFrac * nRows } }.take(maxTerms)
        }
        if (content.isEmpty()) return null
        return (pairs.map { "\"$it\"" } + content.map { "\"$it\"" }).joinToString(" OR ")
    }

    private val askYear = Regex("\\b(năm nào|khi nào|bao giờ|hồi nào|thời gian nào|ngày nào|thế kỷ nào)\\b", RegexOption.IGNORE_CASE)
    private val askNum = Regex("\\b(bao nhiêu|bao xa|bao lâu|bao nhiêu tuổi|cao|dài|rộng|nặng|sâu|diện tích|dân số|mấy)\\b", RegexOption.IGNORE_CASE)
    private val yearRe = Regex("\\b(1[0-9]{3}|20[0-9]{2}|[0-9]{1,2}\\s+tháng\\s+[0-9]{1,2})\\b")
    private val numRe = Regex("\\b[0-9][0-9.,]*\\s?(km|m|kg|nghìn|triệu|tỷ|%|mét|dặm|năm|tuổi|người)\\b", RegexOption.IGNORE_CASE)

    private fun answerBonus(q: String, text: String): Double {
        var b = 0.0
        if (askYear.containsMatchIn(q) && yearRe.containsMatchIn(text)) b += 40.0
        if (askNum.containsMatchIn(q) && numRe.containsMatchIn(text)) b += 40.0
        return b
    }

    // ------------------------------------------------------------------ retrieval
    private class Cand(val title: String, val lo: Long, val hi: Long, val score: Double)

    private fun titleCandidates(question: String, maxTitles: Int = 6): List<Cand> {
        val raw = syllables(question); val toks = raw.map { stripMarks(it) }
        val isStop = raw.map { it in stop || it.length < 2 }
        val found = HashMap<String, Cand>()
        for (n in intArrayOf(4, 3, 2, 1)) for (i in 0..(toks.size - n)) {
            val span = toks.subList(i, i + n)
            if (isStop[i] || isStop[i + n - 1]) continue
            val phrase = span.joinToString(" "); val rawSpan = raw.subList(i, i + n)
            db.rawQuery("SELECT a.title, a.lo, a.hi FROM tfts JOIN art a ON a.rowid = tfts.rowid WHERE tfts MATCH ? ORDER BY length(a.title) LIMIT 6", arrayOf("\"$phrase\"")).use { c ->
                while (c.moveToNext()) {
                    val title = c.getString(0); val lo = c.getLong(1); val hi = c.getLong(2)
                    val base = syllables(title.replace(Regex("\\s*\\(.*?\\)\\s*"), " "))
                    val tt = base.map { stripMarks(it) }
                    val exact = tt == span; val exactMarks = exact && base == rawSpan
                    if (n == 1 && !exactMarks) continue
                    val score = 50.0 * n + (if (exactMarks) 25.0 else if (exact) 5.0 else 0.0) - 1.0 * maxOf(tt.size - n, 0)
                    val prev = found[title]
                    if (prev == null || score > prev.score) found[title] = Cand(title, lo, hi, score)
                }
            }
        }
        return found.values.sortedByDescending { it.score }.take(maxTitles)
    }

    fun search(question: String, k: Int = 6, titleWeight: Double = 6.0): List<Hit> {
        val (content, pairs) = queryTerms(question); val terms = content.toSet()
        var out = ArrayList<Hit>()
        for (cd in titleCandidates(question)) {
            db.rawQuery("SELECT rowid, body FROM chunks WHERE rowid BETWEEN ? AND ?", arrayOf(cd.lo.toString(), cd.hi.toString())).use { c ->
                while (c.moveToNext()) {
                    val rid = c.getLong(0); val body = c.getString(1)
                    val words = syllables("$body ${cd.title}").map { stripMarks(it) }.toSet()
                    out.add(Hit(cd.title, body, cd.score + 25.0 * terms.intersect(words).size + (if (rid == cd.lo) 5.0 else 0.0) + answerBonus(question, body)))
                }
            }
        }
        out.sortByDescending { it.score }; out = ArrayList(out.take(k))
        if (out.count { it.score >= 100 } < 2) {
            val q = ftsQuery(question, docFreq(content + pairs.flatMap { it.split(" ") }))
            if (q != null) db.rawQuery("SELECT title, body, bm25(chunks, ?, 1.0) AS s FROM chunks WHERE chunks MATCH ? ORDER BY s LIMIT ?", arrayOf(titleWeight.toString(), q, k.toString())).use { c ->
                while (c.moveToNext()) out.add(Hit(c.getString(0), c.getString(1), -c.getDouble(2)))
            }
        }
        out.sortByDescending { it.score }
        return out.take(k)
    }

    private val caption = Regex("(?:nhỏ|thumb|trái|phải|giữa)\\|[^.]*?(?:\\.|$)", RegexOption.IGNORE_CASE)
    private val pageRef = Regex("tr\\.\\s?\\d+(?:[,–-]\\d+)*")
    private fun clean(t: String) = pageRef.replace(caption.replace(t, " "), "").replace(Regex("\\s{2,}"), " ").trim()

    /** Compact context block under a character budget (prefill is the price of RAG); null when nothing was found. */
    fun context(question: String, maxChars: Int = 240, maxDocs: Int = 1, minScore: Double = 0.0): String? {
        val hits = search(question).map { Hit(it.title, clean(it.text), it.score) }
        val out = ArrayList<String>(); var used = 0; val per = HashMap<String, Int>()
        for (h in hits) {
            if (h.score < minScore || (per[h.title] ?: 0) >= 2) continue
            per[h.title] = (per[h.title] ?: 0) + 1
            val room = maxChars - used
            if (room < 80) break
            var text = h.text
            if (text.length > room) { val cut = text.substring(0, room); text = cut.substring(0, maxOf(cut.lastIndexOf(". "), cut.lastIndexOf(", "), 60) + 1) }
            out.add("[${h.title}] $text"); used += text.length + h.title.length + 3
            if (out.size >= maxDocs) break
        }
        return if (out.isEmpty()) null else out.joinToString("\n")
    }
}
