package vn.vieedge.voice

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** A saved conversation. Kept only in the app's private storage on the phone; nothing is sent anywhere. */
class Conv(val id: Long, var title: String, var updated: Long, var msgs: JSONArray)

/** Chat history in filesDir/history.json, newest first, at most [MAX] conversations. */
class History(dir: File) {
    private val file = File(dir, "history.json")
    private val lock = Any()

    fun load(): List<Conv> = synchronized(lock) {
        runCatching {
            val a = JSONArray(file.readText())
            (0 until a.length()).map { a.getJSONObject(it) }.map { Conv(it.getLong("id"), it.getString("title"), it.getLong("updated"), it.getJSONArray("msgs")) }
        }.getOrDefault(emptyList())
    }

    fun save(list: List<Conv>) {
        val a = JSONArray()
        list.take(MAX).forEach { a.put(JSONObject().put("id", it.id).put("title", it.title).put("updated", it.updated).put("msgs", it.msgs)) }
        val text = a.toString()
        Thread {
            synchronized(lock) {
                val tmp = File(file.parentFile, "history.json.tmp")
                runCatching { tmp.writeText(text); tmp.renameTo(file) }
            }
        }.start()
    }

    fun clear() = synchronized(lock) { file.delete() }

    companion object {
        const val MAX = 200

        fun encode(msgs: List<Msg>): JSONArray = JSONArray().also { a ->
            msgs.filter { !(it.live && it.text == "…") && it.text.isNotBlank() }.forEach { m ->
                val o = JSONObject().put("r", m.role).put("t", m.text)
                m.card?.let { o.put("c", it) }
                if (m.fallback) o.put("f", true)
                if (m.chips.isNotEmpty()) o.put("k", JSONArray().also { k -> m.chips.forEach { (x, y) -> k.put(JSONArray().put(x).put(y)) } })
                a.put(o)
            }
        }

        fun decode(a: JSONArray): List<Msg> = (0 until a.length()).map { a.getJSONObject(it) }.map { o ->
            Msg(o.getString("r"), o.getString("t")).also { m ->
                m.card = o.optString("c").ifEmpty { null }
                m.fallback = o.optBoolean("f", false)
                o.optJSONArray("k")?.let { k -> for (i in 0 until k.length()) k.getJSONArray(i).let { m.chips.add(it.getString(0) to it.getString(1)) } }
            }
        }
    }
}
