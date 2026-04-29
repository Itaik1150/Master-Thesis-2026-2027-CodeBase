# Lexi — Cloud Deployment Guide

> **Goal:** Deploy the Lexi web app to public URLs so the Android APK works from any network (edu WiFi, home, mobile data) and your supervisor can use the app without any local setup.

## What gets deployed where

| Component | Service | Cost | Notes |
|-----------|---------|------|-------|
| React client (`Lexi/client/`) | **Vercel** | Free | Auto-deploys on every GitHub push |
| Node.js server (`Lexi/server/`) | **Render** | Free | ⚠️ Spins down after 15 min inactivity → ~40s cold start on first request. Acceptable for pilot/thesis stage. |
| MongoDB | Atlas | Already live ✅ | Nothing to do |
| Python engine | Your laptop | Free | Runs locally, connects to cloud services |
| Firebase FCM | Google | Free tier ✅ | Nothing to do |

### ⚠️ About Render's free tier cold start

When nobody has used the app for 15+ minutes, the server goes to sleep. The next request wakes it up — this takes ~40 seconds. After that, everything is fast again.

**Workaround (optional):** Sign up for [UptimeRobot](https://uptimerobot.com) (free) and add a monitor that pings your Render server URL every 10 minutes. This keeps it awake at no cost.

---

## Before you start — collect these values

You'll need to paste these into deployment dashboards. Gather them now:

From `logic-python/.env`:
- `MONGODB_URL` (the `mongodb+srv://...` string)

From `Lexi/server/.env` (or wherever the server reads its env):
- `MONGODB_URL`
- `JWT_SECRET_KEY`
- `OPENAI_API_KEY`
- `FRONTEND_URL` (will be your new Vercel URL — set after step 1)

From `Lexi/client/.env` (or `.env.local`):
- `REACT_APP_API_URL` = `https://lexi-server-1rx9.onrender.com`
- `REACT_APP_FRONTEND_URL` = `https://master-thesis-2026-2027-code-base.vercel.app`

---

## Step 1 — Deploy React client to Vercel

### 1.1 Create a Vercel account
Go to [vercel.com](https://vercel.com) → sign in with GitHub.

### 1.2 Import the repository
1. Click **Add New → Project**
2. Select your GitHub repo (`Master-Thesis-2026-2027-CodeBase`)
3. Vercel will scan the repo — it may auto-detect the wrong folder. **Set manually:**
   - **Root Directory:** `Lexi/client`
   - **Framework Preset:** Create React App
   - **Build Command:** `npm run build`
   - **Output Directory:** `build`

### 1.3 Set environment variables in Vercel
Before clicking Deploy, go to **Environment Variables** and add:

```
REACT_APP_API_URL        = https://lexi-server-1rx9.onrender.com
REACT_APP_FRONTEND_URL   = https://master-thesis-2026-2027-code-base.vercel.app
CI                       = false
```

### 1.4 Deploy
Click **Deploy**. Vercel will build and deploy.

> ✅ **Done — Vercel is live at:**
> ### `https://master-thesis-2026-2027-code-base.vercel.app`
>
> Vercel gives you three URLs after deployment — use only the **first one** (shortest, no random suffix). The others are per-branch and per-deployment previews that change on every push.
>
> | URL | When to use |
> |-----|-------------|
> | `master-thesis-2026-2027-code-base.vercel.app` | ✅ Always — this is the stable production URL |
> | `...-git-main-...vercel.app` | Branch preview — ignore |
> | `...-5rjl30urv-...vercel.app` | One-time deployment preview — ignore |
>
> **✅ Render is live at:** `https://lexi-server-1rx9.onrender.com`
> Remember to go to Vercel → Settings → Environment Variables and set `REACT_APP_API_URL` to this URL, then redeploy.

---

## Step 2 — Deploy Node.js server to Render

### 2.1 Create a Render account
Go to [render.com](https://render.com) → sign in with GitHub.

### 2.2 Create a new Web Service
1. Click **New → Web Service**
2. Select your GitHub repo (`Master-Thesis-2026-2027-CodeBase`)
3. Fill in the settings:
   - **Name:** `lexi-server` (or anything you like)
   - **Region:** pick the closest to you
   - **Root Directory:** `Lexi/server`
   - **Runtime:** Node
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm start`
   - **Instance Type:** Free

### 2.3 Set environment variables in Render
Scroll down to **Environment Variables** on the same page and add:

```
MONGODB_URL      = mongodb+srv://itaik1150_db_user:<PASSWORD>@cluster0.6xv1izi.mongodb.net
                   ⚠️ URL must end at the hostname — NO trailing slash, NO ?appName=... params.
                      The code appends /LexiDB itself. If you include ?appName=Cluster0 the DB name breaks.
MONGODB_DB_NAME  = test
MONGODB_USER     = itaik1150_db_user
MONGODB_PASSWORD = <your Atlas password>
JWT_SECRET_KEY   = (same value you use locally)
OPENAI_API_KEY   = (same value you use locally)
FRONTEND_URL     = https://master-thesis-2026-2027-code-base.vercel.app
NODE_ENV         = production
```

> **Note:** Render automatically assigns a PORT — do not set it manually.

> **Important — CORS:** Once you have both URLs, update `Lexi/server/src/server.ts` to add the Vercel URL to the `corsOptions.origin` array, commit, and push. Render will auto-redeploy.

### 2.4 Deploy
Click **Create Web Service**. Render will build and deploy (~3-5 min).

> ✅ **Render server is live at:** `https://lexi-server-1rx9.onrender.com`

---

## Step 3 — Wire everything together

### 3.1 Update Vercel env vars
Go to Vercel → your project → **Settings → Environment Variables** and set:

```
REACT_APP_API_URL      = https://lexi-server-1rx9.onrender.com
REACT_APP_FRONTEND_URL = https://master-thesis-2026-2027-code-base.vercel.app
CI                     = false
```

Then trigger a redeploy: **Deployments → (latest deployment) → Redeploy**.

### 3.2 Update CORS in server.ts
Open `Lexi/server/src/server.ts`. Add your Vercel URL to the CORS origins:

```typescript
origin: [
    process.env.FRONTEND_URL || 'http://localhost:3000',
    'https://master-thesis-2026-2027-code-base.vercel.app',   // ← add this
    'http://10.0.2.2:3000',              // keep for emulator dev
],
```

Commit and push — Render will auto-redeploy.

### 3.3 Test in browser
Open `https://master-thesis-2026-2027-code-base.vercel.app/e/69e397f15daf7d1e1d399827` in your phone's browser.
- The experiment page should load ✅
- Try registering → user should appear in MongoDB Atlas ✅

---

## Step 4 — Rebuild the APK with production URL

### 4.1 Update `android-app/app/build.gradle.kts`

Change the `EXPERIMENT_URL` to your Vercel URL:

```kotlin
buildConfigField(
    "String", "EXPERIMENT_URL",
    "\"https://master-thesis-2026-2027-code-base.vercel.app/e/69e397f15daf7d1e1d399827\""
)
```

### 4.2 Update `android-app/app/src/main/res/xml/network_security_config.xml`

The production URL uses HTTPS — you can **remove** the local IP domain entries (no longer needed).
The `<base-config cleartextTrafficPermitted="false" />` is already the safe default for HTTPS.

Actually, simplest change: just leave the file as-is. HTTPS works without any special config.

### 4.3 Rebuild and install
In Android Studio: **Build → Build Bundle(s)/APK(s) → Build APK(s)**

Install the new APK on your phone and on your supervisor's phone.

---

## Step 5 — Update Python engine (optional for now)

The Python engine connects directly to MongoDB Atlas and Firebase — both already cloud. No changes needed for the proactive notifications to keep working.

If you add Phase 5 (deep-link to conversation), the Python engine will need to call the Lexi server. At that point, update `logic-python/.env`:

```
LEXI_SERVER_URL = https://lexi-server-1rx9.onrender.com
```

---

## After deployment — working from any network

| Scenario | What to do |
|----------|-----------|
| Different WiFi | Nothing — app uses public URLs |
| Phone on mobile data | Nothing — app uses public URLs |
| Edu WiFi | Nothing — app uses public URLs |
| Share APK with supervisor | Send the `.apk` file — they install and use directly |
| Code change to client | Push to GitHub → Vercel auto-redeploys |
| Code change to server | Push to GitHub → Render auto-redeploys |
| Run proactive scheduler | `python scheduler.py` from your laptop (any network) |

---

## Troubleshooting

**"Network error" in the app after deployment**
- Check Vercel env var `REACT_APP_API_URL` points to the Render URL
- Check Render env var `FRONTEND_URL` points to the Vercel URL
- Check CORS in `server.ts` includes the Vercel URL
- Open Render logs: your service → **Logs** tab

**Render build fails**
- Check Root Directory is set to `Lexi/server`
- Check build command is `npm install && npm run build`
- Check all env vars are set (missing `MONGODB_URL` will crash on start)

**Server takes 40 seconds to respond (cold start)**
- This is normal on Render's free tier after 15 min of inactivity
- Optional fix: add a free UptimeRobot monitor pinging your Render URL every 10 min

**Vercel build fails**
- Check Root Directory is set to `Lexi/client`
- Check `REACT_APP_API_URL` is set (can be a placeholder for now)
- Check build command is `npm run build`

**App loads but login fails**
- Check `JWT_SECRET_KEY` is set in Render
- Check MongoDB Atlas Network Access allows `0.0.0.0/0` (all IPs) — Render IPs change

> **MongoDB Atlas IP whitelist:** Go to Atlas → Network Access → Add IP Address → Allow access from anywhere (`0.0.0.0/0`). This is required because Render servers have dynamic IPs.
