# Lexi Proactive Platform — Technical Documentation

> **Last updated:** June 4, 2026  
> Companion docs: [`README.md`](README.md), [`PLAN.md`](PLAN.md), [`PROACTIVE_NOTIFICATIONS.md`](PROACTIVE_NOTIFICATIONS.md), [`DEPLOYMENT.md`](DEPLOYMENT.md)

---

## 1. Overview

End-to-end system for running proactive conversation experiments:

- **Lexi** — experiment management, chat UI, admin dashboard  
- **Android app** — WebView participant client with FCM and deep links  
- **Python engine** — scheduled proactive cycles, heuristics, LLM personalization, push delivery  

All components share **MongoDB Atlas** and **Firebase Cloud Messaging**.

---

## 2. Architecture

```
┌──────────────────┐     HTTPS      ┌──────────────────┐
│  Android APK     │ ──────────────▶│  React (Vercel)  │
│  WebView + FCM   │                  │  Lexi/client     │
└────────┬─────────┘                  └────────┬─────────┘
         │ FCM token (JS bridge)              │ REST
         ▼                                    ▼
┌────────────────────────────────────────────────────────┐
│  Node.js API (Render) — Lexi/server                   │
│  Auth, users, experiments, conversations, /join        │
└────────┬───────────────────────────────┬───────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌─────────────────────────┐
│  MongoDB Atlas  │◀───────────│  Python scheduler       │
│  users, logs,   │  pymongo   │  logic-python/          │
│  conversations  │            │  (same Render instance) │
└─────────────────┘            └───────────┬─────────────┘
                                           │ FCM Admin SDK
                                           ▼
                                 ┌─────────────────┐
                                 │  Firebase FCM   │
                                 └─────────────────┘
```

**Render single-instance model:** `scripts/render-start.sh` runs the Node server in the foreground and `python -u scheduler.py` in the background.

---

## 3. Components

### 3.1 Android (`android-app/`)

| File | Role |
|------|------|
| `MainActivity.kt` | WebView, cached experiment URL, deep link handling, third-party cookies |
| `AndroidBridge.kt` | `window.Android` — FCM token, `setCurrentUserId` |
| `LexiMessagingService.kt` | FCM receive, high-priority notification, deep-link intent |
| `app/build.gradle.kts` | `versionCode`, join flow cache invalidation |

Participants open the experiment via **join link** → generic APK → IP-based session match (`apk_sessions`).

### 3.2 Lexi client (`Lexi/client/`)

| Area | Role |
|------|------|
| `src/app/App.tsx` | Routes: admin, `/e/:experimentId`, conversation, login |
| `src/services/fcmBridge.ts` | Sync FCM token after login |
| `ProactiveSettingsModal.tsx` | Proactive toggle, heuristics, LLM model, join link |
| `ProtectedExperimentRoute.tsx` | Auth guard + `returnTo` redirect |
| `FinishConversationDialog.tsx` | End chat + return home |

### 3.3 Lexi server (`Lexi/server/`)

| Area | Role |
|------|------|
| `usersController` | Register, login, 30-day cookie, FCM token, proactive prompt expiry on session |
| `experimentsController` | CRUD, proactive settings, bulk `isProactive` sync |
| `conversationsController` | Chat, stream, finish, **proactive opener reset on user message** |
| `joinController` | Landing page session + `match-session` for deferred deep link |

