package com.clpz.mobile

import android.content.Intent
import io.github.jan.supabase.auth.Auth
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.auth.providers.Google
import io.github.jan.supabase.auth.providers.builtin.Email
import io.github.jan.supabase.auth.handleDeeplinks
import io.github.jan.supabase.createSupabaseClient

class AuthRepository {
    val configured=BuildConfig.SUPABASE_URL.isNotBlank()&&BuildConfig.SUPABASE_ANON_KEY.isNotBlank()
    private val client by lazy { createSupabaseClient(BuildConfig.SUPABASE_URL,BuildConfig.SUPABASE_ANON_KEY){install(Auth){scheme="clpz";host="auth"}} }
    fun signedIn()=configured&&client.auth.currentSessionOrNull()!=null
    suspend fun signIn(email:String,password:String){client.auth.signInWith(Email){this.email=email;this.password=password}}
    suspend fun signUp(email:String,password:String){client.auth.signUpWith(Email){this.email=email;this.password=password}}
    suspend fun google()=client.auth.signInWith(Google)
    suspend fun signOut()=client.auth.signOut()
    fun handleDeepLink(intent:Intent)=client.handleDeeplinks(intent)
}
