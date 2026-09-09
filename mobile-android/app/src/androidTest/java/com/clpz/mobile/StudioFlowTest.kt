package com.clpz.mobile

import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileInputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class StudioFlowTest {
    @get:Rule val compose = createComposeRule()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun fixture(): ClipProject {
        val file = File(context.filesDir, "fixture.mp4")
        instrumentation.context.assets.open("fixture.mp4").use { input -> file.outputStream().use { input.copyTo(it) } }
        return ClipProject(name = "A little perspective", sourceUri = Uri.fromFile(file).toString(),
            sourceDurationMs = 6000, startMs = 0, endMs = 5000)
    }

    private fun screenshot(name: String) {
        compose.waitForIdle()
        val dir = File(context.getExternalFilesDir(null), "screenshots").apply { mkdirs() }
        instrumentation.uiAutomation.takeScreenshot().let { bitmap ->
            File(dir, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            bitmap.recycle()
        }
        // Gradle removes the test app after the suite; retain captures outside its data directory.
        instrumentation.uiAutomation.executeShellCommand("mkdir -p /sdcard/Download/clpz-ui").use {
            FileInputStream(it.fileDescriptor).readBytes()
        }
        instrumentation.uiAutomation.executeShellCommand("cp ${File(dir, "$name.png").absolutePath} /sdcard/Download/clpz-ui/$name.png").use {
            FileInputStream(it.fileDescriptor).readBytes()
        }
    }

    @Test fun signInAndLocalEntryRemainAccessible() {
        var entered = false
        compose.setContent { ClpzTheme { AuthScreen(AuthRepository()) { entered = true } } }
        screenshot("01-sign-in")
        compose.onNodeWithText("Password").performTextInput("private-text")
        compose.onNodeWithContentDescription("Show password").performClick()
        compose.onNodeWithContentDescription("Hide password").assertExists()
        compose.onNodeWithText("Try the editor without an account").performScrollTo().performClick()
        assertTrue(entered)
    }

    @Test fun editorSavesAndUndoesTextChanges() {
        val clip = fixture()
        var saved = clip
        compose.setContent { ClpzTheme { EditorScreen(clip, onSave = { saved = it }, onBack = {}) } }
        compose.onNodeWithText("Text", substring = false).performScrollTo().performClick()
        compose.onNodeWithText("On-screen text").performScrollTo().performTextInput("Make it count.")
        compose.waitUntil(5000) { saved.caption == "Make it count." }
        screenshot("03-text-editor")
        compose.onNodeWithContentDescription("Undo").performClick()
        compose.waitUntil(5000) { saved.caption == "" }
        compose.onNodeWithContentDescription("Redo").performClick()
        compose.waitUntil(5000) { saved.caption == "Make it count." }
        compose.onNodeWithText("Frame", substring = false).performScrollTo().performClick()
        screenshot("04-frame-editor")
    }

    @Test fun libraryOpensSavedDrafts() {
        val store = ProjectStore(context)
        store.load().forEach { store.remove(it.id) }
        val clip = fixture()
        store.save(clip)
        store.save(clip.copy(id = "second", name = "Another point of view", startMs = 1000))
        compose.setContent { ClpzTheme { StudioScreen(AuthRepository(), false, {}) } }
        screenshot("02-library")
        compose.onNodeWithText("Continue editing →").performClick()
        compose.onNodeWithContentDescription("Back to library").assertExists()
        screenshot("05-cut-editor")
    }

    @Test fun exportKeepsTrimAndFrameAndProducesPlayableVideo() {
        val clip = fixture().copy(startMs = 1000, endMs = 4000, aspect = "1:1", caption = "Make it count.")
        val done = CountDownLatch(1)
        var result: Result<File>? = null
        instrumentation.runOnMainSync {
            VideoExporter(context).export(clip, {}) { result = it; done.countDown() }
        }
        assertTrue("Export timed out", done.await(90, TimeUnit.SECONDS))
        val file = result!!.getOrThrow()
        assertTrue(file.length() > 1000)
        val metadata = MediaMetadataRetriever()
        try {
            metadata.setDataSource(file.absolutePath)
            val width = metadata.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)
            val height = metadata.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)
            assertEquals(width, height)
            val duration = metadata.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)!!.toLong()
            assertTrue("Export duration $duration", duration in 2700L..3300L)
        } finally { metadata.release() }
    }
}
