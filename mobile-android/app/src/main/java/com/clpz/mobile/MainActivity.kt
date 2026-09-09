@file:androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)

package com.clpz.mobile

import android.content.Intent
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.launch

private val Ink=Color(0xFFF7F2E9);private val Muted=Color(0xFFA79F92);private val Amber=Color(0xFFF0A030);private val Black=Color(0xFF080705);private val Panel=Color(0xFF14110E)

class MainActivity:ComponentActivity(){
    private val auth=AuthRepository()
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);if(auth.configured)runCatching{auth.handleDeepLink(intent)};setContent{ClpzTheme{ClpzApp(auth)}}}
    override fun onNewIntent(intent:Intent){super.onNewIntent(intent);setIntent(intent);if(auth.configured)runCatching{auth.handleDeepLink(intent)};recreate()}
}

@Composable fun ClpzTheme(content: @Composable () -> Unit){MaterialTheme(colorScheme=darkColorScheme(primary=Amber,background=Black,surface=Panel,onBackground=Ink,onSurface=Ink)){Surface(Modifier.fillMaxSize(),color=Black){content()}}}

@Composable fun ClpzApp(auth:AuthRepository){var authenticated by remember{mutableStateOf(auth.signedIn())};if(!authenticated){AuthScreen(auth){authenticated=true};return};val context=LocalContext.current;val scope=rememberCoroutineScope();val store=remember{ProjectStore(context)};var projects by remember{mutableStateOf(store.load())};var editing by remember{mutableStateOf<ClipProject?>(null)};if(editing!=null){EditorScreen(editing!!,{p->store.save(p);projects=store.load();editing=null},{editing=null});return}
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null){runCatching{context.contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION)};val retriever=MediaMetadataRetriever();runCatching{retriever.setDataSource(context,uri);val duration=retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()?:60_000L;val suggestions=store.suggestions(uri,duration);suggestions.forEach(store::save);projects=store.load();editing=suggestions.first()};retriever.release()}}
    LazyColumn(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF211408),Black))).padding(horizontal=20.dp),contentPadding=PaddingValues(bottom=42.dp)){
        item{Row(Modifier.fillMaxWidth().padding(top=28.dp,bottom=30.dp),verticalAlignment=Alignment.CenterVertically){Text("CLPZ",fontSize=30.sp,fontWeight=FontWeight.Black,letterSpacing=2.sp);Spacer(Modifier.weight(1f));IconButton({context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse("${BuildConfig.WEBSITE_URL}/#get-clpz")))}){Icon(Icons.Rounded.CreditCard,"Plans",tint=Amber)};IconButton({scope.launch{auth.signOut();authenticated=false}}){Icon(Icons.Rounded.Logout,"Sign out",tint=Muted)}};Text("Your clip studio",fontSize=40.sp,lineHeight=42.sp,fontWeight=FontWeight.Bold);Text("Import a video, shape the moment, and return to every editable draft.",color=Muted,modifier=Modifier.padding(top=10.dp,bottom=24.dp));Button(onClick={picker.launch(arrayOf("video/*"))},modifier=Modifier.fillMaxWidth().height(56.dp),shape=RoundedCornerShape(14.dp),colors=ButtonDefaults.buttonColors(containerColor=Amber,contentColor=Black)){Icon(Icons.Rounded.Add,"",Modifier.size(20.dp));Spacer(Modifier.width(8.dp));Text("Create clips from a video",fontWeight=FontWeight.Bold)};Row(Modifier.fillMaxWidth().padding(top=34.dp,bottom=14.dp),verticalAlignment=Alignment.CenterVertically){Text("EDITABLE PROJECTS",color=Amber,fontSize=11.sp,fontWeight=FontWeight.Bold,letterSpacing=1.sp);Spacer(Modifier.weight(1f));Text("${projects.size}",color=Muted)}}
        if(projects.isEmpty())item{Box(Modifier.fillMaxWidth().height(230.dp).background(Color.White.copy(.04f),RoundedCornerShape(18.dp)),contentAlignment=Alignment.Center){Column(horizontalAlignment=Alignment.CenterHorizontally){Icon(Icons.Rounded.VideoLibrary,"",tint=Muted,modifier=Modifier.size(42.dp));Text("Your saved clips appear here",color=Muted,modifier=Modifier.padding(top=12.dp))}}}
        items(projects,key={it.id}){project->ProjectCard(project,onEdit={editing=project},onDelete={store.remove(project.id);projects=store.load()})}
    }
}

