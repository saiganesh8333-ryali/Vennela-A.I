package com.vennela.ai

import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.Manifest
import android.content.Intent
import android.provider.Settings
import android.os.Bundle
import androidx.core.net.toUri
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.launch
import java.util.UUID
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.Scope
import androidx.activity.compose.rememberLauncherForActivityResult
import android.util.Log
import android.os.Build
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.Date

import com.vennela.ai.security.SecureTokenManager

val NeonVoidBlack = Color(0xFF000105)
val deepNeonBlue = Color(0xFF0012FF)
val brightNeonBlue = Color(0xFF0099FF)
val holographicWhite = Color(0xFFE0F7FA)

private val FuturisticNeonColorScheme = darkColorScheme(
    primary = brightNeonBlue,
    secondary = deepNeonBlue,
    background = NeonVoidBlack,
    surface = Color(0xFF010309),
    onBackground = holographicWhite,
    onSurface = brightNeonBlue
)

data class ChatMessage(
    val id: String = "",
    val role: String, // "user" or "assistant"
    val content: String = "",
    val timestamp: Long = System.currentTimeMillis()
)

class MainActivity : ComponentActivity() {
    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val recordAudioGranted = permissions[Manifest.permission.RECORD_AUDIO] ?: false
        if (!recordAudioGranted) {
            android.widget.Toast.makeText(this, "Microphone permission is required for Voice Mode", android.widget.Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Initialize secure token manager and sync AgentConfig
        SecureTokenManager.init(applicationContext)

        requestPermissionLauncher.launch(
            arrayOf(
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.POST_NOTIFICATIONS
            )
        )

        // Start Vennela Core Background Service
        val intent = Intent(this, VennelaBackgroundService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        enableEdgeToEdge()
        setContent {
            MaterialTheme(colorScheme = FuturisticNeonColorScheme) {
                MainContent()
            }
        }
    }
}

@Composable
fun MainContent(viewModel: VennelaViewModel = viewModel()) {
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    var currentScreen by remember { mutableStateOf("chat") }
    
    val isReasoningMode by viewModel.isReasoningMode.collectAsState()
    val isVoiceMode by viewModel.isVoiceModeActive.collectAsState()
    val isLiveActive by viewModel.isLiveConversationActive.collectAsState()
    val vennelaState by viewModel.vennelaState.collectAsState()
    val audioAmp by viewModel.volumeLevel.collectAsState()
    val speechAmp by viewModel.speechAmplitude.collectAsState()
    
    val conversations = viewModel.conversations
    val currentConvId by viewModel.currentConversationId.collectAsState()

    Box(modifier = Modifier.fillMaxSize()) {
        ModalNavigationDrawer(
            drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet(
                    modifier = Modifier.width(300.dp),
                    drawerContainerColor = Color(0xFF050B16),
                    drawerContentColor = Color.White
                ) {
                    Spacer(modifier = Modifier.height(48.dp))
                    Text(
                        "VENNELA CORE",
                        modifier = Modifier.padding(horizontal = 24.dp),
                        style = MaterialTheme.typography.headlineSmall,
                        color = brightNeonBlue,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 2.sp
                    )
                    
                    Spacer(modifier = Modifier.height(24.dp))
                    
                    NavigationDrawerItem(
                        label = { Text("New Conversation", fontWeight = FontWeight.Bold) },
                        selected = currentConvId == null,
                        onClick = {
                            viewModel.startNewSession()
                            currentScreen = "chat"
                            scope.launch { drawerState.close() }
                        },
                        icon = { Icon(Icons.Default.Add, contentDescription = null) },
                        modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding),
                        colors = NavigationDrawerItemDefaults.colors(
                            unselectedContainerColor = Color.Transparent, 
                            selectedContainerColor = brightNeonBlue.copy(alpha = 0.1f),
                            unselectedTextColor = Color.White, 
                            selectedTextColor = brightNeonBlue,
                            unselectedIconColor = brightNeonBlue
                        )
                    )

                    Divider(modifier = Modifier.padding(vertical = 12.dp, horizontal = 24.dp), color = Color.White.copy(alpha = 0.1f))

                    Text(
                        "RECENT LOGS",
                        modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.4f)
                    )

                    LazyColumn(modifier = Modifier.weight(1f)) {
                        items(conversations) { conv ->
                            NavigationDrawerItem(
                                label = { 
                                    Text(
                                        conv.title, 
                                        maxLines = 1, 
                                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                    ) 
                                },
                                selected = currentConvId == conv.id,
                                onClick = {
                                    viewModel.loadConversation(conv.id)
                                    currentScreen = "chat"
                                    scope.launch { drawerState.close() }
                                },
                                modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding),
                                colors = NavigationDrawerItemDefaults.colors(
                                    unselectedContainerColor = Color.Transparent, 
                                    selectedContainerColor = brightNeonBlue.copy(alpha = 0.1f),
                                    unselectedTextColor = Color.White.copy(alpha = 0.7f), 
                                    selectedTextColor = brightNeonBlue
                                )
                            )
                        }
                    }

                    Divider(modifier = Modifier.padding(vertical = 12.dp, horizontal = 24.dp), color = Color.White.copy(alpha = 0.1f))

                    NavigationDrawerItem(
                        label = { Text(if (isVoiceMode) "Voice Mode Active" else "Enable Voice Mode") },
                        selected = isVoiceMode,
                        onClick = {
                            viewModel.toggleVoiceMode()
                            scope.launch { drawerState.close() }
                        },
                        icon = { Icon(Icons.Default.Mic, contentDescription = null) },
                        modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding),
                        colors = NavigationDrawerItemDefaults.colors(unselectedContainerColor = Color.Transparent, unselectedTextColor = Color.White, unselectedIconColor = brightNeonBlue)
                    )

                    NavigationDrawerItem(
                        label = { Text("Neural Settings") },
                        selected = currentScreen == "settings",
                        onClick = {
                            currentScreen = "settings"
                            scope.launch { drawerState.close() }
                        },
                        icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                        modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding),
                        colors = NavigationDrawerItemDefaults.colors(unselectedContainerColor = Color.Transparent, unselectedTextColor = Color.White, unselectedIconColor = brightNeonBlue)
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                }
            }
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
            ) {
                if (!isVoiceMode) {
                    NightSkyBackground()
                    
                    Column(modifier = Modifier.fillMaxSize()) {
                        HeaderBar(
                            isReasoningMode = isReasoningMode,
                            onToggleMode = { viewModel.toggleReasoningMode() },
                            onNewChat = { viewModel.startNewSession() },
                            onSettingsClick = { currentScreen = if (currentScreen == "settings") "chat" else "settings" },
                            onMenuClick = { scope.launch { drawerState.open() } },
                            isLiveActive = isLiveActive,
                            onToggleLive = { viewModel.toggleLiveConversation() }
                        )
                        
                        Crossfade(targetState = currentScreen, label = "screen_transition", modifier = Modifier.weight(1f)) { screen ->
                            when (screen) {
                                "chat" -> ChatScreen(viewModel)
                                "settings" -> SettingsScreen(viewModel)
                            }
                        }
                    }
                } else {
                    VennelaVoiceModeUI(
                        state = vennelaState,
                        audioAmplitude = audioAmp / 100f,
                        speechAmplitude = speechAmp
                    )
                    
                    IconButton(
                        onClick = { viewModel.toggleVoiceMode() },
                        modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 80.dp).size(64.dp)
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "Exit", tint = Color.White, modifier = Modifier.size(32.dp))
                    }
                }
            }
        }
    }
}

