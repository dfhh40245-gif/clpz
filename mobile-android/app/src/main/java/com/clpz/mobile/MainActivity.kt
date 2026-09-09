package com.clpz.mobile

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.jan.supabase.auth.status.SessionStatus

class MainActivity : ComponentActivity() {
    private val auth = AuthRepository()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (auth.configured) auth.handleDeepLink(intent)
        setContent { ClpzTheme { ClpzApp(auth) } }
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (auth.configured) auth.handleDeepLink(intent)
    }
}

@Composable
fun ClpzApp(auth: AuthRepository) {
    val session by auth.sessionStatus.collectAsStateWithLifecycle()
    var guest by rememberSaveable { mutableStateOf(false) }
    val signedIn = session is SessionStatus.Authenticated
    if (!signedIn && !guest) AuthScreen(auth, onContinue = { guest = true })
    else StudioScreen(auth, signedIn, onSignIn = { guest = false })
}