@Composable fun ProjectCard(project:ClipProject,onEdit:()->Unit,onDelete:()->Unit){Card(Modifier.fillMaxWidth().padding(bottom=12.dp).clickable(onClick=onEdit),shape=RoundedCornerShape(16.dp),colors=CardDefaults.cardColors(containerColor=Panel)){Row(Modifier.padding(16.dp),verticalAlignment=Alignment.CenterVertically){Box(Modifier.size(62.dp).background(Brush.linearGradient(listOf(Color(0xFF9A481F),Color(0xFF21130C))),RoundedCornerShape(12.dp)),contentAlignment=Alignment.Center){Icon(Icons.Rounded.PlayArrow,"Edit",tint=Ink)};Column(Modifier.weight(1f).padding(horizontal=14.dp)){Text(project.name,fontWeight=FontWeight.Bold);Text("${project.startMs/1000}s — ${project.endMs/1000}s · ${project.aspect}",color=Muted,fontSize=12.sp);if(project.caption.isNotBlank())Text(project.caption,color=Amber,fontSize=11.sp,maxLines=1)};IconButton(onDelete){Icon(Icons.Rounded.Delete,"Delete",tint=Muted)}}}}

@Composable fun EditorScreen(initial:ClipProject,onSave:(ClipProject)->Unit,onBack:()->Unit){val context=LocalContext.current;var project by remember{mutableStateOf(initial)};var exporting by remember{mutableStateOf(false)};var status by remember{mutableStateOf("")};val duration=initial.sourceDurationMs.coerceAtLeast(1_000L)/1000f;val player=remember(initial.sourceUri){ExoPlayer.Builder(context).build().apply{setMediaItem(MediaItem.fromUri(initial.sourceUri));prepare()}};DisposableEffect(player){onDispose{player.release()}}
    Column(Modifier.fillMaxSize().background(Black)){Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){IconButton(onBack){Icon(Icons.Rounded.ArrowBack,"Back")};Text("Edit clip",fontWeight=FontWeight.Bold);Spacer(Modifier.weight(1f));TextButton({onSave(project)}){Text("Save",color=Amber,fontWeight=FontWeight.Bold)}};Box(Modifier.fillMaxWidth().weight(.48f).background(Color.Black),contentAlignment=Alignment.Center){AndroidView({PlayerView(it).apply{this.player=player;useController=true}},Modifier.fillMaxSize());if(project.caption.isNotBlank())Text(project.caption,color=Color.White,fontWeight=FontWeight.Black,fontSize=22.sp,modifier=Modifier.align(Alignment.BottomCenter).padding(36.dp).background(Color.Black.copy(.6f),RoundedCornerShape(6.dp)).padding(8.dp))};Column(Modifier.fillMaxWidth().weight(.52f).padding(20.dp)){Text("TRIM",color=Amber,fontSize=11.sp,fontWeight=FontWeight.Bold);RangeSlider(value=(project.startMs/1000f)..(project.endMs/1000f),onValueChange={project=project.copy(startMs=(it.start*1000).toLong(),endMs=(it.endInclusive*1000).toLong())},valueRange=0f..duration.coerceAtLeast(1f),modifier=Modifier.fillMaxWidth());Text("${project.startMs/1000}s  —  ${project.endMs/1000}s",color=Muted,fontSize=12.sp);OutlinedTextField(project.caption,{project=project.copy(caption=it)},label={Text("Caption")},modifier=Modifier.fillMaxWidth().padding(top=12.dp),singleLine=true);Row(Modifier.padding(vertical=15.dp)){listOf("9:16","1:1","16:9").forEach{ratio->FilterChip(selected=project.aspect==ratio,onClick={project=project.copy(aspect=ratio)},label={Text(ratio)},modifier=Modifier.padding(end=8.dp))}};Button(onClick={exporting=true;VideoExporter(context).export(project,{status=it}){result->exporting=false;status=result.fold({"Saved to ${it.parentFile?.name}"},{it.message?:"Export failed"})}},enabled=!exporting,modifier=Modifier.fillMaxWidth().height(52.dp),colors=ButtonDefaults.buttonColors(containerColor=Amber,contentColor=Black)){Icon(Icons.Rounded.FileDownload,"",Modifier.size(20.dp));Spacer(Modifier.width(8.dp));Text(if(exporting)"Exporting…" else "Export MP4",fontWeight=FontWeight.Bold)};if(status.isNotBlank())Text(status,color=Muted,fontSize=12.sp,modifier=Modifier.padding(top=10.dp))}}
}

