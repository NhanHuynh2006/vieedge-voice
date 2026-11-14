package vn.vieedge.voice

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.GnssStatus
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale
import kotlin.math.abs

/**
 * Phone position from the satellite receiver (GPS, Galileo, BeiDou, GLONASS). Works without mobile data or Wi-Fi:
 * only a view of the sky is needed. The last good fix is kept (also on disk), so in a cave, a valley or indoors the app
 * still shows where the person last was and how long ago.
 */
object LocationHub {
    /** acc: radius in metres of the 68 % confidence circle (Android Location.getAccuracy).
     *  alt: height above mean sea level when the phone provides it (Android 14+), else null; the raw GPS height is above the
     *  WGS84 ellipsoid, which differs from sea level by tens of metres, so it is not shown as "độ cao". */
    class Fix(val lat: Double, val lon: Double, val acc: Float, val alt: Double?, val time: Long, val provider: String, val altAcc: Float? = null)

    var fix by mutableStateOf<Fix?>(null)              // last known position (may be old)
    var satsUsed by mutableStateOf(0)                    // satellites used in the current fix
    var satsSeen by mutableStateOf(0)                    // satellites the receiver can see
    var searching by mutableStateOf(false)               // receiver on, no fix yet in this session
    var enabled by mutableStateOf(true)                  // location switched on in the phone settings
    var permitted by mutableStateOf(false)
    var mark by mutableStateOf<Pair<Double, Double>?>(null)   // a saved point ("my car", "the camp"): distance and direction back

    private var lm: LocationManager? = null
    private var running = false
    private var app: Context? = null

    fun has(ctx: Context) = ctx.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    fun init(ctx: Context) {
        app = ctx.applicationContext
        val p = ctx.getSharedPreferences("location", Context.MODE_PRIVATE)
        if (p.contains("latb")) fix = Fix(java.lang.Double.longBitsToDouble(p.getLong("latb", 0)),
            java.lang.Double.longBitsToDouble(p.getLong("lonb", 0)), p.getFloat("acc", 0f), null, p.getLong("time", 0), "đã lưu")
        if (p.contains("mlat")) mark = java.lang.Double.longBitsToDouble(p.getLong("mlat", 0)) to java.lang.Double.longBitsToDouble(p.getLong("mlon", 0))
        permitted = has(ctx)
    }

    private val listener = LocationListener { l -> onLocation(l) }
    private val netListener = LocationListener { l -> if (fix?.provider != "gps" || System.currentTimeMillis() - (fix?.time ?: 0) > 30_000) onLocation(l) }

    private fun onLocation(l: Location) {
        val gps = l.provider == LocationManager.GPS_PROVIDER
        val msl = if (gps && android.os.Build.VERSION.SDK_INT >= 34 && l.hasMslAltitude()) l.mslAltitudeMeters else null
        val mslAcc = if (msl != null && android.os.Build.VERSION.SDK_INT >= 34 && l.hasMslAltitudeAccuracy()) l.mslAltitudeAccuracyMeters else null
        fix = Fix(l.latitude, l.longitude, l.accuracy, msl, System.currentTimeMillis(), l.provider ?: "gps", mslAcc)
        searching = false
        app?.getSharedPreferences("location", Context.MODE_PRIVATE)?.edit()
            ?.putLong("latb", java.lang.Double.doubleToRawLongBits(l.latitude))?.putLong("lonb", java.lang.Double.doubleToRawLongBits(l.longitude))
            ?.putFloat("acc", l.accuracy)?.putLong("time", System.currentTimeMillis())?.apply()
    }

    private val gnss = object : GnssStatus.Callback() {
        override fun onSatelliteStatusChanged(status: GnssStatus) {
            satsSeen = status.satelliteCount
            satsUsed = (0 until status.satelliteCount).count { status.usedInFix(it) }
        }
        override fun onStopped() { satsUsed = 0 }
    }

