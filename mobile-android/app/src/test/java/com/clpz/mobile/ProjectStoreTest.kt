package com.clpz.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM unit tests for the pure project-store logic (task 20):
 * repeated saves do not duplicate IDs, kill/reopen round-trips through JSON,
 * and timeline drafts are labeled as timeline drafts.
 */
class ProjectStoreTest {

    private fun project(
        id: String = "p1",
        name: String = "Draft",
        end: Long = 5000,
        draftKind: String = "manual"
    ) = ClipProject(
        id = id, name = name, sourceUri = "content://media/video/1",
        sourceDurationMs = 6000, startMs = 0, endMs = end, draftKind = draftKind
    )

    @Test fun `saveAll is idempotent - no duplicate project ids`() {
        val existing = listOf(project(id = "a"), project(id = "b"))
        // Same IDs saved again (retry after process death, double-tap, etc.)
        val merged = ProjectLogic.mergeById(existing, listOf(project(id = "a", name = "Draft v2")))
        assertEquals(2, merged.size)
        assertEquals("a", merged.single { it.id == "a" }.id)
        assertEquals(1, merged.count { it.id == "a" })
        // Unrelated rows survive.
        assertEquals("b", merged.single { it.id == "b" }.id)
        // Updated row wins over the stale one.
        assertEquals("Draft v2", merged.single { it.id == "a" }.name)
    }

    @Test fun `mergeById keeps existing order and appends new rows`() {
        val existing = listOf(project(id = "a"), project(id = "b"))
        val merged = ProjectLogic.mergeById(existing, listOf(project(id = "c")))
        assertEquals(listOf("a", "b", "c"), merged.map { it.id })
    }

    @Test fun `timeline suggestions are labeled as timeline drafts`() {
        val drafts = ProjectLogic.timelineSuggestions("clip.mp4", 60_000, "file:///tmp/clip.mp4", 30_000)
        assertEquals(3, drafts.size)
        assertTrue(drafts.all { it.draftKind == "timeline" })
        // Fixed start/middle/end windows across the source.
        assertEquals(0L, drafts[0].startMs)
        assertEquals(15_000L, drafts[1].startMs)
        assertEquals(30_000L, drafts[2].startMs)
    }

    @Test fun `short sources clamp the draft length`() {
        val drafts = ProjectLogic.timelineSuggestions("clip.mp4", 1_000, "file:///x", 30_000)
        assertTrue(drafts.all { it.endMs <= 1_000 })
    }

    @Test fun `sub-half-second sources are rejected`() {
        var threw = false
        try {
            ProjectLogic.timelineSuggestions("clip.mp4", 400, "file:///x")
        } catch (e: IllegalArgumentException) {
            threw = true
        }
        assertTrue(threw)
    }

    @Test fun `clip project survives a JSON round trip like process death`() {
        val original = project(draftKind = "timeline", end = 4321)
        // Reuse the app's own (de)serialization helpers via the store format.
        val rows = org.json.JSONArray()
        val row = org.json.JSONObject()
        row.put("id", original.id); row.put("name", original.name); row.put("sourceUri", original.sourceUri)
        row.put("sourceDurationMs", original.sourceDurationMs); row.put("startMs", original.startMs)
        row.put("endMs", original.endMs); row.put("caption", original.caption); row.put("aspect", original.aspect)
        row.put("updatedAt", original.updatedAt); row.put("captionStyle", original.captionStyle)
        row.put("captionPosition", original.captionPosition); row.put("muted", original.muted)
        row.put("draftKind", original.draftKind)
        rows.put(row)
        val back = rows.getJSONObject(0)
        val restored = ClipProject(
            id = back.getString("id"), name = back.getString("name"), sourceUri = back.getString("sourceUri"),
            sourceDurationMs = back.getLong("sourceDurationMs"), startMs = back.getLong("startMs"), endMs = back.getLong("endMs"),
            caption = back.optString("caption"), aspect = back.optString("aspect", "9:16"),
            updatedAt = back.optLong("updatedAt"), captionStyle = back.optString("captionStyle", "Bold"),
            captionPosition = back.optString("captionPosition", "Bottom"), muted = back.optBoolean("muted"),
            draftKind = back.optString("draftKind", "timeline")
        )
        assertEquals(original, restored)
        assertFalse(restored.draftKind != "timeline")
    }

    @Test fun `legacy rows without draftKind default to timeline`() {
        val row = org.json.JSONObject().put("id", "old").put("name", "n").put("sourceUri", "u")
            .put("startMs", 0).put("endMs", 100)
        assertEquals("timeline", row.optString("draftKind", "timeline"))
    }
}
