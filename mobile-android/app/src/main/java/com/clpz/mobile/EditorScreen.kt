@file:androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)

package com.clpz.mobile

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.Undo
import androidx.compose.material.icons.automirrored.rounded.Redo
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun EditorScreen(initial: ClipProject, onSave: (ClipProject) -> Unit, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var project by remember(initial.id) { mutableStateOf(initial) }
    var tab by rememberSaveable(initial.id) { mutableIntStateOf(0) }
    val undo = remember(initial.id) { mutableStateListOf<ClipProject>() }
    val redo = remember(initial.id) { mutableStateListOf<ClipProject>() }
    var sliderStart by remember { mutableStateOf<ClipProject?>(null) }
    var rename by remember { mutableStateOf(false) }
    var title by remember { mutableStateOf(initial.name) }
    var exporting by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf<Int?>(null) }
    var exported by remember { mutableStateOf<File?>(null) }
    var saved by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val snackbar = remember { SnackbarHostState() }
    val exporter = remember { VideoExporter(context.applicationContext) }
    val player = remember(initial.id) { ExoPlayer.Builder(context).build().apply { repeatMode = Player.REPEAT_MODE_ONE } }
    var playing by remember { mutableStateOf(false) }
    var position by remember { mutableLongStateOf(0L) }
    val latestProject by rememberUpdatedState(project)
    val saveLatest by rememberUpdatedState(onSave)
    val lifecycleOwner = LocalLifecycleOwner.current
    val view = LocalView.current

    fun change(next: ClipProject) {
        if (project == next) return
        undo.add(project)
        if (undo.size > 50) undo.removeAt(0)
        redo.clear()
        project = next
    }
    fun leave() { onSave(project); onBack() }
    fun share(file: File) {
        try {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "video/mp4"; putExtra(Intent.EXTRA_STREAM, uri)
                clipData = ClipData.newRawUri("CLPZ clip", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(intent, "Share your clip"))
        } catch (_: Exception) { scope.launch { snackbar.showSnackbar("No sharing app is available. Use Save video instead.") } }
    }
    val saveVideo = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("video/mp4")) { uri ->
        val file = exported
        if (uri != null && file != null) scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    context.contentResolver.openOutputStream(uri)?.use { output -> file.inputStream().use { it.copyTo(output) } }
                        ?: error("Unable to write video")
                }
                snackbar.showSnackbar("Video saved. Your draft is still editable.")
            } catch (_: Exception) { snackbar.showSnackbar("Couldn’t save there. Try another folder.") }
        }
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) { playing = isPlaying }
            override fun onPlayerError(exception: PlaybackException) { error = "This video can’t be opened. It may have moved. Import the original again." }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener); player.release(); exporter.cancel(); view.keepScreenOn = false }
    }
    DisposableEffect(lifecycleOwner, player) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) { saveLatest(latestProject); player.pause() }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(project) { saved = false; delay(350); onSave(project); saved = true }
    LaunchedEffect(project.startMs, project.endMs) {
        delay(180)
        val item = MediaItem.Builder().setUri(project.sourceUri).setClippingConfiguration(
            MediaItem.ClippingConfiguration.Builder().setStartPositionMs(project.startMs).setEndPositionMs(project.endMs).build()
        ).build()
        player.setMediaItem(item); player.prepare(); position = 0
    }
    LaunchedEffect(project.aspect, project.caption, project.captionStyle, project.captionPosition, project.muted) {
        delay(120)
        player.volume = if (project.muted) 0f else 1f
        player.setVideoEffects(VideoEffects.create(project))
    }
    LaunchedEffect(player) { while (true) { position = player.currentPosition.coerceAtLeast(0); delay(100) } }
    BackHandler { if (!exporting) leave() }
    Scaffold(
        containerColor = Black, snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically) {
                IconAction("Back to library", Icons.AutoMirrored.Rounded.ArrowBack, !exporting) { leave() }
                Column(Modifier.weight(1f).clickable(enabled = !exporting) { title = project.name; rename = true }.padding(8.dp)) {
                    Text(project.name, maxLines = 1, fontWeight = FontWeight.SemiBold, fontSize = 15.sp,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                    Text(if (saved) "All changes saved" else "Saving…", color = if (saved) Mint else Muted, fontSize = 10.sp)
                }
                IconAction("Undo", Icons.AutoMirrored.Rounded.Undo, undo.isNotEmpty() && !exporting) {
                    redo.add(project); project = undo.removeAt(undo.lastIndex)
                }
                IconAction("Redo", Icons.AutoMirrored.Rounded.Redo, redo.isNotEmpty() && !exporting) {
                    undo.add(project); project = redo.removeAt(redo.lastIndex)
                }
            }
        },
        bottomBar = {
            Surface(color = Black, border = BorderStroke(1.dp, Edge)) {
                Column(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 10.dp)) {
                    PrimaryAction("Export video · ${timeLabel(project.endMs - project.startMs)}", Icons.Rounded.IosShare,
                        enabled = !exporting && error == null) {
                        onSave(project); player.pause(); exporting = true; progress = null; view.keepScreenOn = true
                        try {
                            exporter.export(project, { progress = it }) { result ->
                                exporting = false; view.keepScreenOn = false
                                result.onSuccess { exported = it }.onFailure {
                                    scope.launch { snackbar.showSnackbar("Export failed. Try a shorter clip or a different video.") }
                                }
                            }
                        } catch (_: Exception) {
                            exporting = false; view.keepScreenOn = false
                            scope.launch { snackbar.showSnackbar("Couldn’t start exporting. Check your available storage.") }
                        }
                    }
                }
            }
        }
    ) { padding ->
        BoxWithConstraints(Modifier.padding(padding).fillMaxSize().imePadding()) {
            val previewHeight = minOf(330.dp, maxHeight * .49f).coerceAtLeast(150.dp)
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                Box(Modifier.fillMaxWidth().height(previewHeight).background(Panel).padding(10.dp),
                    contentAlignment = Alignment.Center) {
                    AndroidView(factory = { PlayerView(it).apply { this.player = player; useController = false } },
                        modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(12.dp)))
                    Box(Modifier.align(Alignment.TopStart).padding(8.dp)) { Pill("LIVE PREVIEW", Ink) }
                    // Keep status outside the rendered picture.
                    if (error != null) Surface(Modifier.padding(16.dp), color = Black, shape = RoundedCornerShape(12.dp)) {
                        Text(error!!, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
                    }
                }
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconAction(if (playing) "Pause preview" else "Play preview", if (playing) Icons.Rounded.Pause else Icons.Rounded.PlayArrow) {
                        if (playing) player.pause() else player.play()
                    }
                    Slider(value = position.toFloat().coerceIn(0f, (project.endMs - project.startMs).toFloat()),
                        onValueChange = { player.seekTo(it.toLong()); position = it.toLong() },
                        valueRange = 0f..(project.endMs - project.startMs).toFloat().coerceAtLeast(1f), modifier = Modifier.weight(1f))
                    Text(timeLabel(position), color = Muted, fontSize = 11.sp, fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(start = 10.dp))
                }
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("Cut" to Icons.Rounded.ContentCut, "Text" to Icons.Rounded.TextFields, "Frame" to Icons.Rounded.Crop).forEachIndexed { index, (label, icon) ->
                        FilterChip(tab == index, { tab = index }, label = { Text(label) },
                            leadingIcon = { Icon(icon, null, Modifier.size(17.dp)) }, modifier = Modifier.weight(1f))
                    }
                }
                Column(Modifier.padding(horizontal = 24.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    when (tab) {
                        0 -> {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Eyebrow("Find your moment", Amber)
                                Text("${timeLabel(project.endMs - project.startMs)} selected", color = Muted, fontSize = 11.sp)
                            }
                            Text("Drag the handles to set your start and finish.", color = Muted, fontSize = 13.sp)
                            RangeSlider(
                                value = project.startMs.toFloat()..project.endMs.toFloat(),
                                onValueChange = { range ->
                                    if (sliderStart == null) sliderStart = project
                                    val minimum = minOf(500L, project.sourceDurationMs)
                                    val start = range.start.toLong().coerceIn(0L, project.sourceDurationMs - minimum)
                                    val end = range.endInclusive.toLong().coerceIn(start + minimum, project.sourceDurationMs)
                                    project = project.copy(startMs = start, endMs = end)
                                },
                                onValueChangeFinished = {
                                    sliderStart?.let { if (it != project) { undo.add(it); redo.clear() } }; sliderStart = null
                                },
                                valueRange = 0f..project.sourceDurationMs.toFloat().coerceAtLeast(1f)
                            )
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Pill("IN  ${timeLabel(project.startMs)}", Amber)
                                Pill("OUT  ${timeLabel(project.endMs)}", Amber)
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Rounded.VolumeUp, null, Modifier.size(20.dp), tint = Muted)
                                Text("Original audio", Modifier.weight(1f).padding(start = 12.dp))
                                Switch(!project.muted, { change(project.copy(muted = !it)) })
                            }
                        }
                        1 -> {
                            Eyebrow("Say it your way", Amber)
                            OutlinedTextField(project.caption, { if (it.length <= 100) change(project.copy(caption = it)) },
                                placeholder = { Text("Add a line worth remembering") }, label = { Text("On-screen text") },
                                supportingText = { Text("${project.caption.length}/100 · shown for the whole clip") },
                                shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth(), maxLines = 3)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                listOf("Bold", "Clean", "Highlight").forEach { style ->
                                    FilterChip(project.captionStyle == style, { change(project.copy(captionStyle = style)) },
                                        label = { Text(style, fontSize = 12.sp) })
                                }
                            }
                            Text("Position", color = Muted, fontSize = 12.sp)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                listOf("Top", "Middle", "Bottom").forEach { place ->
                                    FilterChip(project.captionPosition == place, { change(project.copy(captionPosition = place)) },
                                        label = { Text(place, fontSize = 12.sp) })
                                }
                            }
                        }
                        else -> {
                            Eyebrow("A frame for every feed", Amber)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                listOf("9:16" to "Vertical", "1:1" to "Square", "16:9" to "Wide").forEach { (ratio, label) ->
                                    Surface(onClick = { change(project.copy(aspect = ratio)) }, modifier = Modifier.weight(1f),
                                        shape = RoundedCornerShape(16.dp), color = if (project.aspect == ratio) Amber.copy(alpha = .12f) else Panel,
                                        border = BorderStroke(1.dp, if (project.aspect == ratio) Amber else Edge)) {
                                        Column(Modifier.padding(vertical = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                                            Box(Modifier.height(40.dp), contentAlignment = Alignment.Center) {
                                                val width = when (ratio) { "9:16" -> 20.dp; "1:1" -> 30.dp; else -> 40.dp }
                                                val height = when (ratio) { "9:16" -> 36.dp; "1:1" -> 30.dp; else -> 23.dp }
                                                Box(Modifier.size(width, height).border(2.dp, if (project.aspect == ratio) Amber else Muted, RoundedCornerShape(4.dp)))
                                            }
                                            Text(ratio, modifier = Modifier.padding(top = 10.dp), fontWeight = FontWeight.Bold)
                                            Text(label, color = Muted, fontSize = 11.sp)
                                        }
                                    }
                                }
                            }
                            Text("The crop stays centered. The preview shows your exported frame.", color = Muted, fontSize = 13.sp)
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Rounded.CheckCircleOutline, null, tint = Mint, modifier = Modifier.size(17.dp))
                                Text("720p · MP4 · original video untouched", color = Muted, fontSize = 11.sp, modifier = Modifier.padding(start = 8.dp))
                            }
                        }
                    }
                }
            }
        }
    }
    if (rename) AlertDialog(onDismissRequest = { rename = false }, title = { Text("Name your clip") },
        text = { OutlinedTextField(title, { title = it.take(64) }, singleLine = true, label = { Text("Clip name") }) },
        confirmButton = { TextButton({ change(project.copy(name = title.trim())); rename = false }, enabled = title.isNotBlank()) { Text("Save name") } },
        dismissButton = { TextButton({ rename = false }) { Text("Cancel") } })
    if (exporting) AlertDialog(onDismissRequest = {}, title = { Text("Making the final cut.") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Text("Keep CLPZ open while your video exports. Your draft is already saved.", color = Muted)
                if (progress == null) LinearProgressIndicator(Modifier.fillMaxWidth())
                else LinearProgressIndicator(progress = { progress!! / 100f }, modifier = Modifier.fillMaxWidth())
                Text(progress?.let { "$it% rendered" } ?: "Preparing the video…", color = Amber)
            }
        }, confirmButton = { TextButton({ exporter.cancel(); exporting = false; view.keepScreenOn = false }) { Text("Cancel export") } })
    exported?.let { file ->
        AlertDialog(onDismissRequest = { exported = null }, icon = { Icon(Icons.Rounded.CheckCircle, null, tint = Mint, modifier = Modifier.size(44.dp)) },
            title = { Text("Ready for the world.") }, text = {
                Text("Your video is rendered. Save it to your files or send it straight to another app. Your draft stays editable.")
            }, confirmButton = {
                TextButton({ saveVideo.launch(project.name.replace(Regex("[^A-Za-z0-9_-]"), "-") + ".mp4") }) { Text("Save video") }
            }, dismissButton = {
                Row {
                    TextButton({ exported = null }) { Text("Done") }
                    TextButton({ share(file) }) { Text("Share") }
                }
            })
    }
}
