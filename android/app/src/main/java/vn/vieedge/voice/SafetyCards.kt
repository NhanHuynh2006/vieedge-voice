package vn.vieedge.voice

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

/**
 * Vetted first-aid and disaster cards (assets/the_an_toan.json, same file as data/an_toan on the Pi).
 * Port of src/vieedge/safety/__init__.py: an emergency question gets the card's fixed, sourced answer instead of LLM text;
 * an emergency without a card gets the "call 115 / 112" fallback; everything else returns null.
 * The word lists come from the file ("quy_tac"), so both implementations apply the same rules.
 */
class SafetyCards(json: String, clfJson: String? = null) {
    class Card(val id: String, val title: String, val say: String, val priority: Int, val keys: List<String>, val keysAscii: List<String>,
               val context: List<String>, val combos: List<List<List<String>>>, val block: List<String>, val factual: Boolean,
               val group: String = "", val call: String = "", val sources: List<String> = emptyList())
    data class Match(val card: Card?, val say: String, val key: String, val via: String = "luat")

    /** Second stage (assets/phan_loai.json, bench/train_safety_clf.py): a linear classifier over word uni/bigrams with and
     *  without diacritics, used only when the rules name no card. Same features and arithmetic as Classifier in Python. */
    class Classifier(json: String) {
        val classes: List<String>
        private val bias: DoubleArray
        val tau: Double
        val margin: Double
        private val w = HashMap<String, List<Pair<Int, Double>>>()
        init {
            val d = JSONObject(json)
            classes = d.getJSONArray("lop").let { a -> (0 until a.length()).map { a.getString(it) } }
            bias = d.getJSONArray("lech").let { a -> DoubleArray(a.length()) { a.getDouble(it) } }
            tau = d.getDouble("nguong"); margin = d.getDouble("cach_biet")
            val f = d.getJSONObject("dac_trung")
            for (k in f.keys()) { val a = f.getJSONArray(k); w[k] = (0 until a.length()).map { a.getJSONArray(it).let { p -> p.getInt(0) to p.getDouble(1) } } }
        }
        fun predict(text: String): Triple<String, Double, Double> {
            val z = bias.copyOf()
            for (f in features(text)) w[f]?.forEach { (c, v) -> z[c] += v }
            val mx = z.max()
            val e = z.map { Math.exp(it - mx) }
            val s = e.sum()
            val o = e.indices.sortedByDescending { e[it] }
            return Triple(classes[o[0]], e[o[0]] / s, (e[o[0]] - e[o[1]]) / s)
        }
    }
    val clf: Classifier? = clfJson?.let { runCatching { Classifier(it) }.getOrNull() }

    val version: String
    val fallback: String
    val cards: List<Card>
    private val ask: List<String>
    private val knowledge: List<String>
    private val emergency: List<String>
    private val notEmergency: List<String>
    private val year: Regex
    private val infant: List<String>
    private val infantMonth: Regex
    private val child: List<String>
    private val redirects: List<Triple<String, String, String>>   // adult card -> infant / child card, in file order

    init {
        val d = JSONObject(json)
        version = d.optString("phien_ban")
        fallback = d.getJSONObject("du_phong").getString("noi")
        val r = d.getJSONObject("quy_tac")
        ask = list(r.getJSONArray("hoi_cach_lam")); knowledge = list(r.getJSONArray("kien_thuc"))
        emergency = list(r.getJSONArray("khan_cap")); notEmergency = list(r.getJSONArray("khong_khan_cap"))
        year = Regex("(^| )" + r.getString("nam_kien_thuc") + "( |$)")
        infant = list(r.getJSONArray("tre_nho"))
        infantMonth = Regex("(^| )([0-9]+|" + list(r.getJSONArray("tre_nho_thang")).joinToString("|") + ") tháng( |$)")
        child = r.optJSONArray("tre_em")?.let { list(it) } ?: emptyList()
        redirects = d.optJSONArray("chuyen_the")?.let { a -> (0 until a.length()).map { a.getJSONObject(it) }.map { Triple(it.getString("tu_the"), it.getString("sang"), it.getString("khi")) } }
            ?: d.optJSONObject("tre_so_sinh")?.let { listOf(Triple(it.getString("tu_the"), it.getString("sang"), "so_sinh")) } ?: emptyList()
        val out = ArrayList<Card>()
        val arr = d.getJSONArray("the")
        for (i in 0 until arr.length()) {
            val c = arr.getJSONObject(i)
            val keys = list(c.getJSONArray("khoa")).toSet().sortedByDescending { it.length }
            val combos = ArrayList<List<List<String>>>()
            c.optJSONArray("to_hop")?.let { th -> for (j in 0 until th.length()) { val g = th.getJSONArray(j); combos.add((0 until g.length()).map { list(g.getJSONArray(it)) }) } }
            out.add(Card(c.getString("id"), c.getString("ten"), c.getString("noi"), c.optInt("uu_tien", 1), keys,
                keys.filter { it.split(" ").size >= 3 }.map { stripAccents(it) },
                c.optJSONArray("can_ngu_canh")?.let { list(it) } ?: emptyList(), combos,
                c.optJSONArray("tru")?.let { list(it) } ?: emptyList(), c.optBoolean("bo_qua_kien_thuc", false),
                c.optString("nhom"), c.optString("goi"), c.optJSONArray("nguon")?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()))
        }
        cards = out
    }

