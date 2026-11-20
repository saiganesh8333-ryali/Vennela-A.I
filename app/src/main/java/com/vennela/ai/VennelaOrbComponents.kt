package com.vennela.ai

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.unit.dp

enum class VennelaState {
    IDLE,
    CONNECTING,
    LISTENING,
    PROCESSING,
    SPEAKING,
    DISCONNECTED,
    ERROR
}

// Vennela Original Deep Blue Palette
private val VennelaBlackBlue = Color(0xFF050B16)
private val VennelaDeepBlue = Color(0xFF0B192C)
private val VennelaSpaceBlue = Color(0xFF102A43)
private val VennelaNavy = Color(0xFF000080)
private val VennelaElectricBlue = Color(0xFF00BFFF)
private val VennelaCyan = Color(0xFF00FFFF)

/**
 * Modifier that applies a subtle inward scale to the content when Vennela is active.
 * Target: 1.0f -> 0.96f
 */
fun Modifier.vennelaActivationScale(isActivated: Boolean): Modifier = this.composed {
    val scale by animateFloatAsState(
        targetValue = if (isActivated) 0.96f else 1.0f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioLowBouncy,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "content_scale"
    )
    this.scale(scale)
}

/**
 * Full-screen activation flash.
 * Deep-blue energy spreading from top-center.
 */
@Composable
fun VennelaFlashOverlay(
    isActivated: Boolean,
    modifier: Modifier = Modifier
) {
    var triggerFlash by remember { mutableStateOf(false) }
    
    LaunchedEffect(isActivated) {
        if (isActivated) {
            triggerFlash = true
        }
    }

    val flashAnim = remember { Animatable(0f) }
    
    LaunchedEffect(triggerFlash) {
        if (triggerFlash) {
            flashAnim.snapTo(0f)
            flashAnim.animateTo(
                targetValue = 1f,
                animationSpec = tween(durationMillis = 700, easing = LinearOutSlowInEasing)
            )
            triggerFlash = false
        }
    }

    val progress = flashAnim.value
    if (progress > 0f && progress < 1f) {
        // Flash timing: 0-0.3 fade in, 0.3-1.0 fade out
        val alpha = if (progress < 0.3f) {
            progress / 0.3f
        } else {
            1f - (progress - 0.3f) / 0.7f
        }
        
        Canvas(modifier = modifier.fillMaxSize()) {
            val centerTop = Offset(size.width / 2, 0f)
            
            // 1. Spreading Energy Gradient
            drawRect(
                brush = Brush.radialGradient(
                    0.0f to VennelaElectricBlue.copy(alpha = 0.5f * alpha),
                    0.4f to VennelaDeepBlue.copy(alpha = 0.3f * alpha),
                    1.0f to Color.Transparent,
                    center = centerTop,
                    radius = size.height * 1.8f * progress
                )
            )
            
            // 2. Subtle Edge Glow (Vignette)
            drawRect(
                brush = Brush.verticalGradient(
                    0.0f to VennelaNavy.copy(alpha = 0.4f * alpha),
                    0.25f to Color.Transparent
                )
            )
        }
    }
}

/**
 * Tiny futuristic AI presence indicator. (6-10dp core)
 */
