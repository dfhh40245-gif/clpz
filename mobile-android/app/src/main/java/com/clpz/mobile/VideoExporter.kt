package com.clpz.mobile

import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Environment
import android.text.SpannableString
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.graphics.Color
import android.graphics.Typeface
import androidx.annotation.OptIn
import androidx.media3.common.Effect
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.OverlayEffect
import androidx.media3.effect.Presentation
import androidx.media3.effect.TextOverlay
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.Effects
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.Transformer
import java.io.File

@OptIn(UnstableApi::class)
class VideoExporter(private val context:Context){
    fun export(project:ClipProject,onProgress:(String)->Unit,onDone:(Result<File>)->Unit){
        val dir=File(context.getExternalFilesDir(Environment.DIRECTORY_MOVIES),"CLPZ").apply{mkdirs()}
        val output=File(dir,"CLPZ-${project.name.replace(Regex("[^A-Za-z0-9_-]"),"-")}-${System.currentTimeMillis()}.mp4")
        val media=MediaItem.Builder().setUri(Uri.parse(project.sourceUri)).setClippingConfiguration(MediaItem.ClippingConfiguration.Builder().setStartPositionMs(project.startMs).setEndPositionMs(project.endMs).build()).build()
        val ratio=when(project.aspect){"1:1"->1f;"16:9"->16f/9f;else->9f/16f}
        val effects=mutableListOf<Effect>(Presentation.createForAspectRatio(ratio,Presentation.LAYOUT_SCALE_TO_FIT_WITH_CROP))
        if(project.caption.isNotBlank()){val text=SpannableString(project.caption.uppercase());text.setSpan(ForegroundColorSpan(Color.WHITE),0,text.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);text.setSpan(BackgroundColorSpan(Color.argb(170,0,0,0)),0,text.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);text.setSpan(StyleSpan(Typeface.BOLD),0,text.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);effects.add(OverlayEffect(listOf(TextOverlay.createStaticTextOverlay(text))))}
        val edited=EditedMediaItem.Builder(media).setEffects(Effects(emptyList(),effects)).build()
        val transformer=Transformer.Builder(context).addListener(object:Transformer.Listener{
            override fun onCompleted(composition:androidx.media3.transformer.Composition,result:ExportResult){MediaScannerConnection.scanFile(context,arrayOf(output.absolutePath),arrayOf("video/mp4"),null);onDone(Result.success(output))}
            override fun onError(composition:androidx.media3.transformer.Composition,result:ExportResult,exception:ExportException){output.delete();onDone(Result.failure(exception))}
        }).build()
        onProgress("Exporting on this device…")
        transformer.start(edited,output.absolutePath)
    }
}
