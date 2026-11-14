package vn.vieedge.voice

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/** Same answers as the Python matcher: reads the expected outputs written by bench/make_parity.py (results/an_toan/parity_python.jsonl). */
class SafetyCardsParityTest {
    @Test
    fun matchesPython() {
        val root = generateSequence(File("").absoluteFile) { it.parentFile }.first { File(it, "data/an_toan/the_an_toan.json").exists() }
        val clf = File(root, "data/an_toan/phan_loai.json").takeIf { it.exists() }?.readText()
        val sc = SafetyCards(File(root, "data/an_toan/the_an_toan.json").readText(), clf)
        var n = 0; val diff = ArrayList<String>()
        File(root, "results/an_toan/parity_python.jsonl").forEachLine { l ->
            val j = JSONObject(l); val m = sc.match(j.getString("q"))
            val got = if (m == null) "khong" else (m.card?.id ?: "du_phong")
            if (got != j.getString("got")) diff.add("${j.getString("q")} kotlin=$got python=${j.getString("got")}")
            n++
        }
        println("parity: $n questions, ${diff.size} differences"); diff.take(20).forEach { println(it) }
        assertEquals(0, diff.size)
    }
}
