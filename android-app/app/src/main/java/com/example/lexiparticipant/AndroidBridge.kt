package com.example.lexiparticipant

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import android.webkit.JavascriptInterface
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class AndroidBridge(private val context: Context) {

    private val sharedPreferences: SharedPreferences = context.getSharedPreferences("lexi", Context.MODE_PRIVATE)
    private val serverUrl = "http://10.0.2.2:5000"

    @JavascriptInterface
    fun getFCMToken(): String {
        val token = sharedPreferences.getString("fcmToken", "") ?: ""
        Log.d("AndroidBridge", "Retrieved FCM token: ${token.take(20)}...")
        return token
    }

    @JavascriptInterface
    fun setCurrentUserId(userId: String) {
        sharedPreferences.edit().putString("userId", userId).apply()
        Log.d("AndroidBridge", "User ID saved: $userId")
    }

    @JavascriptInterface
    fun getCurrentUserId(): String {
        return sharedPreferences.getString("userId", "") ?: ""
    }

    @JavascriptInterface
    fun sendTokenToServer(userId: String, fcmToken: String) {
        Log.d("AndroidBridge", "Sending token to server - User: $userId, Token: ${fcmToken.take(20)}...")
        
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val result = postTokenToServer(userId, fcmToken)
                withContext(Dispatchers.Main) {
                    Log.d("AndroidBridge", "Token transmission result: $result")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Log.e("AndroidBridge", "Failed to send token: ${e.message}")
                }
            }
        }
    }

    @JavascriptInterface
    fun initializeTokenTransmission() {
        val fcmToken = getFCMToken()
        val userId = getCurrentUserId()
        
        if (fcmToken.isNotEmpty()) {
            sendTokenToServer(userId, fcmToken)
        } else {
            Log.w("AndroidBridge", "No FCM token available for transmission")
        }
    }

    private suspend fun postTokenToServer(userId: String, fcmToken: String): String {
        return withContext(Dispatchers.IO) {
            val url = URL("$serverUrl/users/fcm-token")
            val connection = url.openConnection() as HttpURLConnection
            
            try {
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                
                val jsonPayload = JSONObject().apply {
                    put("userId", userId)
                    put("fcmToken", fcmToken)
                }
                
                // Send request
                val outputStream = connection.outputStream
                val writer = OutputStreamWriter(outputStream, "UTF-8")
                writer.write(jsonPayload.toString())
                writer.flush()
                writer.close()
                outputStream.close()
                
                // Get response
                val responseCode = connection.responseCode
                val responseMessage = connection.responseMessage
                
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    "Success: $responseMessage"
                } else {
                    "Error: $responseCode $responseMessage"
                }
                
            } catch (e: Exception) {
                throw e
            } finally {
                connection.disconnect()
            }
        }
    }

    @JavascriptInterface
    fun isTokenAvailable(): Boolean {
        val token = sharedPreferences.getString("fcmToken", "") ?: ""
        return token.isNotEmpty()
    }

    @JavascriptInterface
    fun getDeviceInfo(): String {
        return JSONObject().apply {
            put("manufacturer", android.os.Build.MANUFACTURER)
            put("model", android.os.Build.MODEL)
            put("version", android.os.Build.VERSION.RELEASE)
            put("sdk", android.os.Build.VERSION.SDK_INT)
        }.toString()
    }
    
    @JavascriptInterface
    fun setOpenedFromNotification(value: Boolean) {
        sharedPreferences.edit().putBoolean("openedFromNotification", value).apply()
        Log.d("AndroidBridge", "Set openedFromNotification: $value")
    }
    
    @JavascriptInterface
    fun wasOpenedFromNotification(): Boolean {
        val wasOpened = sharedPreferences.getBoolean("openedFromNotification", false)
        // Clear the flag after reading so it doesn't persist
        if (wasOpened) {
            sharedPreferences.edit().putBoolean("openedFromNotification", false).apply()
        }
        Log.d("AndroidBridge", "Was opened from notification: $wasOpened")
        return wasOpened
    }
}
