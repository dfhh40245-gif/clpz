package com.clpz.mobile

import android.content.Intent
import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.util.LruCache
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.io.File

private val thumbnailCache = object : LruCache<String, Bitmap>(12 * 1024 * 1024) {
    override fun sizeOf(key: String, value: Bitmap) = value.byteCount
}
private val thumbnailSlots = Semaphore(2)

@Composable
fun VideoThumbnail(project: ClipProject, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val key = project.sourceUri + ":" + project.startMs
    val bitmap by produceState<Bitmap?>(thumbnailCache.get(key), key) {
        if (value == null) value = withContext(Dispatchers.IO) {
            thumbnailSlots.withPermit {
                thumbnailCache.get(key) ?: runCatching {
                    val retriever = MediaMetadataRetriever()
                    try {
                        retriever.setDataSource(context, Uri.parse(project.sourceUri))
                        if (Build.VERSION.SDK_INT >= 27) retriever.getScaledFrameAtTime(
                            project.startMs * 1000, MediaMetadataRetriever.OPTION_CLOSEST_SYNC, 480, 480)
                        else null
                    } finally { retriever.release() }
                }.getOrNull()?.also { thumbnailCache.put(key, it) }
            }
        }
    }
    Box(modifier.background(Brush.linearGradient(listOf(Edge, Panel))), contentAlignment = Alignment.Center) {
        if (bitmap != null) Image(bitmap!!.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        else Icon(Icons.Rounded.Movie, null, Modifier.size(36.dp), tint = Muted)
    }
}

private data class ImportSource(val uri: Uri, val duration: Long, val name: String)

@Composable
fun StudioScreen(auth: AuthRepository, signedIn: Boolean, onSignIn: () -> Unit) {
    val context = LocalContext.current
    val store = remember { ProjectStore(context) }
    val scope = rememberCoroutineScope()
    var projects by remember { mutableStateOf(store.load()) }
    var editingId by rememberSaveable { mutableStateOf<String?>(null) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    var search by rememberSaveable { mutableStateOf("") }
    var shortestFirst by rememberSaveable { mutableStateOf(false) }
    var importing by remember { mutableStateOf(false) }
    var source by remember { mutableStateOf<ImportSource?>(null) }
    var length by remember { mutableIntStateOf(30) }
    var pendingDelete by remember { mutableStateOf<ClipProject?>(null) }
    val snackbar = remember { SnackbarHostState() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            importing = true
            try {
                source = withContext(Dispatchers.IO) {
                    val persisted = runCatching {
                        context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }.isSuccess
                    val readableUri = if (persisted) uri else {
                        val local = File(context.filesDir, "sources").apply { mkdirs() }
                        val copy = File(local, "${System.currentTimeMillis()}.mp4")
                        try {
                            context.contentResolver.openInputStream(uri)?.use { input ->
                                copy.outputStream().use { input.copyTo(it) }
                            } ?: error("Could not open this video.")
                        } catch (e: Exception) { copy.delete(); throw e }
                        Uri.fromFile(copy)
                    }
                    val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
                        if (it.moveToFirst()) it.getString(0) else "My video"
                    } ?: "My video"
                    val retriever = MediaMetadataRetriever()
                    try {
                        retriever.setDataSource(context, readableUri)
                        val duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()
                            ?: error("This video format couldn't be read.")
                        require(duration >= 500) { "Choose a video at least half a second long." }
                        ImportSource(readableUri, duration, name)
                    } finally { retriever.release() }
                }
            } catch (_: Exception) { snackbar.showSnackbar("Couldn’t open that video. Choose a local video and try again.") }
            finally { importing = false }
        }
    }
    fun importVideo() { if (!importing) picker.launch(arrayOf("video/*")) }

    val editing = projects.firstOrNull { it.id == editingId }
    if (editing != null) {
        EditorScreen(editing, onSave = { project -> store.save(project); projects = store.load() },
            onBack = { editingId = null })
        return
    }
    BackHandler(section != 0) { section = 0 }
    Scaffold(
        containerColor = Black,
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            Surface(color = Black, border = BorderStroke(1.dp, Edge)) {
                Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 22.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton({ section = 0 }) {
                        Icon(Icons.Rounded.GridView, null, Modifier.size(19.dp), tint = if (section == 0) Amber else Muted)
                        Spacer(Modifier.width(8.dp)); Text("Library", color = if (section == 0) Ink else Muted)
                    }
                    FilledIconButton({ importVideo() }, enabled = !importing, modifier = Modifier.size(52.dp),
                        shape = RoundedCornerShape(17.dp)) { Icon(Icons.Rounded.Add, "Import video") }
                    TextButton({ section = 1 }) {
                        Icon(Icons.Rounded.PersonOutline, null, Modifier.size(20.dp), tint = if (section == 1) Amber else Muted)
                        Spacer(Modifier.width(8.dp)); Text("Account", color = if (section == 1) Ink else Muted)
                    }
                }
            }
        }
    ) { padding ->
        if (section == 1) {
            AccountScreen(auth, signedIn, projects.size, Modifier.padding(padding), onSignIn) {
                scope.launch {
                    try { auth.signOut(); onSignIn() } catch (_: Exception) { snackbar.showSnackbar("Couldn’t sign out. Please try again.") }
                }
            }
        } else {
            val filtered = projects.filter { it.name.contains(search, ignoreCase = true) }
                .let { if (shortestFirst) it.sortedBy { p -> p.endMs - p.startMs } else it }
            LazyVerticalGrid(columns = GridCells.Adaptive(156.dp), modifier = Modifier.padding(padding).fillMaxSize(),
                contentPadding = PaddingValues(20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp)) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Wordmark(); Spacer(Modifier.weight(1f)); Pill("ON YOUR DEVICE", Mint)
                    }
                }
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.padding(top = 12.dp, bottom = 4.dp)) {
                        Eyebrow("Your pocket studio", Amber)
                        Text("Good footage.\nGreat possibilities.", style = MaterialTheme.typography.headlineLarge,
                            modifier = Modifier.padding(top = 10.dp))
                        Text("Pick a moment. Make it yours.", color = Muted, modifier = Modifier.padding(top = 10.dp))
                    }
                }
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Surface(onClick = { importVideo() }, shape = RoundedCornerShape(22.dp),
                        color = Amber, modifier = Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Rounded.Add, null, Modifier.size(30.dp), tint = Black)
                            Column(Modifier.weight(1f).padding(horizontal = 14.dp)) {
                                Text("Start a new clip", color = Black, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                                Text("Import from your camera roll or files", color = Black.copy(alpha = .75f), fontSize = 12.sp)
                            }
                            Icon(Icons.AutoMirrored.Rounded.ArrowForward, null, tint = Black)
                        }
                    }
                }
                if (projects.isNotEmpty() && search.isBlank()) item(span = { GridItemSpan(maxLineSpan) }) {
                    val latest = projects.first()
                    Column(Modifier.padding(top = 6.dp)) {
                        Eyebrow("Pick up where you left off")
                        Surface(onClick = { editingId = latest.id }, shape = RoundedCornerShape(22.dp),
                            modifier = Modifier.padding(top = 12.dp), color = Panel, border = BorderStroke(1.dp, Edge)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                VideoThumbnail(latest, Modifier.size(96.dp))
                                Column(Modifier.weight(1f).padding(14.dp)) {
                                    Text(latest.name, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold)
                                    Text("Saved draft · ${timeLabel(latest.endMs - latest.startMs)}", color = Muted, fontSize = 12.sp)
                                    Text("Continue editing →", color = Amber, fontSize = 12.sp, modifier = Modifier.padding(top = 7.dp))
                                }
                            }
                        }
                    }
                }
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Your drafts", style = MaterialTheme.typography.titleLarge)
                            Spacer(Modifier.width(10.dp)); Pill(projects.size.toString())
                            Spacer(Modifier.weight(1f))
                            TextButton({ shortestFirst = !shortestFirst }) {
                                Text(if (shortestFirst) "Shortest first" else "Recent", fontSize = 12.sp)
                                Icon(Icons.Rounded.Sort, null, Modifier.padding(start = 6.dp).size(17.dp))
                            }
                        }
                        if (projects.isNotEmpty()) OutlinedTextField(search, { search = it }, placeholder = { Text("Find a draft") },
                            leadingIcon = { Icon(Icons.Rounded.Search, null) }, singleLine = true,
                            trailingIcon = { if (search.isNotEmpty()) IconAction("Clear search", Icons.Rounded.Close) { search = "" } },
                            shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth())
                    }
                }
                if (filtered.isEmpty()) item(span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().padding(vertical = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Surface(shape = CircleShape, color = Panel) { Icon(Icons.Rounded.MovieCreation, null, Modifier.padding(24.dp).size(32.dp), tint = Amber) }
                        Text(if (search.isBlank()) "Your next great clip starts here." else "No matching drafts.",
                            fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 18.dp))
                        Text(if (search.isBlank()) "Import a video. Your edits stay saved\nso you can come back anytime." else "Try a different name.",
                            color = Muted, fontSize = 13.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            modifier = Modifier.padding(top = 8.dp))
                    }
                }
                items(filtered, key = { it.id }) { project ->
                    ProjectCard(project, onEdit = { editingId = project.id },
                        onDuplicate = { store.duplicate(project); projects = store.load() },
                        onDelete = { pendingDelete = project })
                }
            }
        }
    }
    if (importing) AlertDialog(onDismissRequest = {}, confirmButton = {},
        title = { Text("Opening your video") }, text = {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("Preparing your footage. Nothing is uploaded.")
            }
        })
    source?.let { video ->
        AlertDialog(onDismissRequest = { source = null }, title = { Text("Make your first cuts.") }, text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(video.name, fontWeight = FontWeight.SemiBold)
                Text("${timeLabel(video.duration)} · Choose a starting clip length.", color = Muted)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(15, 30, 60).forEach { seconds ->
                        FilterChip(length == seconds, { length = seconds }, label = { Text("${seconds}s") })
                    }
                }
                Text("We’ll make up to 3 drafts from the start, middle, and end. Refine the cuts in the editor.", color = Muted)
            }
        }, confirmButton = {
            TextButton({
                store.saveAll(store.suggestions(video.uri, video.duration, video.name, length * 1000L))
                projects = store.load(); source = null; section = 0; search = ""
                scope.launch { snackbar.showSnackbar("Drafts ready. Tap one to start editing.") }
            }) { Text("Create drafts") }
        }, dismissButton = { TextButton({ source = null }) { Text("Cancel") } })
    }
    pendingDelete?.let { project ->
        AlertDialog(onDismissRequest = { pendingDelete = null }, title = { Text("Delete this draft?") },
            text = { Text("“${project.name}” will be removed. Your original video and exported files stay on your device.") },
            confirmButton = { TextButton({ store.remove(project.id); projects = store.load(); pendingDelete = null }) { Text("Delete draft", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ pendingDelete = null }) { Text("Keep draft") } })
    }
}

