package com.vennela.ai

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Shadow

private val VennelaNeonBlue = Color(0xFF0099FF)
private val VennelaDeepBlue = Color(0xFF0B192C)
private val VennelaCyan = Color(0xFF00FFFF)
private val VennelaNavy = Color(0xFF000080)
private val VennelaElectricBlue = Color(0xFF00BFFF)

/**
 * Enhanced 3D Orb with multi-layered depths and energy waves.
 */
@Composable
fun Vennela3DOrb(
    amplitude: Float,
    state: VennelaState,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "orb_3d_pro")
    
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(10000, easing = LinearEasing)),
        label = "rotation"
    )

    val pulsingGlow by infiniteTransition.animateFloat(
        initialValue = 0.5f, targetValue = 1.0f,
        animationSpec = infiniteRepeatable(tween(2500, easing = EaseInOutSine), RepeatMode.Reverse),
        label = "glow"
    )

    val animatedAmp by animateFloatAsState(
        targetValue = amplitude,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = Spring.StiffnessLow),
        label = "orb_amp"
    )

    Canvas(modifier = modifier.size(140.dp)) {
        val center = Offset(size.width / 2, size.height / 2)
        val baseRadius = 35.dp.toPx()
        val currentRadius = baseRadius * (1f + animatedAmp * 0.6f)

        // 1. Atmosphere / Outer Energy
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(VennelaElectricBlue.copy(alpha = 0.25f * pulsingGlow), Color.Transparent),
                center = center,
                radius = currentRadius * 4.5f
            ),
            radius = currentRadius * 4.5f
        )

        // 2. Neon Energy Rim
        drawCircle(
            brush = Brush.sweepGradient(
                colors = listOf(VennelaCyan, VennelaNeonBlue, VennelaElectricBlue, VennelaCyan),
                center = center
            ),
            radius = currentRadius * 1.02f,
            style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round)
        )

        // 3. 3D Core Sphere
        withTransform({
            rotate(rotation, center)
            if (state == VennelaState.SPEAKING) {
                val s = 1.1f + animatedAmp * 0.2f
                scale(s, s, center)
            }
        }) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(VennelaNavy, VennelaDeepBlue, Color(0xFF010309)),
                    center = center,
                    radius = currentRadius
                ),
                radius = currentRadius
            )

            // Internal Energy Shells
            for (i in 0..4) {
                val shellAlpha = (0.2f + (i * 0.1f)) * pulsingGlow
                drawOval(
                    color = VennelaCyan.copy(alpha = shellAlpha),
                    topLeft = Offset(center.x - currentRadius, center.y - (currentRadius * 0.15f * i)),
                    size = Size(currentRadius * 2, (currentRadius * 0.4f)),
                    style = Stroke(width = 0.8.dp.toPx())
                )
            }
        }

        // 4. Specular Highlight (The Glass Look)
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(Color.White.copy(alpha = 0.4f), Color.Transparent),
                center = Offset(center.x - currentRadius * 0.4f, center.y - currentRadius * 0.4f),
                radius = currentRadius * 0.6f
            ),
            radius = currentRadius * 0.6f,
            center = Offset(center.x - currentRadius * 0.4f, center.y - currentRadius * 0.4f)
        )
    }
}

/**
 * Energy Field Edge animation that covers all screen edges.
 */
@Composable
fun VennelaEdgeGlow(
    amplitude: Float,
    state: VennelaState
) {
    val isActive = state != VennelaState.IDLE
    val infiniteTransition = rememberInfiniteTransition(label = "edge_pro")
    
    val phase by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(4000, easing = LinearEasing)),
        label = "phase"
    )

    val animatedAmp by animateFloatAsState(
        targetValue = amplitude,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = Spring.StiffnessMedium),
        label = "edge_amp"
    )

    if (isActive) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = (6.dp.toPx() + animatedAmp * 15f)
            val alpha = (0.4f + animatedAmp * 0.6f)

            val rectPath = Path().apply {
                moveTo(0f, 0f)
                lineTo(size.width, 0f)
                lineTo(size.width, size.height)
                lineTo(0f, size.height)
                close()
            }

            // High-depth edge glow layers
            drawPath(
                path = rectPath,
                brush = Brush.sweepGradient(
                    0.0f to VennelaNavy,
                    0.25f to VennelaNeonBlue,
                    0.5f to VennelaCyan,
                    0.75f to VennelaNeonBlue,
                    1.0f to VennelaNavy,
                    center = Offset(size.width / 2, size.height / 2)
                ),
                style = Stroke(width = strokeWidth * 2.2f, cap = StrokeCap.Round),
                alpha = 0.15f * alpha
            )

            drawPath(
                path = rectPath,
                color = VennelaNeonBlue.copy(alpha = 0.6f * alpha),
                style = Stroke(
                    width = strokeWidth,
                    pathEffect = PathEffect.dashPathEffect(
                        intervals = floatArrayOf(size.width / 2, size.width / 4),
                        phase = phase * size.width
                    )
                )
            )
            
            drawPath(
                path = rectPath,
                color = VennelaCyan.copy(alpha = 0.3f * alpha),
                style = Stroke(width = 1.dp.toPx())
            )
        }
    }
}

@Composable
fun VennelaVoiceModeUI(
    state: VennelaState,
    audioAmplitude: Float,
    speechAmplitude: Float
) {
    val currentAmp = if (state == VennelaState.SPEAKING) speechAmplitude else audioAmplitude
    
    Box(modifier = Modifier.fillMaxSize()) {
        // 1. Edge Glow
        VennelaEdgeGlow(amplitude = currentAmp, state = state)
        
        // 2. Activation Flash
        VennelaFlashOverlay(isActivated = state != VennelaState.IDLE)
        
        // 3. Center UI
        Column(
            modifier = Modifier.fillMaxSize().padding(top = 80.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Vennela3DOrb(amplitude = currentAmp, state = state)
            
            Spacer(modifier = Modifier.height(48.dp))
            
            // Subtitle state indicator
            val statusText = when(state) {
                VennelaState.CONNECTING -> "Connecting to Live Core..."
                VennelaState.LISTENING -> "Listening to Neural Input..."
                VennelaState.PROCESSING -> "Synchronizing Intelligence..."
                VennelaState.SPEAKING -> "Vennela Communicating..."
                VennelaState.DISCONNECTED -> "Disconnected"
                VennelaState.ERROR -> "Live Session Error"
                VennelaState.IDLE -> "Standby Mode"
            }
            
            androidx.compose.material3.Text(
                text = statusText.uppercase(),
                style = androidx.compose.ui.text.TextStyle(
                    color = VennelaCyan.copy(alpha = 0.7f),
                    fontSize = 12.sp,
                    letterSpacing = 4.sp,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                    shadow = Shadow(color = VennelaNeonBlue, blurRadius = 10f)
                )
            )
        }
    }
}
