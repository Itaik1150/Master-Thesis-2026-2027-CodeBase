/**
 * FCM Bridge Service
 * 
 * This service bridges the Android WebView FCM token with the Node.js backend.
 * It's called after user authentication to pair the FCM token with the user ID.
 */

declare global {
  interface Window {
    Android?: {
      getFCMToken: () => string;
      isTokenAvailable: () => boolean;
      getDeviceInfo: () => string;
    };
  }
}

export const setupFCMBridge = async (): Promise<void> => {
  try {
    // Check if running inside Android WebView
    if (!window.Android) {
      console.log('FCM Bridge: Not running in Android WebView');
      return;
    }

    // Get current FCM token
    const currentToken = await getCurrentFCMToken();
    
    if (!currentToken) {
      console.warn('FCM Bridge: No FCM token available');
      return;
    }

    console.log('FCM Bridge: Token retrieved successfully', currentToken.substring(0, 20) + '...');

    // Import dynamically to avoid circular dependencies
    const { updateFCMToken } = await import('../DAL/server-requests/users');
    
    // Send token to backend
    await updateFCMToken(currentToken);
    
    console.log('FCM Bridge: Token synced with backend successfully');
    
    // Set up token refresh listener (if available)
    setupTokenRefreshListener();
    
  } catch (error) {
    console.error('FCM Bridge: Failed to setup FCM bridge', error);
  }
};

/**
 * Get current FCM token with retry mechanism
 */
export const getCurrentFCMToken = async (): Promise<string | null> => {
  try {
    if (!window.Android) {
      return null;
    }

    // Check if FCM token is available
    if (!window.Android.isTokenAvailable()) {
      console.warn('FCM Bridge: No FCM token available');
      return null;
    }

    // Get FCM token from Android
    const fcmToken = window.Android.getFCMToken();
    
    if (!fcmToken || fcmToken.trim() === '') {
      console.warn('FCM Bridge: Empty FCM token received');
      return null;
    }

    return fcmToken;
  } catch (error) {
    console.error('FCM Bridge: Error getting token', error);
    return null;
  }
};

/**
 * Set up token refresh listener (placeholder for future Firebase implementation)
 */
export const setupTokenRefreshListener = (): void => {
  // This would be used if we had Firebase JS SDK in the WebView
  // For now, we'll rely on periodic token checks
  console.log('FCM Bridge: Token refresh listener setup (placeholder)');
  
  // Periodic token sync every 5 minutes
  setInterval(async () => {
    try {
      const currentToken = await getCurrentFCMToken();
      if (currentToken) {
        const { updateFCMToken } = await import('../DAL/server-requests/users');
        await updateFCMToken(currentToken);
        console.log('FCM Bridge: Periodic token sync completed');
      }
    } catch (error) {
      console.warn('FCM Bridge: Periodic token sync failed', error);
    }
  }, 5 * 60 * 1000); // 5 minutes
};

/**
 * Check if the app is running in Android WebView
 */
export const isAndroidWebView = (): boolean => {
  return typeof window !== 'undefined' && window.Android !== undefined;
};

/**
 * Get FCM token if available
 */
export const getFCMToken = (): string | null => {
  if (!isAndroidWebView() || !window.Android) {
    return null;
  }
  
  try {
    const token = window.Android.getFCMToken();
    return token && token.trim() !== '' ? token : null;
  } catch (error) {
    console.error('FCM Bridge: Error getting token', error);
    return null;
  }
};

/**
 * Get device info for debugging
 */
export const getDeviceInfo = (): string | null => {
  if (!isAndroidWebView() || !window.Android) {
    return null;
  }
  
  try {
    return window.Android.getDeviceInfo();
  } catch (error) {
    console.error('FCM Bridge: Error getting device info', error);
    return null;
  }
};