@Composable
fun VennelaOrb(
    state: VennelaState,
    audioAmplitude: Float = 0f,
    speechAmplitude: Float = 0f,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "orb_infinite")
    
    val breatheScale by infiniteTransition.animateFloat(
        initialValue = 0.95f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(2500, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breathe"
    )

    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(4000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "rotation"
    )

    val animatedAudioAmp by animateFloatAsState(
        targetValue = audioAmplitude,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = Spring.StiffnessLow),
        label = "audio_amp"
    )
    
    val animatedSpeechAmp by animateFloatAsState(
        targetValue = speechAmplitude,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = Spring.StiffnessMediumLow),
        label = "speech_amp"
    )

    Canvas(modifier = modifier.size(36.dp)) {
        val center = Offset(size.width / 2, size.height / 2)
        val baseRadius = 8.dp.toPx() // Small Core
        
        val currentRadius = when (state) {
            VennelaState.IDLE, VennelaState.DISCONNECTED, VennelaState.ERROR -> baseRadius * breatheScale
            VennelaState.CONNECTING, VennelaState.PROCESSING -> baseRadius * 1.15f
            VennelaState.LISTENING -> baseRadius * (1f + animatedAudioAmp * 0.9f)
            VennelaState.SPEAKING -> baseRadius * (1f + animatedSpeechAmp * 0.85f)
        }

        // 1. Soft Ambient Glow
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(VennelaElectricBlue.copy(alpha = 0.35f), Color.Transparent),
                center = center,
                radius = currentRadius * 3.5f
            ),
            radius = currentRadius * 3.5f,
            center = center
        )

        // 2. The Core
        withTransform({
            if (state == VennelaState.PROCESSING || state == VennelaState.CONNECTING) {
                rotate(rotation, center)
            }
            if (state == VennelaState.SPEAKING || state == VennelaState.LISTENING) {
                val shift = (if (state == VennelaState.SPEAKING) animatedSpeechAmp else animatedAudioAmp) * 2.5f
                translate(shift, -shift)
            }
        }) {
            drawCircle(
                brush = Brush.linearGradient(
                    colors = listOf(VennelaBlackBlue, VennelaDeepBlue, VennelaNavy),
                    start = Offset(center.x - currentRadius, center.y - currentRadius),
                    end = Offset(center.x + currentRadius, center.y + currentRadius)
                ),
                radius = currentRadius,
                center = center
            )
            
            // Neon cyan rim for definition
            drawCircle(
                color = VennelaCyan.copy(alpha = 0.75f),
                radius = currentRadius,
                center = center,
                style = Stroke(width = 1.dp.toPx())
            )
        }

        // 3. Communications ripples
        if (state == VennelaState.SPEAKING || state == VennelaState.LISTENING) {
            val amp = if (state == VennelaState.SPEAKING) animatedSpeechAmp else animatedAudioAmp
            if (amp > 0.05f) {
                val rippleRadius = currentRadius * (1f + amp * 1.8f)
                drawCircle(
                    color = VennelaElectricBlue.copy(alpha = 0.4f * (1f - amp)),
                    radius = rippleRadius,
                    center = center,
                    style = Stroke(width = 0.8.dp.toPx())
                )
            }
        }
    }
}

/**
 * Unified application-level overlay.
 * Contains the flash energy and the persistent orb.
 */
@Composable
fun VennelaLiveOverlay(
    isActivated: Boolean,
    state: VennelaState,
    audioAmplitude: Float = 0f,
    speechAmplitude: Float = 0f,
    modifier: Modifier = Modifier
) {
    val alpha by animateFloatAsState(
        targetValue = if (isActivated) 1f else 0f,
        animationSpec = tween(600),
        label = "overlay_alpha"
    )
    
    val entranceScale by animateFloatAsState(
        targetValue = if (isActivated) 1f else 0.5f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioLowBouncy, 
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "entrance_scale"
    )

    Box(modifier = modifier.fillMaxSize()) {
        // Full-screen Flash activation effect
        VennelaFlashOverlay(isActivated = isActivated)

        // The AI Orb presence indicator
        if (alpha > 0.01f) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    // Respect system status bars if not hidden
                    .windowInsetsPadding(WindowInsets.statusBars)
                    .padding(top = 10.dp)
                    .graphicsLayer {
                        this.alpha = alpha
                        this.scaleX = entranceScale
                        this.scaleY = entranceScale
                    },
                contentAlignment = Alignment.TopCenter
            ) {
                VennelaOrb(
                    state = state,
                    audioAmplitude = audioAmplitude,
                    speechAmplitude = speechAmplitude
                )
            }
        }
    }
}