@Composable
fun ChatScreen(viewModel: VennelaViewModel) {
    val messages = viewModel.messages
    val isThinking by viewModel.isThinking.collectAsState()
    val thoughts by viewModel.currentThoughts.collectAsState()
    val partialSpeech by viewModel.partialSpeech.collectAsState()
    val suggestions = viewModel.proactiveSuggestions
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(16.dp),
                contentPadding = PaddingValues(top = 20.dp, bottom = 40.dp)
            ) {
                items(messages, key = { it.timestamp.toString() + it.role }) { msg ->
                    NeonChatBubble(msg)
                }
                
                if (partialSpeech.isNotEmpty()) {
                    item {
                        Text(
                            text = partialSpeech,
                            color = Color.White.copy(alpha = 0.4f),
                            fontSize = 14.sp,
                            fontStyle = androidx.compose.ui.text.font.FontStyle.Italic,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                }

                if (isThinking) {
                    item {
                        VennelaThinkingIndicator(thoughts)
                    }
                }
            }
            
            if (messages.isEmpty() && !isThinking) {
                VennelaWelcomeUI()
            }
        }

        // Proactive Suggestions
        if (suggestions.isNotEmpty() && !isThinking) {
            LazyRow(
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(suggestions) { suggestion ->
                    Surface(
                        modifier = Modifier.clickable { viewModel.sendMessage(suggestion) },
                        color = brightNeonBlue.copy(alpha = 0.1f),
                        shape = RoundedCornerShape(20.dp),
                        border = BorderStroke(1.dp, brightNeonBlue.copy(alpha = 0.3f))
                    ) {
                        Text(
                            suggestion,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                            color = brightNeonBlue,
                            fontSize = 13.sp
                        )
                    }
                }
            }
        }

        var inputText by remember { mutableStateOf(TextFieldValue("")) }
        NeonInputCapsule(
            value = inputText,
            onValueChange = { 
                inputText = it 
                viewModel.updateListeningState(it.text.isNotEmpty())
            },
            onSend = {
                val text = inputText.text
                if (text.isNotBlank()) {
                    viewModel.sendMessage(text)
                    inputText = TextFieldValue("")
                }
            }
        )
    }
}