@Composable
fun ProjectCard(project: ClipProject, onEdit: () -> Unit, onDuplicate: () -> Unit, onDelete: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    Surface(onClick = onEdit, shape = RoundedCornerShape(20.dp), color = Panel, border = BorderStroke(1.dp, Edge)) {
        Column {
            Box {
                VideoThumbnail(project, Modifier.fillMaxWidth().aspectRatio(1.3f))
                Row(Modifier.align(Alignment.BottomStart).padding(10.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Pill(timeLabel(project.endMs - project.startMs))
                    Pill(project.aspect)
                }
            }
            Row(Modifier.padding(start = 12.dp, top = 5.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(project.name, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    Text("Editable draft", color = Muted, fontSize = 11.sp)
                }
                Box {
                    IconAction("Options for ${project.name}", Icons.Rounded.MoreVert) { menu = true }
                    DropdownMenu(menu, { menu = false }) {
                        DropdownMenuItem(text = { Text("Duplicate") }, onClick = { menu = false; onDuplicate() }, leadingIcon = { Icon(Icons.Rounded.ContentCopy, null) })
                        DropdownMenuItem(text = { Text("Delete") }, onClick = { menu = false; onDelete() }, leadingIcon = { Icon(Icons.Rounded.DeleteOutline, null) })
                    }
                }
            }
        }
    }
}

@Composable
private fun AccountScreen(auth: AuthRepository, signedIn: Boolean, count: Int, modifier: Modifier, onSignIn: () -> Unit, onSignOut: () -> Unit) {
    val context = LocalContext.current
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(22.dp)) {
        Wordmark()
        Eyebrow("Your space", Amber)
        Text("Keep creating.", style = MaterialTheme.typography.headlineLarge)
        Surface(shape = RoundedCornerShape(24.dp), color = Panel, border = BorderStroke(1.dp, Edge)) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(Icons.Rounded.PersonOutline, null, Modifier.size(36.dp), tint = Amber)
                Text(if (signedIn) auth.email() ?: "CLPZ account" else "Local workspace", style = MaterialTheme.typography.titleLarge)
                Text("$count saved drafts on this device.", color = Muted)
                Text("Your originals stay untouched. Removing the app also removes local drafts, so save your finished videos first.", color = Muted, fontSize = 13.sp)
            }
        }
        PrimaryAction(if (signedIn) "Manage plans & credits" else "Sign in to CLPZ", Icons.Rounded.CreditCard) {
            if (signedIn) context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.WEBSITE_URL + "/account")))
            else onSignIn()
        }
        Text("One account for the website and mobile. Your plan and payments are managed on the CLPZ website.", color = Muted)
        if (signedIn) OutlinedButton(onSignOut, Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) { Text("Sign out") }
        Text("CLPZ Mobile · ${BuildConfig.VERSION_NAME}", color = Muted, fontSize = 12.sp)
    }
}
