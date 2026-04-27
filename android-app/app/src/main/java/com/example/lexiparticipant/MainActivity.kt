package com.example.lexiparticipant

import android.annotation.SuppressLint
import android.os.Bundle
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
import android.os.Build

import android.content.Context
import android.webkit.JavascriptInterface

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                AppRoot()
            }



        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)
        }

    }
}

@Composable
private fun AppRoot() {
    ChatScreen(url = BuildConfig.EXPERIMENT_URL)
}


@Composable
private fun SetupScreen(onContinue: (String) -> Unit) {
    var input by remember { mutableStateOf(TextFieldValue("")) }
    var error by remember { mutableStateOf<String?>(null) }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp),
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "Lexi Experiment",
                style = MaterialTheme.typography.headlineMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Paste participant link (for now) and continue. We’ll replace this with QR later.",
                style = MaterialTheme.typography.bodyMedium
            )
            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("Participant URL") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            if (error != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(text = error!!, color = MaterialTheme.colorScheme.error)
            }

            Spacer(modifier = Modifier.height(16.dp))

            Button(
                onClick = {
                    val url = input.text.trim()
                    if (url.isEmpty()) {
                        error = "Please enter a URL."
                        return@Button
                    }
                    // Minimal validation for now
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        error = "URL must start with http:// or https://"
                        return@Button
                    }
                    error = null
                    onContinue(url)
                },
                modifier = Modifier.fillMaxWidth()
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
                        android.view.ViewGroup.LayoutParams.MATCH_PARENT
                    )

                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                    
                    // Allow mixed content for HTTP in WebView
                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
                        settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                    }

                    webViewClient = object : WebViewClient() {
                        override fun onReceivedError(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                            error: android.webkit.WebResourceError?
                        ) {
                            super.onReceivedError(view, request, error)
                            android.util.Log.e("MY_DEBUG_TAG", "WebView Error: " + error?.description)
                        }
                    }
                    webChromeClient = WebChromeClient() 

                    addJavascriptInterface(AndroidBridge(context), "Android")
                    android.util.Log.d("MY_DEBUG_TAG", "Loading URL: " + url)
                    loadUrl(url)
                }
            }
        )
    }
}