@Composable
fun VennelaThinkingIndicator(thoughts: String?) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(20.dp),
            color = brightNeonBlue,
            strokeWidth = 2.dp
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = thoughts ?: "Vennela is thinking...",
            color = Color.White.copy(alpha = 0.6f),
            fontSize = 14.sp,
            fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
        )
    }
}

@Composable
fun VennelaWelcomeUI() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.alpha(0.5f)
    ) {
        Icon(
            Icons.Default.AutoAwesome, 
            contentDescription = null, 
            tint = brightNeonBlue, 
            modifier = Modifier.size(64.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            "How can I assist your objective today?",
            color = Color.White,
            fontSize = 18.sp,
            fontWeight = FontWeight.Light
        )
    }
}

@Composable
fun SettingsScreen(viewModel: VennelaViewModel) {
    val context = LocalContext.current
    
    val gso = remember {
        GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestScopes(Scope("https://www.googleapis.com/auth/gmail.readonly"))
            .build()
    }
    val googleSignInClient: GoogleSignInClient = remember { GoogleSignIn.getClient(context, gso) }
    
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
        try {
            val account = task.getResult(com.google.android.gms.common.api.ApiException::class.java)
            Log.d("VennelaAI", "Signed in as: ${account?.email}")
        } catch (e: Exception) {
            Log.e("VennelaAI", "Sign-in failed", e)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(32.dp))
            .border(1.dp, brightNeonBlue.copy(alpha = 0.2f), RoundedCornerShape(32.dp))
            .padding(24.dp)
    ) {
        SettingItem(
            title = "CORE SETTINGS",
            subtitle = "",
            icon = Icons.Default.Settings,
            onClick = {}
        )
        Spacer(modifier = Modifier.height(32.dp))

        SettingItem(
            title = "Connect Google Account",
            subtitle = "Enable Gmail reading & AI analysis",
            icon = Icons.Default.AccountCircle,
            onClick = {
                launcher.launch(googleSignInClient.signInIntent)
            }
        )
        
        SettingItem(
            title = "Default AI Assistant",
            subtitle = "Set Vennela as your primary digital assistant",
            icon = Icons.Default.AutoAwesome,
            onClick = {
                val intent = Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
                context.startActivity(intent)
            }
        )
        
        SettingItem(
            title = "Voice Session",
            subtitle = "Initialize background voice core",
            icon = Icons.Default.MicNone,
            onClick = {
                val intent = Intent(context, VennelaBackgroundService::class.java)
                intent.action = "START_VOICE_SESSION"
                context.startForegroundService(intent)
            }
        )

        SettingItem(
            title = "STT Engine (Whisper)",
            subtitle = "Using High Performance Local Whisper.cpp",
            icon = Icons.Default.GraphicEq,
            onClick = {}
        )

        SettingItem(
            title = "Overlay Permission",
            subtitle = "Enable visual feedback over other apps",
            icon = Icons.Default.Layers,
            onClick = {
                val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, "package:${context.packageName}".toUri())
                context.startActivity(intent)
            }
        )

        Spacer(modifier = Modifier.height(32.dp))
        Text("DIAGNOSTICS", color = brightNeonBlue, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Button(
                onClick = { 
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    }
                    context.startActivity(intent)
                },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = brightNeonBlue.copy(alpha = 0.2f))
            ) {
                Text("Test STT", color = Color.White)
            }
            
            Button(
                onClick = { 
                    // This will trigger a test speak via the viewmodel
                    viewModel.sendMessage("Test speech. This is Vennela's premium natural female voice.")
                },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = brightNeonBlue.copy(alpha = 0.2f))
            ) {
                Text("Test TTS", color = Color.White)
            }
        }
        
        Spacer(modifier = Modifier.weight(1f))
        
        Text(
            "Vennela AI v1.2 | Ultra Performance Mode",
            modifier = Modifier.align(Alignment.CenterHorizontally).alpha(0.4f),
            color = Color.White,
            fontSize = 12.sp
        )
    }
}