@Composable fun AuthScreen(auth:AuthRepository,onDone:()->Unit){var email by remember{mutableStateOf("")};var password by remember{mutableStateOf("")};var signup by remember{mutableStateOf(false)};var message by remember{mutableStateOf(if(auth.configured)"" else "This build is missing its Supabase configuration.")};var busy by remember{mutableStateOf(false)};val scope=rememberCoroutineScope();Box(Modifier.fillMaxSize().background(Brush.radialGradient(listOf(Color(0xFFF0A030),Color(0xFF4A2A0E),Black),radius=1200f)).padding(22.dp),contentAlignment=Alignment.Center){Card(shape=RoundedCornerShape(24.dp),colors=CardDefaults.cardColors(containerColor=Color(0xDD11100E))){Column(Modifier.padding(26.dp),horizontalAlignment=Alignment.CenterHorizontally){Text("CLPZ",fontSize=34.sp,fontWeight=FontWeight.Black,letterSpacing=3.sp);Text(if(signup)"Create your account" else "Welcome back",fontSize=26.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=20.dp));Text("The same account works on the website and mobile.",color=Muted,fontSize=13.sp,modifier=Modifier.padding(vertical=8.dp));OutlinedTextField(email,{email=it},label={Text("Email")},singleLine=true,modifier=Modifier.fillMaxWidth().padding(top=12.dp));OutlinedTextField(password,{password=it},label={Text("Password")},singleLine=true,modifier=Modifier.fillMaxWidth().padding(top=10.dp));if(message.isNotBlank())Text(message,color=Color(0xFFFF9D7B),fontSize=12.sp,modifier=Modifier.padding(top=10.dp));Button({scope.launch{busy=true;message="";runCatching{if(signup)auth.signUp(email,password)else auth.signIn(email,password)}.onSuccess{if(signup)message="Check your email, then sign in." else onDone()}.onFailure{message=it.message?:"Could not continue"};busy=false}},enabled=auth.configured&&!busy&&email.isNotBlank()&&password.length>=6,modifier=Modifier.fillMaxWidth().height(52.dp).padding(top=12.dp),colors=ButtonDefaults.buttonColors(containerColor=Amber,contentColor=Black)){Text(if(signup)"Create account" else "Sign in",fontWeight=FontWeight.Bold)};TextButton({signup=!signup;message=""},enabled=auth.configured){Text(if(signup)"Already registered? Sign in" else "New to CLPZ? Sign up",color=Amber)};TextButton({scope.launch{runCatching{auth.google()}.onFailure{message=it.message?:"Google sign-in failed"}}},enabled=auth.configured){Text("Continue with Google",color=Ink)}}}}}
