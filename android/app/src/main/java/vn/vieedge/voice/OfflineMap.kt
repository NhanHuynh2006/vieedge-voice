package vn.vieedge.voice

import android.content.Context
import android.os.Bundle
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import okhttp3.Dispatcher
import okhttp3.OkHttpClient
import org.json.JSONObject
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.module.http.HttpRequestUtil
import org.maplibre.android.offline.OfflineManager
import org.maplibre.android.offline.OfflineRegion
import org.maplibre.android.offline.OfflineRegionError
import org.maplibre.android.offline.OfflineRegionStatus
import org.maplibre.android.offline.OfflineTilePyramidRegionDefinition
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.tan

/**
 * Offline map: OpenStreetMap data as vector tiles from OpenFreeMap (free, no key), drawn by MapLibre Native.
 * OpenFreeMap allows offline downloads of at most 3,000 tiles or 50 MB each, with at most 4 parallel requests and a
 * User-Agent naming the app (openfreemap.org/tos); the OpenStreetMap tile server itself forbids offline downloads, so it is
 * not used. Download an area while there is internet (before a trip into the mountains); the map, your GPS position and the
 * saved point keep working there without any signal. Map data © OpenStreetMap contributors, © OpenMapTiles.
 */
object OfflineMap {
    const val STYLE = "https://tiles.openfreemap.org/styles/liberty"
    const val MAX_TILES = 3000L
    const val MAX_BYTES = 50L * 1024 * 1024
    private var ready = false

    class Area(val id: Long, val name: String, val km: Int, val tiles: Long, val bytes: Long, val done: Boolean)

    val areas = mutableStateListOf<Area>()
    var progress by mutableStateOf<String?>(null)        // text of the running download, null when idle
    var busy by mutableStateOf(false)

    fun init(ctx: Context) {
        if (ready) return
        MapLibre.getInstance(ctx.applicationContext)
        HttpRequestUtil.setOkHttpClient(OkHttpClient.Builder()
            .dispatcher(Dispatcher().apply { maxRequestsPerHost = 4; maxRequests = 4 })
            .addInterceptor { c -> c.proceed(c.request().newBuilder().header("User-Agent", "VieEdgeVoice/1.0 (HCMUTE student project, offline safety assistant)").build()) }
            .build())
        OfflineManager.getInstance(ctx).setOfflineMapboxTileCountLimit(MAX_TILES)
        ready = true
    }

    /** Square area of `km` x `km` around a point. */
    fun bounds(lat: Double, lon: Double, km: Int): LatLngBounds {
        val dLat = km / 2.0 / 111.32; val dLon = km / 2.0 / (111.32 * cos(lat * PI / 180))
        return LatLngBounds.from(lat + dLat, lon + dLon, lat - dLat, lon - dLon)
    }

    private fun tileX(lon: Double, z: Int) = floor((lon + 180) / 360 * (1 shl z)).toLong()
    private fun tileY(lat: Double, z: Int): Long { val r = lat * PI / 180; return floor((1 - ln(tan(r) + 1 / cos(r)) / PI) / 2 * (1 shl z)).toLong() }

    /** Number of vector tiles of the area for zoom 0..14 (OpenMapTiles stops at 14; closer zooms reuse them). */
    fun estimate(b: LatLngBounds, maxZoom: Int = 14): Long = (0..maxZoom).sumOf { z ->
        (tileX(b.longitudeEast, z) - tileX(b.longitudeWest, z) + 1) * (tileY(b.latitudeSouth, z) - tileY(b.latitudeNorth, z) + 1)
    }

    fun refresh(ctx: Context) {
        init(ctx)
        OfflineManager.getInstance(ctx).listOfflineRegions(object : OfflineManager.ListOfflineRegionsCallback {
            override fun onList(offlineRegions: Array<OfflineRegion>?) {
                val list = offlineRegions ?: emptyArray()
                areas.clear()
                for (r in list) {
                    val meta = runCatching { JSONObject(String(r.metadata)) }.getOrNull()
                    r.getStatus(object : OfflineRegion.OfflineRegionStatusCallback {
                        override fun onStatus(status: OfflineRegionStatus?) {
                            areas.add(Area(r.id, meta?.optString("name") ?: "Khu vực ${r.id}", meta?.optInt("km") ?: 0,
                                status?.completedTileCount ?: 0, status?.completedResourceSize ?: 0, status?.isComplete == true))
                        }
                        override fun onError(error: String?) {}
                    })
                }
            }
            override fun onError(error: String) {}
        })
    }

