package com.vennela.ai

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.*
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.*
import kotlin.random.Random

@Composable
fun HeaderBar(
    isReasoningMode: Boolean,
    onToggleMode: () -> Unit,
    onNewChat: () -> Unit,
    onSettingsClick: () -> Unit,
    onMenuClick: () -> Unit,
    isLiveActive: Boolean,
    onToggleLive: () -> Unit
) {
    val neonBlue = Color(0xFF0099FF)
    val primaryColor = if (isReasoningMode) Color(0xFF9B72F3) else neonBlue
    val activeColor = Color(0xFF00FFFF)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = 24.dp, vertical = 20.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        IconButton(onClick = onMenuClick) {
            Icon(Icons.Default.Menu, contentDescription = "Menu", tint = primaryColor, modifier = Modifier.size(28.dp))
        }

        Spacer(modifier = Modifier.weight(1f))
        
        Text(
            text = if (isReasoningMode) "DEEP THINKING" else "VENNELA AI",
            style = TextStyle(
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = 4.sp,
                shadow = Shadow(color = primaryColor.copy(alpha = 0.7f), blurRadius = 15f)
            ),
            modifier = Modifier
                .alpha(0.95f)
                .clickable { onToggleMode() }
        )
        
        Spacer(modifier = Modifier.weight(1f))

        IconButton(onClick = onToggleLive) {
            Icon(
                if (isLiveActive) Icons.Default.Mic else Icons.Default.MicNone,
                contentDescription = "Live Conversation",
                tint = if (isLiveActive) activeColor else primaryColor,
                modifier = Modifier.size(28.dp)
            )
        }

        IconButton(onClick = onSettingsClick) {
            Icon(Icons.Default.Settings, contentDescription = "Settings", tint = primaryColor, modifier = Modifier.size(28.dp))
        }
    }
}

@Composable
fun NightSkyBackground() {
    val starData = remember {
        List(400) {
            Triple(Random.nextFloat(), Random.nextFloat(), Random.nextFloat() * 0.7f + 0.3f)
        }
    }

    val infiniteTransition = rememberInfiniteTransition(label = "stars_anim")
    val twinkle by infiniteTransition.animateFloat(
        initialValue = 0.2f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(3000, easing = LinearOutSlowInEasing), RepeatMode.Reverse),
        label = "twinkle"
    )

    Canvas(modifier = Modifier.fillMaxSize()) {
        drawRect(Brush.verticalGradient(colors = listOf(Color(0xFF000000), Color(0xFF000208), Color(0xFF000510))))
        
        drawCircle(
            brush = Brush.radialGradient(
                0f to Color(0xFF001A33).copy(alpha = 0.2f),
                1f to Color.Transparent,
                center = Offset(size.width * 0.5f, size.height * 0.5f)
            ),
            radius = size.width * 1.2f
        )
        
        starData.forEachIndexed { i, star ->
            val alpha = if (i % 6 == 0) twinkle * star.third else star.third
            drawCircle(
                color = Color.White,
                radius = if (i % 50 == 0) 1.5.dp.toPx() else 0.6.dp.toPx(),
                center = Offset(star.first * size.width, star.second * size.height),
                alpha = alpha
            )
        }
    }
}

@Composable
fun RotatingMoon(modifier: Modifier = Modifier) {
    val infiniteTransition = rememberInfiniteTransition(label = "moon_rotation")
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(20000, easing = LinearEasing)), label = "rotation"
    )

    Box(
        modifier = modifier
            .size(280.dp)
            .shadow(120.dp, CircleShape, spotColor = Color(0xFFFFF9C4).copy(alpha = 0.4f))
            .clip(CircleShape)
            .background(
                Brush.radialGradient(
                    0.0f to Color(0xFFFFFDE7),
                    0.85f to Color(0xFFFFF9C4),
                    1.0f to Color(0xFFFBC02D).copy(alpha = 0.8f)
                )
            )
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val radius = size.minDimension / 2
            val center = Offset(size.width / 2, size.height / 2)

            for (i in 0..60) {
                val craterSeed = Random(i.toLong())
                val basePhi = craterSeed.nextFloat() * 2 * PI.toFloat()
                val baseTheta = craterSeed.nextFloat() * PI.toFloat()
                val currentPhi = basePhi + (rotation * 2 * PI.toFloat())
                
                val z = radius * sin(baseTheta) * cos(currentPhi)
                val x = radius * sin(baseTheta) * sin(currentPhi)
                val y = radius * cos(baseTheta)

                if (z > 0) {
                    val visibility = z / radius
                    val craterRadius = (2 + (i % 8)).dp.toPx() * (0.8f + 0.4f * visibility)
                    
                    drawCircle(
                        color = Color(0xFF8D6E63).copy(alpha = 0.15f * visibility),
                        radius = craterRadius,
                        center = Offset(center.x + x, center.y + y)
                    )
                    
                    drawCircle(
                        color = Color.White.copy(alpha = 0.15f * visibility),
                        radius = craterRadius * 0.9f,
                        center = Offset(center.x + x - 1.dp.toPx(), center.y + y - 1.dp.toPx())
                    )
                }
            }

            drawCircle(
                brush = Brush.radialGradient(
                    0.65f to Color.Transparent,
                    1.0f to Color.Black.copy(alpha = 0.45f),
                    center = Offset(size.width * 0.35f, size.height * 0.35f)
                ),
                radius = radius
            )
            
            drawCircle(
                brush = Brush.radialGradient(
                    0.9f to Color.Transparent,
                    1.0f to Color.White.copy(alpha = 0.15f)
                ),
                radius = radius
            )
        }
    }
}