    fun match(text: String): Match? {
        val t = normVi(text)
        if (t.isEmpty()) return null
        val ta = stripAccents(t)
        var best: Card? = null; var bestP = -1; var bestL = -1; var bestKey = ""
        for (c in cards) {
            if (c.context.isNotEmpty() && c.context.none { has(t, it) }) continue
            if (c.block.any { has(t, it) }) continue
            var key = c.keys.firstOrNull { has(t, it) } ?: c.keysAscii.firstOrNull { has(ta, it) }
            if (key == null) {
                for (combo in c.combos) {
                    val words = combo.map { g -> g.firstOrNull { has(t, it) } }
                    if (words.all { it != null }) { key = words.joinToString("+"); break }
                }
            }
            if (key != null && (c.priority > bestP || (c.priority == bestP && key.length > bestL))) {
                best = c; bestP = c.priority; bestL = key.length; bestKey = key
            }
        }
        val isAsk = ask.any { has(t, it) }
        val isKnowledge = knowledge.any { has(t, it) } || year.containsMatchIn(t)
        if (best != null) {
            if (isKnowledge && !isAsk && !best.factual) return null
            best = redirect(best!!, t)
            return Match(best, best!!.say, bestKey)
        }
        if (clf != null && (isAsk || !isKnowledge)) {
            val (c, p, gap) = clf.predict(text)
            val card = if (c != "khong" && p >= clf.tau && gap >= clf.margin) byId(c) else null
            if (card != null) { val r = redirect(card, t); return Match(r, r.say, "~$c:${"%.2f".format(java.util.Locale.ROOT, p)}", "phan_loai") }
        }
        var te = t
        for (x in notEmergency) te = te.replace(x, " ")
        if ((isAsk || !isKnowledge) && emergency.any { has(te, it) }) return Match(null, fallback, "")
        return null
    }

    /** Adult card -> infant / child version when the normalised question names a baby or a child. */
    fun redirect(card: Card, t: String): Card {
        var c = card
        for ((src, dst, whenWord) in redirects) {
            val hit = if (whenWord == "so_sinh") infant.any { has(t, it) } || infantMonth.containsMatchIn(t) else child.any { has(t, it) }
            if (c.id == src && hit) byId(dst)?.let { c = it }
        }
        return c
    }

    fun phrases(): List<String> = cards.map { it.say } + fallback

    fun byId(id: String?): Card? = cards.firstOrNull { it.id == id }

    /** Source names and links (assets/nguon.json), id -> (name, url). */
    var sourceNames: Map<String, Pair<String, String>> = emptyMap()

    companion object {
        fun load(ctx: Context): SafetyCards? = runCatching {
            SafetyCards(ctx.assets.open("the_an_toan.json").bufferedReader().readText(),
                runCatching { ctx.assets.open("phan_loai.json").bufferedReader().readText() }.getOrNull()).also { sc ->
                runCatching {
                    val j = JSONObject(ctx.assets.open("nguon.json").bufferedReader().readText())
                    sc.sourceNames = j.keys().asSequence().associateWith { k -> j.getJSONObject(k).let { it.getString("ten") to it.optString("url") } }
                }
            }
        }.getOrNull()

        /** Text for the screen: spoken phone numbers back to digits. */
        fun display(s: String): String {
            var r = s
            for ((spoken, digits) in listOf("một một một" to "111", "một một lăm" to "115", "một một hai" to "112", "một một bốn" to "114", "một một ba" to "113",
                "chín một một" to "911", "chín chín chín" to "999", "không không không" to "000"))
                r = r.replace(spoken, digits).replace(spoken.replaceFirstChar { it.uppercase() }, digits)
            return r
        }

        /** Classifier features: word unigrams/bigrams with and without diacritics, sorted and de-duplicated. */
        fun features(text: String): List<String> {
            val w = normVi(text).split(" ").filter { it.isNotEmpty() }
            val a = w.map { stripAccents(it) }
            val f = HashSet<String>()
            w.forEach { f.add("w:$it") }; a.forEach { f.add("a:$it") }
            for (i in 0 until w.size - 1) { f.add("b:${w[i]}_${w[i + 1]}"); f.add("c:${a[i]}_${a[i + 1]}") }
            return f.sorted()
        }

        private fun list(a: JSONArray): List<String> = (0 until a.length()).map { normVi(a.getString(it)) }

        /** Lower case, NFC, punctuation removed, diacritics kept (same as norm_vi in Python). */
        fun normVi(s: String): String = Normalizer.normalize(s.lowercase(), Normalizer.Form.NFC)
            .replace(Regex("[^\\p{L}\\p{N}_\\s]"), " ").replace(Regex("\\s+"), " ").trim()

        fun stripAccents(s: String): String = Normalizer.normalize(
            Normalizer.normalize(s.replace("đ", "d"), Normalizer.Form.NFD).filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() },
            Normalizer.Form.NFC)

        private fun has(t: String, phrase: String) = " $t ".contains(" $phrase ")
    }
}
