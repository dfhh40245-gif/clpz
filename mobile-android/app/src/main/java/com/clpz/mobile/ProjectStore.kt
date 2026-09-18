package com.clpz.mobile

import android.content.Context
import android.content.Intent
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
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
    val muted: Boolean = false,
    /** "timeline" = automatic start/middle/end draft; "manual" = user-created/edited draft. */
    val draftKind: String = "timeline"
)

/**
 * Pure merge/suggestion logic, free of Android types so it can be unit-tested
 * on the JVM (app/src/test). ProjectStore delegates to these functions.
 */
object ProjectLogic {
    /**
     * Upsert by id: incoming projects replace existing rows with the same id
     * instead of appending duplicates. Rows present only in [existing] are kept.
     */
    fun mergeById(existing: List<ClipProject>, incoming: List<ClipProject>): List<ClipProject> {
        if (incoming.isEmpty()) return existing
        val incomingIds = incoming.map { it.id }.toHashSet()
        val kept = existing.filterNot { it.id in incomingIds }
        return kept + incoming
    }

    /**
     * Automatic "timeline drafts": fixed start/middle/end windows across the
     * source. These are NOT semantic/AI moment suggestions — the UI labels them
     * accordingly and semantic detection would be a separately evaluated feature.
     */
    fun timelineSuggestions(
        name: String,
        durationMs: Long,
        sourceUri: String,
        lengthMs: Long = 30_000L
    ): List<ClipProject> {
        require(durationMs >= 500) { "Choose a video at least half a second long." }
        val length = minOf(lengthMs, durationMs)
        val starts = listOf(0L, (durationMs / 2 - length / 2).coerceAtLeast(0), (durationMs - length).coerceAtLeast(0)).distinct()
        return starts.mapIndexed { index, start ->
            ClipProject(
                name = "${name.substringBeforeLast('.').take(32)} · ${index + 1}",
                sourceUri = sourceUri,
                sourceDurationMs = durationMs,
                startMs = start,
                endMs = start + length,
                draftKind = "timeline"
            )
        }
    }
}

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
                    captionPosition = row.optString("captionPosition", "Bottom"), muted = row.optBoolean("muted"),
                    draftKind = row.optString("draftKind", "timeline")
                )
            }.getOrNull()
        }.sortedByDescending { it.updatedAt }
    }

    fun save(project: ClipProject) = write(ProjectLogic.mergeById(load(), listOf(project)))
    fun saveAll(projects: List<ClipProject>) = write(ProjectLogic.mergeById(load(), projects))
    fun remove(id: String) = write(load().filterNot { it.id == id })
    fun duplicate(project: ClipProject) =
        save(project.copy(id = UUID.randomUUID().toString(), name = project.name + " copy", draftKind = "manual"))

    /**
     * True when the project's source is still readable: file:// sources must
     * exist on disk and content:// sources must still carry a persisted read
     * grant. Used to surface a recoverable "source missing" state instead of a
     * silent playback failure.
     */
    fun isSourceAvailable(context: Context, project: ClipProject): Boolean {
        val uri = runCatching { Uri.parse(project.sourceUri) }.getOrNull() ?: return false
        return when (uri.scheme) {
            "file" -> File(uri.path ?: return false).exists()
            "content" -> runCatching {
                context.checkUriPermission(
                    uri, android.os.Process.myPid(), android.os.Process.myUid(),
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                ) == android.content.pm.PackageManager.PERMISSION_GRANTED
            }.getOrDefault(false)
            else -> false
        }
    }

    private fun write(projects: List<ClipProject>) {
        val rows = JSONArray()
        projects.forEach { p ->
            rows.put(JSONObject().apply {
                put("id", p.id); put("name", p.name); put("sourceUri", p.sourceUri)
                put("sourceDurationMs", p.sourceDurationMs); put("startMs", p.startMs); put("endMs", p.endMs)
                put("caption", p.caption); put("aspect", p.aspect); put("updatedAt", p.updatedAt)
                put("captionStyle", p.captionStyle); put("captionPosition", p.captionPosition); put("muted", p.muted)
                put("draftKind", p.draftKind)
            })
        }
        prefs.edit().putString("rows", rows.toString()).apply()
    }

    fun suggestions(uri: Uri, durationMs: Long, name: String = "Untitled", lengthMs: Long = 30_000L): List<ClipProject> =
        ProjectLogic.timelineSuggestions(name, durationMs, uri.toString(), lengthMs)
}
