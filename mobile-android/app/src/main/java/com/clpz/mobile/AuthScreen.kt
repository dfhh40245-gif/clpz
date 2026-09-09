package com.clpz.mobile

import android.content.Intent
import android.net.Uri
import android.util.Patterns
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

@Composable
fun AuthScreen(auth: AuthRepository, onContinue: () -> Unit) {
    var email by rememberSaveable { mutableStateOf("") }
    // Passwords stay in memory, outside saved-instance state.
    var password by remember { mutableStateOf("") }
    var visible by remember { mutableStateOf(false) }
    var signup by rememberSaveable { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var success by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    Column(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Panel, Black), endY = 950f))
        .safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Wordmark()
            Spacer(Modifier.weight(1f))
            Pill("MOBILE STUDIO", Amber)
        }
        Spacer(Modifier.height(32.dp))
        Eyebrow("Big ideas. Short cuts.", Amber)
        Text("Make it\nworth watching.", style = MaterialTheme.typography.headlineLarge, modifier = Modifier.padding(top = 12.dp))
        Text("Your footage. Your rhythm.\nA little studio that goes everywhere.", color = Muted,
            modifier = Modifier.padding(top = 14.dp, bottom = 24.dp))
        Surface(shape = RoundedCornerShape(26.dp), color = Panel, border = BorderStroke(1.dp, Edge)) {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(false to "Sign in", true to "Create account").forEach { (value, label) ->
                        FilterChip(selected = signup == value, onClick = { signup = value; message = "" },
                            enabled = !busy, label = { Text(label) }, modifier = Modifier.weight(1f))
                    }
                }
                Text(if (signup) "Start your next idea." else "Good to see you.", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(email, { email = it }, label = { Text("Email address") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email), enabled = !busy,
                    shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth())
                OutlinedTextField(password, { password = it }, label = { Text("Password") }, singleLine = true,
                    visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), enabled = !busy,
                    trailingIcon = { IconAction(if (visible) "Hide password" else "Show password", if (visible) Icons.Rounded.VisibilityOff else Icons.Rounded.Visibility) { visible = !visible } },
                    shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth())
                if (signup) Text("Use at least 6 characters.", color = Muted, fontSize = 12.sp)
                if (message.isNotEmpty()) Text(message, color = if (success) Mint else MaterialTheme.colorScheme.error, fontSize = 13.sp)
                PrimaryAction(if (busy) "Please wait…" else if (signup) "Create account" else "Let's go",
                    Icons.AutoMirrored.Rounded.ArrowForward, enabled = !busy && auth.configured) {
                    if (!Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) {
                        success = false; message = "Enter a valid email address."
                    } else if (password.length < 6) {
                        success = false; message = "Your password needs at least 6 characters."
                    } else scope.launch {
                        busy = true; message = ""; success = false
                        try {
                            if (signup) auth.signUp(email, password) else auth.signIn(email, password)
                            if (auth.signedIn()) onContinue()
                            else { success = true; message = "Check your inbox to confirm your email, then sign in." }
                        } catch (_: Exception) { message = "Couldn’t sign in. Check your details and connection, then try again." }
                        finally { busy = false }
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    HorizontalDivider(Modifier.weight(1f), color = Edge)
                    Text("or", color = Muted, fontSize = 12.sp)
                    HorizontalDivider(Modifier.weight(1f), color = Edge)
                }
                OutlinedButton(onClick = { scope.launch {
                    busy = true
                    try { auth.google() } catch (_: Exception) { success = false; message = "Google couldn’t open. Please try again." }
                    finally { busy = false }
                } }, enabled = !busy && auth.configured, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) {
                    Text("G", fontWeight = FontWeight.Bold, color = Ink)
                    Spacer(Modifier.width(12.dp)); Text("Continue with Google", color = Ink)
                }
            }
        }
        TextButton(onContinue, enabled = !busy, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
            Text("Try the editor without an account", color = Amber)
        }
        Text("Local drafts and exports are free. Use your CLPZ account for plans and credits.",
            color = Muted, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            listOf("Privacy" to "/privacy", "Terms" to "/terms").forEach { (label, path) ->
                TextButton({ context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.WEBSITE_URL + path))) }) {
                    Text(label, color = Muted, fontSize = 12.sp)
                }
            }
        }
    }
}
