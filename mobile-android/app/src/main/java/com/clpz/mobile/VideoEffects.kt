package com.clpz.mobile

import android.graphics.Color
import android.graphics.Typeface
import android.text.Layout
import android.text.SpannableString
import android.text.Spanned
import android.text.style.*
import androidx.annotation.OptIn
import androidx.media3.common.Effect
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.*
import java.util.Locale

@OptIn(UnstableApi::class)
object VideoEffects {
    fun create(project: ClipProject): List<Effect> {
        val ratio = when (project.aspect) { "1:1" -> 1f; "16:9" -> 16f / 9; else -> 9f / 16 }
        val effects = mutableListOf<Effect>(
            Presentation.createForAspectRatio(ratio, Presentation.LAYOUT_SCALE_TO_FIT_WITH_CROP),
            Presentation.createForHeight(720)
        )
        if (project.caption.isNotBlank()) {
            val raw = if (project.captionStyle == "Bold") project.caption.uppercase(Locale.ROOT) else project.caption
            val lineLength = if (project.aspect == "9:16") 19 else 32
            val wrapped = raw.split("\n").joinToString("\n") { line ->
                val words = line.split(" ")
                val lines = mutableListOf("")
                for (word in words) {
                    if (lines.last().length + word.length + 1 > lineLength && lines.last().isNotEmpty()) lines.add("")
                    lines[lines.lastIndex] = (lines.last() + " " + word).trim()
                }
                lines.joinToString("\n")
            }
            val text = SpannableString(wrapped)
            fun span(value: Any) = text.setSpan(value, 0, text.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            span(ForegroundColorSpan(if (project.captionStyle == "Highlight") Color.BLACK else Color.WHITE))
            span(BackgroundColorSpan(if (project.captionStyle == "Highlight") Color.rgb(255, 195, 105) else Color.argb(180, 0, 0, 0)))
            span(StyleSpan(if (project.captionStyle == "Clean") Typeface.NORMAL else Typeface.BOLD))
            span(AbsoluteSizeSpan(26))
            span(AlignmentSpan.Standard(Layout.Alignment.ALIGN_CENTER))
            val y = when (project.captionPosition) { "Top" -> .68f; "Middle" -> 0f; else -> -.60f }
            val settings = StaticOverlaySettings.Builder().setBackgroundFrameAnchor(0f, y).build()
            effects.add(OverlayEffect(listOf(TextOverlay.createStaticTextOverlay(text, settings))))
        }
        return effects
    }
}
