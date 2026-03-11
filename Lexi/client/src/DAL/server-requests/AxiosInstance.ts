import axios from 'axios';

// Detect if running in Android emulator
const isAndroidEmulator = () => {
    return typeof window !== 'undefined' && (
        window.location.hostname === '10.0.2.2' ||
        window.location.hostname.includes('android') ||
        navigator.userAgent.includes('Android')
    );
};

// Use different base URLs for browser vs emulator
const baseURL = isAndroidEmulator()
    ? 'http://10.0.2.2:5000' // Android emulator
    : 'http://localhost:5000'; // Browser development

console.log('🔧 Axios baseURL:', baseURL);

const axiosInstance = axios.create({
    baseURL: process.env.REACT_APP_API_URL || baseURL,
    withCredentials: true,
});

export default axiosInstance;
