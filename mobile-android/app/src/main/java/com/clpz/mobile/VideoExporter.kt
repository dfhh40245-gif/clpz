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

@OptIn(UnstableApi::class)
class VideoExporter(private val context: Context) {
    private var transformer: Transformer? = null
    private var output: File? = null
    private val handler = Handler(Looper.getMainLooper())
    private var report: Runnable? = null

    fun export(project: ClipProject, onProgress: (Int?) -> Unit, onDone: (Result<File>) -> Unit) {
        require(project.endMs > project.startMs) { "Select a non-empty clip." }
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
                    stopPolling(); transformer = null
                    onDone(Result.success(file))
                }
                override fun onError(composition: Composition, result: ExportResult, exception: ExportException) {
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
        if (transformer != null) { transformer?.cancel(); output?.delete() }
        transformer = null
    }
    private fun stopPolling() { report?.let { handler.removeCallbacks(it) }; report = null }
}