    /** Starts the receiver (1 s updates). Safe to call repeatedly. */
    @SuppressLint("MissingPermission")
    fun start(ctx: Context) {
        permitted = has(ctx)
        val m = lm ?: (ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager).also { lm = it }
        enabled = runCatching { m.isProviderEnabled(LocationManager.GPS_PROVIDER) }.getOrDefault(false)
        if (!permitted || running) return
        runCatching {
            val h = Handler(Looper.getMainLooper())
            m.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, listener, Looper.getMainLooper())
            // the network provider gives a rough position fast where there is mobile signal; GPS replaces it when it locks
            if (m.allProviders.contains(LocationManager.NETWORK_PROVIDER))
                runCatching { m.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 5000L, 0f, netListener, Looper.getMainLooper()) }
            m.registerGnssStatusCallback(gnss, h)
            m.getLastKnownLocation(LocationManager.GPS_PROVIDER)?.let { if (fix == null || it.time > fix!!.time) onLocation(it) }
            running = true; searching = true
        }
    }

    fun stop() {
        runCatching { lm?.removeUpdates(listener); lm?.removeUpdates(netListener); lm?.unregisterGnssStatusCallback(gnss) }
        running = false; searching = false
    }

    fun setMark(ctx: Context, p: Pair<Double, Double>?) {
        mark = p
        val e = ctx.getSharedPreferences("location", Context.MODE_PRIVATE).edit()
        if (p == null) e.remove("mlat").remove("mlon") else e.putLong("mlat", java.lang.Double.doubleToRawLongBits(p.first)).putLong("mlon", java.lang.Double.doubleToRawLongBits(p.second))
        e.apply()
    }

    // ------------------------------------------------------------------ text
    fun ageText(f: Fix): String {
        val s = (System.currentTimeMillis() - f.time) / 1000
        return when { s < 15 -> "vừa xong"; s < 90 -> "$s giây trước"; s < 3600 -> "${s / 60} phút trước"; s < 86400 -> "${s / 3600} giờ trước"; else -> "${s / 86400} ngày trước" }
    }

    /** "10.77250, 106.69800": what to read out or paste into a map app. */
    fun coords(f: Fix) = String.format(Locale.ROOT, "%.5f, %.5f", f.lat, f.lon)

    fun dms(v: Double, pos: String, neg: String): String {
        val a = abs(v); val d = a.toInt(); val mm = (a - d) * 60; val m = mm.toInt(); val s = (mm - m) * 60
        return String.format(Locale.ROOT, "%d°%02d'%04.1f\"%s", d, m, s, if (v >= 0) pos else neg)
    }

    fun shareText(f: Fix): String =
        "Tôi cần giúp đỡ. Vị trí của tôi: ${coords(f)} (sai số khoảng ${f.acc.toInt()} m, ${ageText(f)}). Bản đồ: https://www.openstreetmap.org/?mlat=${"%.5f".format(Locale.ROOT, f.lat)}&mlon=${"%.5f".format(Locale.ROOT, f.lon)}#map=17/${"%.5f".format(Locale.ROOT, f.lat)}/${"%.5f".format(Locale.ROOT, f.lon)}"

    /** Spoken form: digits after the decimal point read one by one ("mười phẩy tám năm không một"). */
    fun spoken(f: Fix): String {
        fun num(v: Double): String { val s = String.format(Locale.ROOT, "%.4f", abs(v)); val (i, d) = s.split('.'); return "$i phẩy ${d.toCharArray().joinToString(" ")}" }
        val ns = if (f.lat >= 0) "Bắc" else "Nam"; val ew = if (f.lon >= 0) "Đông" else "Tây"
        // short sentences: the voice starts on the first one while the next ones are synthesised (slow phones)
        return "Vĩ độ ${num(f.lat)} độ $ns. Kinh độ ${num(f.lon)} độ $ew. Sai số khoảng ${f.acc.toInt()} mét, cập nhật ${ageText(f)}."
    }

    /** Distance and compass direction from the current fix to the saved point. */
    fun toMark(f: Fix, m: Pair<Double, Double>): String {
        val r = FloatArray(2); Location.distanceBetween(f.lat, f.lon, m.first, m.second, r)
        val d = r[0]; val b = ((r[1] + 360) % 360)
        val dir = listOf("Bắc", "Đông Bắc", "Đông", "Đông Nam", "Nam", "Tây Nam", "Tây", "Tây Bắc")[(((b + 22.5) % 360) / 45).toInt()]
        val dist = if (d < 1000) "${d.toInt()} m" else String.format(Locale("vi"), "%.1f km", d / 1000)
        return "Cách $dist, về hướng $dir"
    }
}