**Representative endpoints**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/users/create` | Register (+ optional `fcmToken`) |
| POST | `/users/login` | Login |
| POST | `/users/fcm-token` | Update device token |
| GET | `/users/user` | Active user + cookie refresh |
| POST | `/conversations/create` | New conversation (used by Python pre-create) |
| POST | `/conversations/message` | Send message |
| GET | `/conversations/message/stream` | SSE assistant reply |
| GET | `/conversations/conversation` | Load conversation |
| POST | `/conversations/finish` | End conversation (+ opener reset) |
| GET | `/join/:experimentId` | Participant onboarding page |
| GET | `/join/match-session` | APK IP → experiment URL |

### 3.4 Python engine (`logic-python/`)

| File | Role |
|------|------|
| `scheduler.py` | Cron jobs (`FIRE_TIMES`), calls `run_full_proactive_cycle()` |
| `run_cycle.py` | Single manual cycle (dev / smoke test) |
| `services/research_service.py` | Orchestration, memory, inject, FCM, logging |
| `services/llm_service.py` | OpenAI / Anthropic, extraction, personalization |
| `services/fcm_service.py` | Firebase send; credentials from env or `/etc/secrets/firebase.json` |
| `heuristics/*.py` | Temporal, affective, behavioural gap |
| `utils/mongodb_client.py` | Atlas connection |

---

## 4. MongoDB collections (main)

| Collection | Purpose |
|------------|---------|
| `users` | Participants, `agent`, `fcmToken`, `isProactive`, `proactiveMemory` |
| `experiments` | Config, `experimentFeatures.proactiveSettings` |
| `conversations` | Messages |
| `metadata_conversations` | Conversation metadata, `userId`, `isFinished` |
| `proactive_logs` | Per-send audit (`trigger_source`, message, status) |
| `apk_sessions` | Deferred deep-link IP matching |

---

## 5. Proactive settings schema (experiment)

```json
{
  "experimentFeatures": {
    "proactiveSettings": {
      "enabled": true,
      "frequency": 30,
      "heuristics": {
        "temporal": true,
        "affective": true,
        "behaviouralGap": true
      },
      "llmModel": "gpt-4o"
    }
  }
}
```

See [`PROACTIVE_NOTIFICATIONS.md`](PROACTIVE_NOTIFICATIONS.md) for which fields are enforced in Python vs UI-only.

---

## 6. Environment variables

### Lexi server (`Lexi/server/.env`)

| Variable | Description |
|----------|-------------|
| `MONGODB_URL` | Atlas connection string |
| `MONGODB_DB_NAME` | Database name |
| `JWT_SECRET_KEY` | Auth cookie signing |
| `PORT` | Listen port (Render sets `10000`) |
| `FRONTEND_URL` | CORS + redirects |
| `OPENAI_API_KEY` | In-chat LLM (if used server-side) |

### Lexi client

| Variable | Description |
|----------|-------------|
| `REACT_APP_API_URL` | Node API base URL |

### Python (`logic-python/.env` — local; mirror on Render)

| Variable | Description |
|----------|-------------|
| `MONGODB_URL` | Atlas |
| `MONGODB_DB_NAME` | e.g. `test` |
| `MONGODB_USERS_COLLECTION` | e.g. `users` |
| `OPENAI_API_KEY` | LLM |
| `LLM_PROVIDER` / `LLM_MODEL` | Default model |
| `ANTHROPIC_API_KEY` | If using Claude |
| `SERVICE_ACCOUNT_JSON` | Local path to Firebase JSON |
| `SERVICE_ACCOUNT_JSON_CONTENT` | Full JSON string (alternative) |
| `LEXI_SERVER_URL` | Node API for `POST /conversations/create` |
| `FRONTEND_BASE_URL` | Deep links in FCM |
| `DAILY_MESSAGE_LIMIT` | Per-user daily cap |
| `PROMPT_EXPIRY_HOURS` | Opener reset timer (default 2) |
| `AFFECTIVE_DELAY_HOURS` | Affective follow-up delay (omit in prod) |

**Render:** prefer Secret File `firebase.json` mounted at `/etc/secrets/firebase.json`.

---

## 7. Security notes

- Do not commit `.env` or `*-firebase-adminsdk*.json` (see `.gitignore`).  
- Rotate keys if they ever appeared in public git history.  
- Production traffic should use HTTPS only (Vercel + Render).  
- Participant auth: HTTP-only cookie, 30-day `maxAge`.

---

## 8. Operations checklist

| Task | How |
|------|-----|
| Deploy code | `git push` → Vercel + Render auto-build |
| Change notification times | `scheduler.py` `FIRE_TIMES` → push |
| Run one cycle manually | `python logic-python/run_cycle.py` |
| View sends | MongoDB `proactive_logs` |
| Debug participant opener | `users.agent.firstChatSentence`, `proactiveMemory` |

---

*For deployment steps and Render configuration, see [`DEPLOYMENT.md`](DEPLOYMENT.md).*