@Composable
fun SettingItem(title: String, subtitle: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .padding(vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, tint = brightNeonBlue, modifier = Modifier.size(28.dp))
        Spacer(modifier = Modifier.width(20.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Color.White.copy(alpha = 0.5f), fontSize = 13.sp)
        }
        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = Color.White.copy(alpha = 0.2f))
    }
}

@Composable
fun NeonChatBubble(msg: ChatMessage) {
    val isUser = msg.role == "user"
    val alignment = if (isUser) Alignment.End else Alignment.Start
    
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalAlignment = alignment) {
        Surface(
            modifier = Modifier.widthIn(max = 300.dp),
            color = if (isUser) brightNeonBlue.copy(alpha = 0.1f) else Color.White.copy(alpha = 0.05f),
            shape = RoundedCornerShape(
                topStart = 20.dp, 
                topEnd = 20.dp, 
                bottomStart = if (isUser) 20.dp else 4.dp, 
                bottomEnd = if (isUser) 4.dp else 20.dp
            ),
            border = BorderStroke(1.dp, if (isUser) brightNeonBlue.copy(alpha = 0.3f) else Color.White.copy(alpha = 0.1f))
        ) {
            Column(modifier = Modifier.padding(14.dp)) {
                Text(
                    text = msg.content,
                    color = holographicWhite,
                    fontSize = 15.sp,
                    lineHeight = 22.sp
                )
                
                Spacer(modifier = Modifier.height(4.dp))
                
                Text(
                    text = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date(msg.timestamp)),
                    color = Color.White.copy(alpha = 0.3f),
                    fontSize = 10.sp,
                    modifier = Modifier.align(Alignment.End)
                )
            }
        }
    }
}

@Composable
fun NeonInputCapsule(value: TextFieldValue, onValueChange: (TextFieldValue) -> Unit, onSend: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 24.dp)
            .height(60.dp)
            .background(Color.White.copy(alpha = 0.05f), RoundedCornerShape(30.dp))
            .border(1.dp, brightNeonBlue.copy(alpha = 0.2f), RoundedCornerShape(30.dp))
            .padding(horizontal = 20.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        TextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.weight(1f),
            placeholder = { Text("Communicate with Vennela...", color = Color.White.copy(alpha = 0.2f), fontSize = 14.sp) },
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Color.Transparent,
                unfocusedContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                cursorColor = brightNeonBlue,
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White
            )
        )
        IconButton(onClick = onSend, modifier = Modifier.size(48.dp)) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null, tint = brightNeonBlue, modifier = Modifier.size(24.dp))
        }
    }
}
