package com.example.lexiparticipant

import android.annotation.SuppressLint
import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private const val PREFS_NAME         = "lexi_prefs"
private const val KEY_EXPERIMENT_URL = "experiment_url"
private const val KEY_VERSION_CODE   = "version_code"

class MainActivity : ComponentActivity() {

    private val prefs: SharedPreferences by lazy {
        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)
        }

        // If a new APK version was installed, clear the cached experiment URL so
        // match-session runs again and picks up the correct experiment for this build.
        val currentVersion = BuildConfig.VERSION_CODE
        val storedVersion  = prefs.getInt(KEY_VERSION_CODE, -1)
        if (storedVersion != currentVersion) {
            prefs.edit()
                .remove(KEY_EXPERIMENT_URL)
                .putInt(KEY_VERSION_CODE, currentVersion)
                .apply()
        }

        val savedUrl = prefs.getString(KEY_EXPERIMENT_URL, null)

        if (savedUrl != null) {
            // Already matched on a previous launch — load directly.
            setContent { MaterialTheme { ChatScreen(url = savedUrl) } }
        } else {
            // First launch: show a loading screen while we attempt to match this
            // device's IP to a recent APK download session on the server.
            setContent { MaterialTheme { MatchingScreen() } }

            CoroutineScope(Dispatchers.IO).launch {
                val experimentUrl = tryMatchSession()
                withContext(Dispatchers.Main) {
                    if (experimentUrl != null) {
                        prefs.edit().putString(KEY_EXPERIMENT_URL, experimentUrl).apply()
                        setContent { MaterialTheme { ChatScreen(url = experimentUrl) } }
                    } else {
                        // No automatic match — fall back to the manual setup screen
                        // so the researcher / participant can paste the URL directly.
                        setContent {
                            MaterialTheme {
                                SetupScreen(onContinue = { url ->
                                    prefs.edit().putString(KEY_EXPERIMENT_URL, url).apply()
                                    setContent { MaterialTheme { ChatScreen(url = url) } }
                                })
                            }
                        }
                    }
                }
            }
        }
    }

    // Calls GET /experiments/match-session on the server.
    // Returns the full WebView URL if a match is found, null otherwise.
    // Retries once to handle Render's ~40s cold-start on the free tier.
    private fun tryMatchSession(): String? {
        repeat(2) { attempt ->
            try {
                val url = URL("${BuildConfig.SERVER_URL}/experiments/match-session")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "GET"
                // 45s covers Render's worst-case cold start (~40s).
                conn.connectTimeout = 45_000
                conn.readTimeout   = 45_000
                conn.setRequestProperty("Accept", "application/json")

                val code = conn.responseCode
                if (code == 200) {
                    val body = conn.inputStream.bufferedReader().readText()
                    val json = JSONObject(body)
                    val experimentId = json.optString("experimentId", "")
                    if (experimentId.isNotEmpty()) {
                        return "${BuildConfig.FRONTEND_BASE_URL}/e/$experimentId"
                    }
                    // Server responded but no match found — don't retry.
                    android.util.Log.w("Lexi", "match-session: no match (attempt ${attempt + 1})")
                    return null
                } else {
                    android.util.Log.w("Lexi", "match-session HTTP $code (attempt ${attempt + 1})")
                }
            } catch (e: Exception) {
                android.util.Log.e("Lexi", "match-session failed (attempt ${attempt + 1}): ${e.message}")
            }
        }
        return null
    }
}

// Shown while the app is trying to auto-detect the experiment.
@Composable
private fun MatchingScreen() {
    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Spacer(modifier = Modifier.height(20.dp))
            Text(
                text = "Connecting to experiment…",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "This may take up to 30 seconds on first launch.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

// Fallback: participant can paste a URL manually.
@Composable
private fun SetupScreen(onContinue: (String) -> Unit) {
    var input by remember { mutableStateOf(TextFieldValue("")) }
    var error by remember { mutableStateOf<String?>(null) }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(text = "Lexi Experiment", style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "Could not detect your experiment automatically. Please paste the participant link you received.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("Participant URL") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            if (error != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(text = error!!, color = MaterialTheme.colorScheme.error)
            }
            Spacer(modifier = Modifier.height(16.dp))
            Button(
                onClick = {
                    val url = input.text.trim()
                    if (url.isEmpty()) { error = "Please enter a URL."; return@Button }
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        error = "URL must start with http:// or https://"; return@Button
                    }
                    error = null
                    onContinue(url)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Continue")
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun ChatScreen(url: String) {
    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                WebView(context).apply {
                    layoutParams = android.view.ViewGroup.LayoutParams(
                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    )
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        settings.mixedContentMode =
                            android.webkit.WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                    }
                    webViewClient = object : WebViewClient() {
                        override fun onReceivedError(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                            error: android.webkit.WebResourceError?,
                        ) {
                            super.onReceivedError(view, request, error)
                            android.util.Log.e("Lexi", "WebView Error: ${error?.description}")
                        }
                    }
                    webChromeClient = WebChromeClient()
                    addJavascriptInterface(AndroidBridge(context), "Android")
                    android.util.Log.d("Lexi", "Loading URL: $url")
                    loadUrl(url)
                }
            },
        )
    }
}