    /** Downloads the area around (lat, lon). Refuses areas over the OpenFreeMap limit before asking the server. */
    fun download(ctx: Context, lat: Double, lon: Double, km: Int, name: String): String? {
        init(ctx)
        val b = bounds(lat, lon, km)
        val n = estimate(b)
        if (n > MAX_TILES) return "Khu vực ${km} km cần khoảng $n mảnh bản đồ, quá giới hạn $MAX_TILES mảnh cho mỗi lần tải. Hãy chọn khu vực nhỏ hơn."
        val def = OfflineTilePyramidRegionDefinition(STYLE, b, 0.0, 14.0, ctx.resources.displayMetrics.density)
        val meta = JSONObject().put("name", name).put("km", km).put("lat", lat).put("lon", lon).put("time", System.currentTimeMillis()).toString().toByteArray()
        busy = true; progress = "Đang chuẩn bị tải khoảng $n mảnh…"
        OfflineManager.getInstance(ctx).createOfflineRegion(def, meta, object : OfflineManager.CreateOfflineRegionCallback {
            override fun onCreate(offlineRegion: OfflineRegion) {
                offlineRegion.setObserver(object : OfflineRegion.OfflineRegionObserver {
                    override fun onStatusChanged(status: OfflineRegionStatus) {
                        val pct = if (status.requiredResourceCount > 0) 100.0 * status.completedResourceCount / status.requiredResourceCount else 0.0
                        progress = "Đã tải ${"%.0f".format(pct)}% · ${status.completedTileCount} mảnh · ${"%.1f".format(status.completedResourceSize / 1e6)} MB"
                        if (status.completedResourceSize > MAX_BYTES) {
                            offlineRegion.setDownloadState(OfflineRegion.STATE_INACTIVE); busy = false
                            progress = "Dừng ở 50 MB theo giới hạn của OpenFreeMap; phần đã tải vẫn dùng được."; refresh(ctx)
                        } else if (status.isComplete) {
                            offlineRegion.setDownloadState(OfflineRegion.STATE_INACTIVE); busy = false
                            progress = "Đã tải xong ${status.completedTileCount} mảnh, ${"%.1f".format(status.completedResourceSize / 1e6)} MB. Bản đồ này dùng được khi không có mạng."
                            refresh(ctx)
                        }
                    }
                    override fun onError(error: OfflineRegionError) { progress = "Lỗi tải: ${error.message}. Kiểm tra kết nối mạng."; busy = false }
                    override fun mapboxTileCountLimitExceeded(limit: Long) { progress = "Vượt giới hạn $limit mảnh."; busy = false }
                })
                offlineRegion.setDownloadState(OfflineRegion.STATE_ACTIVE)
            }
            override fun onError(error: String) { progress = "Không tạo được vùng tải: $error"; busy = false }
        })
        return null
    }

    fun delete(ctx: Context, id: Long) {
        OfflineManager.getInstance(ctx).listOfflineRegions(object : OfflineManager.ListOfflineRegionsCallback {
            override fun onList(offlineRegions: Array<OfflineRegion>?) {
                offlineRegions?.firstOrNull { it.id == id }?.delete(object : OfflineRegion.OfflineRegionDeleteCallback {
                    override fun onDelete() { refresh(ctx) }
                    override fun onError(error: String) {}
                })
            }
            override fun onError(error: String) {}
        })
    }
}

/** The map with the current position (blue dot) and the saved point (red dot). Pans freely; "follow" recentres on GPS. */
@Composable
fun MapPanel(modifier: Modifier, lat: Double?, lon: Double?, mark: Pair<Double, Double>?, follow: Int) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var style by remember { mutableStateOf<Style?>(null) }
    val view = remember { OfflineMap.init(ctx); MapView(ctx).also { it.onCreate(Bundle()) } }
    DisposableEffect(owner) {
        val obs = LifecycleEventObserver { _, e ->
            when (e) {
                Lifecycle.Event.ON_START -> view.onStart(); Lifecycle.Event.ON_RESUME -> view.onResume()
                Lifecycle.Event.ON_PAUSE -> view.onPause(); Lifecycle.Event.ON_STOP -> view.onStop()
                else -> {}
            }
        }
        owner.lifecycle.addObserver(obs); view.onStart(); view.onResume()
        onDispose { owner.lifecycle.removeObserver(obs); view.onPause(); view.onStop(); view.onDestroy() }
    }
    LaunchedEffect(Unit) {
        view.getMapAsync { m ->
            map = m
            m.cameraPosition = CameraPosition.Builder().target(LatLng(lat ?: 16.0, lon ?: 107.5)).zoom(if (lat != null) 14.0 else 4.5).build()
            m.setStyle(Style.Builder().fromUri(OfflineMap.STYLE)) { s ->
                s.addSource(GeoJsonSource("me")); s.addSource(GeoJsonSource("mark"))
                s.addLayer(CircleLayer("me-halo", "me").withProperties(PropertyFactory.circleRadius(16f), PropertyFactory.circleColor("#2F5BEA"), PropertyFactory.circleOpacity(0.18f)))
                s.addLayer(CircleLayer("me-dot", "me").withProperties(PropertyFactory.circleRadius(7f), PropertyFactory.circleColor("#2F5BEA"),
                    PropertyFactory.circleStrokeColor("#FFFFFF"), PropertyFactory.circleStrokeWidth(2.5f)))
                s.addLayer(CircleLayer("mark-dot", "mark").withProperties(PropertyFactory.circleRadius(7f), PropertyFactory.circleColor("#D93A3A"),
                    PropertyFactory.circleStrokeColor("#FFFFFF"), PropertyFactory.circleStrokeWidth(2.5f)))
                style = s
            }
        }
    }
    LaunchedEffect(style, lat, lon, mark) {
        val s = style ?: return@LaunchedEffect
        (s.getSource("me") as? GeoJsonSource)?.setGeoJson(if (lat != null && lon != null) FeatureCollection.fromFeature(Feature.fromGeometry(Point.fromLngLat(lon, lat))) else FeatureCollection.fromFeatures(emptyList()))
        (s.getSource("mark") as? GeoJsonSource)?.setGeoJson(if (mark != null) FeatureCollection.fromFeature(Feature.fromGeometry(Point.fromLngLat(mark.second, mark.first))) else FeatureCollection.fromFeatures(emptyList()))
    }
    LaunchedEffect(follow, map) {
        val m = map ?: return@LaunchedEffect
        if (follow > 0 && lat != null && lon != null) m.animateCamera(org.maplibre.android.camera.CameraUpdateFactory.newLatLngZoom(LatLng(lat, lon), 15.0))
    }
    AndroidView({ view }, modifier)
}
