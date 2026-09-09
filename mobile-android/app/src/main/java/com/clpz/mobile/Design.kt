package com.clpz.mobile

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Ink = Color(0xFFF6F2E9)
val Muted = Color(0xFFACA99F)
val Amber = Color(0xFFFFC369)
val Black = Color(0xFF0B0C0C)
val Panel = Color(0xFF171919)
val Edge = Color(0xFF303331)
val Mint = Color(0xFFAED2B5)

@Composable
fun ClpzTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(primary = Amber, onPrimary = Black,
            background = Black, onBackground = Ink, surface = Panel, onSurface = Ink,
            surfaceVariant = Color(0xFF252827), onSurfaceVariant = Muted,
            outline = Edge, secondary = Mint, error = Color(0xFFFFB4AB)),
        typography = Typography(
            headlineLarge = androidx.compose.ui.text.TextStyle(fontSize = 38.sp, lineHeight = 42.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-1.5).sp),
            headlineMedium = androidx.compose.ui.text.TextStyle(fontSize = 28.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-.7).sp),
            titleLarge = androidx.compose.ui.text.TextStyle(fontSize = 21.sp, lineHeight = 27.sp, fontWeight = FontWeight.SemiBold),
            bodyLarge = androidx.compose.ui.text.TextStyle(fontSize = 16.sp, lineHeight = 25.sp),
            bodyMedium = androidx.compose.ui.text.TextStyle(fontSize = 14.sp, lineHeight = 21.sp),
            labelLarge = androidx.compose.ui.text.TextStyle(fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
        )
    ) { Surface(Modifier.fillMaxSize(), color = Black, content = content) }
}

@Composable
fun Wordmark() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Surface(shape = RoundedCornerShape(10.dp), color = Amber) {
            Icon(Icons.Rounded.ContentCut, null, Modifier.padding(9.dp).size(20.dp), tint = Black)
        }
        Text("clpz", fontSize = 28.sp, fontWeight = FontWeight.Black, letterSpacing = (-1).sp)
    }
}

@Composable
fun Eyebrow(text: String, color: Color = Muted) {
    Text(text.uppercase(), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.8.sp, color = color)
}

@Composable
fun PrimaryAction(text: String, icon: ImageVector, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
        shape = RoundedCornerShape(18.dp), contentPadding = PaddingValues(18.dp)) {
        Icon(icon, null, Modifier.size(19.dp))
        Spacer(Modifier.width(10.dp))
        Text(text)
    }
}

@Composable
fun IconAction(label: String, icon: ImageVector, enabled: Boolean = true, onClick: () -> Unit) {
    IconButton(onClick, enabled = enabled, modifier = Modifier.size(48.dp)) {
        Icon(icon, label, tint = if (enabled) Ink else Muted.copy(alpha = .3f), modifier = Modifier.size(21.dp))
    }
}

@Composable
fun Pill(text: String, color: Color = Ink) {
    Surface(color = Black.copy(alpha = .78f), shape = CircleShape, border = BorderStroke(1.dp, Edge)) {
        Text(text, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = color,
            fontSize = 10.sp, fontWeight = FontWeight.Medium, fontFamily = FontFamily.Monospace)
    }
}

fun timeLabel(ms: Long): String {
    val seconds = ms.coerceAtLeast(0) / 1000
    return "%d:%02d".format(seconds / 60, seconds % 60)
}
