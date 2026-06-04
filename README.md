# Lexi — Proactive Conversational Agents (Master Thesis 2026–2027)

Research platform for studying **proactive AI-initiated conversations**: the system schedules when to contact participants, sends push notifications, and opens personalized chat openers — integrated with a full experiment management stack.

Based on [Lexi](https://github.com/Tomer-Lavan/Lexi) (Tomer Lavan), extended for proactive experiments, heuristics, Android distribution, and cloud deployment.

---

## What the system does

| Role | Experience |
|------|------------|
| **Researcher** | Creates experiments in the admin dashboard, enables proactive mode, configures heuristics and LLM model, shares a join link, exports data |
| **Participant** | Installs the Android app, registers, receives proactive notifications, taps to open the right conversation, chats with the agent |

**Proactive engine** (Python): three research heuristics — **Temporal**, **Affective**, **Behavioural Gap** — plus topic fallback; memory-aware Hebrew/English messages; Firebase push; opener injection and deep linking.

---

## Repository layout

```
├── Lexi/
│   ├── client/          React — participant UI + admin dashboard (Vercel)
│   └── server/          Node.js Express API (Render)
├── logic-python/        Proactive scheduler, heuristics, LLM, FCM
├── android-app/         WebView shell + FCM + deferred deep linking
├── scripts/             Render build/start (Node + Python on one instance)
├── PLAN.md              Roadmap & completed work summary
├── PLAN_BACKLOG.md      Remaining tasks by importance
├── PROACTIVE_NOTIFICATIONS.md   Proactive pipeline spec (start here for nudge work)
├── PROJECT_DOCUMENTATION.md     Architecture & API reference
├── DEPLOYMENT.md        Production setup
└── AI_GUIDELINES.md     Rules for AI-assisted development
```

---

## Production URLs (current)

| Component | URL |
|-----------|-----|
| Web app | https://master-thesis-2026-2027-code-base.vercel.app |
| API | https://lexi-server-1rx9.onrender.com |
| API + scheduler | Same Render service (Starter) |

MongoDB Atlas and Firebase FCM are shared across Node and Python.

---

## Quick start (local)

**Prerequisites:** Node 18+, Python 3.12+, MongoDB Atlas URI, OpenAI key, Firebase service account JSON (local file path in `.env`).

```bash
# 1. API
cd Lexi/server
npm install
cp .env.example .env   # fill MONGODB_URL, JWT_SECRET_KEY, etc.
npm run dev            # :5000

# 2. Client
cd Lexi/client
npm install
# set REACT_APP_API_URL=http://localhost:5000
npm start              # :3000

# 3. One proactive cycle (manual test)
cd logic-python
pip install -r requirements.txt
cp .env.example .env   # MONGODB_URL, OPENAI_API_KEY, SERVICE_ACCOUNT_JSON path, LEXI_SERVER_URL
python run_cycle.py

# 4. Android — open android-app/ in Android Studio, set EXPERIMENT_URL in build.gradle.kts
```

**Production deploy:** see [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Documentation index

| Document | Read when… |
|----------|------------|
| [`PROACTIVE_NOTIFICATIONS.md`](PROACTIVE_NOTIFICATIONS.md) | Improving notifications, understanding the full nudge pipeline |
| [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) | Architecture, collections, env vars, key endpoints |
| [`PLAN.md`](PLAN.md) | What phases are done vs open |
| [`PLAN_BACKLOG.md`](PLAN_BACKLOG.md) | Prioritized future work |
| [`AI_GUIDELINES.md`](AI_GUIDELINES.md) | Working with Cursor / AI on this repo |

---

## License & attribution

Lexi web platform: original work by Tomer Lavan. Thesis extensions: proactive engine, heuristics, Android integration, and deployment tooling in this repository.
