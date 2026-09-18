package com.clpz.mobile

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.annotation.OptIn
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.*
import java.io.File

/**
 * Cancellation contract (task 20): [cancel] must (1) stop any in-flight export
 * work, (2) delete the partial output file, and (3) guarantee the completion
 * callback never fires — and never fires with success. [isBusy] mirrors that:
 * it stays true from start() until cancel or a terminal callback.
 */
@OptIn(UnstableApi::class)
class VideoExporter(private val context: Context) {
    private var transformer: Transformer? = null
    private var output: File? = null
    private val handler = Handler(Looper.getMainLooper())
    private var report: Runnable? = null
    private var cancelled = false

    val isBusy: Boolean get() = transformer != null

    fun export(project: ClipProject, onProgress: (Int?) -> Unit, onDone: (Result<File>) -> Unit) {
        check(!isBusy) { "An export is already running." }
        require(project.endMs > project.startMs) { "Select a non-empty clip." }
        cancelled = false
        val directory = File(context.filesDir, "exports").apply { mkdirs() }
        val file = File(directory, "CLPZ-${System.currentTimeMillis()}.mp4")
        output = file
        val media = MediaItem.Builder().setUri(project.sourceUri).setClippingConfiguration(
            MediaItem.ClippingConfiguration.Builder().setStartPositionMs(project.startMs).setEndPositionMs(project.endMs).build()
        ).build()
        val edited = EditedMediaItem.Builder(media).setRemoveAudio(project.muted)
            .setEffects(Effects(emptyList(), VideoEffects.create(project))).build()
        val task = Transformer.Builder(context).setVideoMimeType(MimeTypes.VIDEO_H264)
            .addListener(object : Transformer.Listener {
                override fun onCompleted(composition: Composition, result: ExportResult) {
                    if (cancelled) return
                    stopPolling(); transformer = null
                    onDone(Result.success(file))
                }
                override fun onError(composition: Composition, result: ExportResult, exception: ExportException) {
                    if (cancelled) return
                    stopPolling(); transformer = null; file.delete()
                    onDone(Result.failure(exception))
                }
            }).build()
        transformer = task
        report = object : Runnable {
            override fun run() {
                val holder = ProgressHolder()
                val state = task.getProgress(holder)
                onProgress(if (state == Transformer.PROGRESS_STATE_AVAILABLE) holder.progress else null)
                handler.postDelayed(this, 300)
            }
        }
        try { task.start(edited, file.absolutePath); handler.post(report!!) }
        catch (e: Exception) { stopPolling(); transformer = null; file.delete(); onDone(Result.failure(e)) }
    }

    fun cancel() {
        stopPolling()
        cancelled = true
        transformer?.cancel()
        transformer = null
        output?.delete()
    }

    private fun stopPolling() { report?.let { handler.removeCallbacks(it) }; report = null }
}
