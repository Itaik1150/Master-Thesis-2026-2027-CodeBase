package com.example.lexiparticipant

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class LexiMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        Log.d("FCM", "New token: $token")
        val prefs = getSharedPreferences("lexi", MODE_PRIVATE)
        prefs.edit().putString("fcmToken", token).apply()
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val title = message.notification?.title ?: message.data["title"] ?: "Lexi"
        val body  = message.notification?.body  ?: message.data["body"]  ?: "Tap to open chat"

        showNotification(title, body)
    }

    private fun showNotification(title: String, body: String) {
        // lexi_nudges_v2: IMPORTANCE_HIGH channel.
        // A new channel ID is required because Android locks in a channel's
        // importance once created — the old lexi_nudges (IMPORTANCE_DEFAULT)
        // cannot be upgraded in-place on a device that already has it.
        val channelId = "lexi_nudges_v2"

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }

        // Use a unique request code per nudge so each PendingIntent is distinct
        // and notifications don't silently replace each other.
        val requestCode = (System.currentTimeMillis() % Int.MAX_VALUE).toInt()
        val immutableFlag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
            PendingIntent.FLAG_IMMUTABLE else 0

        val pendingIntent = PendingIntent.getActivity(
            this,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or immutableFlag
        )

        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Lexi Nudges",
                NotificationManager.IMPORTANCE_HIGH   // heads-up banner + sound + vibration
            ).apply {
                description = "Proactive conversation starters from Lexi"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 400, 200, 400)
            }
            manager.createNotificationChannel(channel)
        }

        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.mipmap.faviconh)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))  // expand long messages
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)   // pre-Oreo heads-up fallback
            .setSound(soundUri)
            .setVibrate(longArrayOf(0, 400, 200, 400))
            .setContentIntent(pendingIntent)
            .setFullScreenIntent(pendingIntent, true)        // wake screen + show over lock screen
            .build()

        // Unique notification ID ensures each nudge appears as a separate entry
        // rather than silently updating the previous one.
        val notificationId = (System.currentTimeMillis() % Int.MAX_VALUE).toInt()
        manager.notify(notificationId, notification)
    }
}
