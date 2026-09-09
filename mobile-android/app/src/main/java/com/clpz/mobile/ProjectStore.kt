package com.clpz.mobile

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class ClipProject(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val sourceUri: String,
    val sourceDurationMs: Long,
    val startMs: Long,
    val endMs: Long,
    val caption: String = "",
    val aspect: String = "9:16",
    val updatedAt: Long = System.currentTimeMillis(),
    val captionStyle: String = "Bold",
    val captionPosition: String = "Bottom",
    val muted: Boolean = false
)

class ProjectStore(context: Context) {
    private val prefs = context.getSharedPreferences("clpz_projects", Context.MODE_PRIVATE)

    fun load(): List<ClipProject> {
        val rows = runCatching { JSONArray(prefs.getString("rows", "[]")) }.getOrDefault(JSONArray())
        return (0 until rows.length()).mapNotNull { index ->
            runCatching {
                val row = rows.getJSONObject(index)
                val end = row.getLong("endMs")
                ClipProject(
                    id = row.getString("id"), name = row.getString("name"), sourceUri = row.getString("sourceUri"),
                    sourceDurationMs = row.optLong("sourceDurationMs", end), startMs = row.getLong("startMs"),
                    endMs = end, caption = row.optString("caption"), aspect = row.optString("aspect", "9:16"),
                    updatedAt = row.optLong("updatedAt"), captionStyle = row.optString("captionStyle", "Bold"),
                    captionPosition = row.optString("captionPosition", "Bottom"), muted = row.optBoolean("muted")
                )
            }.getOrNull()
        }.sortedByDescending { it.updatedAt }
    }

    fun save(project: ClipProject) = write(load().filterNot { it.id == project.id } + project.copy(updatedAt = System.currentTimeMillis()))
    fun saveAll(projects: List<ClipProject>) = write(load() + projects)
    fun remove(id: String) = write(load().filterNot { it.id == id })
    fun duplicate(project: ClipProject) = save(project.copy(id = UUID.randomUUID().toString(), name = project.name + " copy"))

    private fun write(projects: List<ClipProject>) {
        val rows = JSONArray()
        projects.forEach { p ->
            rows.put(JSONObject().apply {
                put("id", p.id); put("name", p.name); put("sourceUri", p.sourceUri)
                put("sourceDurationMs", p.sourceDurationMs); put("startMs", p.startMs); put("endMs", p.endMs)
                put("caption", p.caption); put("aspect", p.aspect); put("updatedAt", p.updatedAt)
                put("captionStyle", p.captionStyle); put("captionPosition", p.captionPosition); put("muted", p.muted)
            })
        }
        prefs.edit().putString("rows", rows.toString()).apply()
    }

    fun suggestions(uri: Uri, durationMs: Long, name: String = "Untitled", lengthMs: Long = 30_000L): List<ClipProject> {
        require(durationMs >= 500) { "Choose a video at least half a second long." }
        val length = minOf(lengthMs, durationMs)
        val starts = listOf(0L, (durationMs / 2 - length / 2).coerceAtLeast(0), (durationMs - length).coerceAtLeast(0)).distinct()
        return starts.mapIndexed { index, start ->
            ClipProject(name = "${name.substringBeforeLast('.').take(32)} · ${index + 1}", sourceUri = uri.toString(),
                sourceDurationMs = durationMs, startMs = start, endMs = start + length)
        }
    }
}
