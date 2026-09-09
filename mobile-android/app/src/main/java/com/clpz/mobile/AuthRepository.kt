package com.clpz.mobile

import android.content.Intent
import io.github.jan.supabase.auth.Auth
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.auth.handleDeeplinks
import io.github.jan.supabase.auth.providers.Google
import io.github.jan.supabase.auth.providers.builtin.Email
import io.github.jan.supabase.auth.status.SessionStatus
import io.github.jan.supabase.createSupabaseClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class AuthRepository {
    val configured = BuildConfig.SUPABASE_URL.isNotBlank() && BuildConfig.SUPABASE_ANON_KEY.isNotBlank()
    private val client by lazy {
        createSupabaseClient(BuildConfig.SUPABASE_URL, BuildConfig.SUPABASE_ANON_KEY) {
            install(Auth) { scheme = "clpz"; host = "auth" }
        }
    }
    val sessionStatus: StateFlow<SessionStatus>
        get() = if (configured) client.auth.sessionStatus else MutableStateFlow(SessionStatus.NotAuthenticated(false))
    fun email(): String? = if (configured) client.auth.currentUserOrNull()?.email else null
    fun signedIn() = configured && client.auth.currentSessionOrNull() != null
    suspend fun signIn(email: String, password: String) {
        client.auth.signInWith(Email) { this.email = email.trim(); this.password = password }
    }
    suspend fun signUp(email: String, password: String) {
        client.auth.signUpWith(Email) { this.email = email.trim(); this.password = password }
    }
    suspend fun google() = client.auth.signInWith(Google)
    suspend fun signOut() = client.auth.signOut()
    fun handleDeepLink(intent: Intent) = client.handleDeeplinks(intent)
}
