# Lexi Project - Complete End-to-End FCM Integration

## 🎯 Project Overview
This project establishes a full communication loop between Android app, Node.js server, and Python logic using MongoDB as a shared database for proactive notifications.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Android App   │───▶│  React Client  │───▶│  Node.js Server │
│  (WebView)     │    │   (Forms)      │    │   (Express)    │
│                 │    │                 │    │                 │
│  FCM Token      │    │  User Data      │    │  MongoDB Atlas   │
│  Capture        │    │  Registration   │    │  (LexiDB)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
         │                        │                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Python Logic   │◀───│ MongoDB Client   │◀───│  Firebase FCM     │
│  (Proactive)    │    │  (pymongo)      │    │  (Admin SDK)    │
│                 │    │                 │    │                 │
│  User Query      │    │  Real-time Data  │    │  Push Notifications│
│  & Analysis      │    │  Retrieval      │    │  to Devices      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
Master Thesis 2026-2027 CodeBase/
├── android-app/                    # Android WebView app
│   └── app/src/main/java/com/example/lexiparticipant/
│       ├── MainActivity.kt          # WebView setup
│       └── AndroidBridge.kt          # FCM token bridge
├── Lexi/                          # Web application
│   ├── client/                     # React frontend
│   │   ├── src/
│   │   │   ├── components/forms/
│   │   │   │   ├── RegisterForm.tsx    # User registration
│   │   │   │   └── LoginForm.tsx        # User login
│   │   │   ├── services/
│   │   │   │   └── fcmBridge.ts       # FCM token handling
│   │   │   ├── hooks/
│   │   │   │   └── useActiveUser.ts   # User state management
│   │   │   └── DAL/server-requests/
│   │   │       └── users.ts             # API calls
│   │   └── .env.emulator              # Android emulator config
│   └── server/                     # Node.js backend
│       ├── src/
│       │   ├── controllers/
│       │   │   └── usersController.controller.ts  # User management
│       │   ├── services/
│       │   │   └── users.service.ts              # Database operations
│       │   ├── models/
│       │   │   └── UsersModel.ts               # MongoDB schema
│       │   ├── routers/
│       │   │   └── usersRouter.router.ts         # API routes
│       │   ├── mongoDBProvider.ts           # MongoDB connection
│       │   └── server.ts                  # Express server
│       └── .env                         # Environment variables
└── logic-python/                    # Python proactive logic
    ├── core/
    │   ├── models.py                # Data models
    │   └── data_loader.py           # MongoDB integration
    ├── services/
    │   └── fcm_service.py          # Firebase FCM
    ├── utils/
    │   └── mongodb_client.py        # MongoDB client
    ├── .env                         # Environment variables
    ├── requirements.txt              # Dependencies
    └── send_test_push.py          # Test script
```

## 🔧 Key Components

### 1. Android App (`android-app/`)
- **MainActivity.kt**: WebView container loading React app
- **AndroidBridge.kt**: JavaScript interface for FCM token retrieval
- **FCM Service**: Background service for token generation

### 2. React Frontend (`Lexi/client/`)
- **Registration/Login Forms**: Capture user data and FCM tokens
- **FCM Bridge**: Communication between WebView and Android
- **API Integration**: Send tokens to Node.js backend

### 3. Node.js Server (`Lexi/server/`)
- **Express API**: RESTful endpoints for user management
- **MongoDB Integration**: Store users with FCM tokens
- **CORS Configuration**: Support for Android emulator

### 4. Python Logic (`logic-python/`)
- **MongoDB Client**: Real-time data retrieval from Atlas
- **FCM Service**: Firebase Admin SDK for push notifications
- **Decision Engine**: Proactive notification logic

## 🔄 Data Flow

### Registration Flow:
1. **User registers** in React app → Android captures FCM token
2. **Token sent** to Node.js API → Stored in MongoDB Atlas
3. **Python queries** MongoDB → Retrieves user with FCM token
4. **Firebase sends** push notification → Android device receives

### Proactive Notifications:
1. **Python analyzes** user data and context
2. **Decision engine** determines when to send notifications
3. **FCM service** delivers personalized messages
4. **Android app** displays proactive notifications

## 🛠️ Technologies Used

### Frontend:
- **React**: User interface and forms
- **TypeScript**: Type safety and development
- **Android WebView**: Native app container

### Backend:
- **Node.js**: Express server and API
- **MongoDB Atlas**: Cloud database storage
- **Mongoose**: MongoDB object modeling

### Python Logic:
- **Python 3.12**: Core logic implementation
- **pymongo**: MongoDB driver for database access
- **Firebase Admin SDK**: Push notification service
- **python-dotenv**: Environment variable management

## 🚀 Deployment & Configuration

### Environment Variables:
```bash
# MongoDB Atlas
MONGODB_URL=mongodb+srv://itaik1150_db_user:7wYGyhm2vNl3aeay@cluster0.ls6m7wa.mongodb.net/?appName=Cluster0
MONGODB_DB_NAME=LexiDB
MONGODB_USERS_COLLECTION=users

# Firebase
SERVICE_ACCOUNT_JSON=services/lexi-72330-firebase-adminsdk-fbsvc-49c2c6ee82.json

# Development
FRONTEND_URL=http://localhost:3000
PORT=5000
```

### Android Emulator Setup:
```bash
# Port forwarding for emulator communication
adb reverse tcp:5000 tcp:5000
adb reverse tcp:3000 tcp:3000
```

## 🧪 Testing & Verification

### Test Scripts:
1. **`send_test_push.py`**: End-to-end FCM notification testing
2. **`test_auth.py`**: MongoDB connection verification
3. **Manual Testing**: Android emulator registration flow

### Success Metrics:
- ✅ **MongoDB Connection**: Atlas database accessible
- ✅ **User Registration**: Data persistence working
- ✅ **FCM Token Capture**: Android bridge functional
- ✅ **Push Notifications**: Firebase delivery confirmed
- ✅ **End-to-End Flow**: Complete communication loop

## 🎯 Thesis Achievement

This project successfully demonstrates:
- **Cross-platform integration** (Android, Web, Python)
- **Real-time communication** (FCM push notifications)
- **Cloud database synchronization** (MongoDB Atlas)
- **Proactive system architecture** (Decision engine + notifications)
- **Full development lifecycle** (Frontend → Backend → Logic → User)

## 📝️ Future Enhancements

1. **Enhanced Decision Logic**: ML-based notification timing
2. **User Analytics**: Engagement metrics and optimization
3. **Multi-device Support**: Tablet and phone compatibility
4. **Offline Capabilities**: Local caching and sync
5. **Security Hardening**: Token encryption and validation

---

**Project Status: ✅ COMPLETE - Full End-to-End FCM Integration Working!**

*Generated: March 1, 2026*
*Last Updated: Successful FCM notification delivery confirmed*
