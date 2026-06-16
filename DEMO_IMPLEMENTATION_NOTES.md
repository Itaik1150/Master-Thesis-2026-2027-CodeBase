# Oxford Demo Implementation - Phase 2, Task 2

## Overview
This document tracks the implementation of the hardcoded 3-notification demo sequence for the EIF CogAI 2026 conference (June 25-26).

**Branch**: `oxford-demo`
**Status**: Complete ✅

---

## Changes Summary

### 1. Database Schema (TypeScript)

#### `Lexi/server/src/models/UsersModel.ts`
- Added `is_demo_finished: boolean` (default: false) — termination flag for demo
- Added `demo_registration_time: Date` — timestamp when user registered

#### `Lexi/server/src/types/users.type.ts`
- Updated `IUser` interface to include:
  - `is_demo_finished?: boolean`
  - `demo_registration_time?: Date`

#### `Lexi/server/src/services/users.service.ts`
- Modified `createUser()` to set `demo_registration_time: new Date()` when creating a user
- This allows the demo cycle to calculate elapsed time since registration

---

### 2. Demo Logic (Python)

#### `logic-python/services/research_service.py`
Added new method `run_demo_cycle()`:
- Queries users where `is_demo_finished = false` AND `demo_registration_time` exists
- For each user, calculates elapsed seconds since registration
- Fires 3 hardcoded notifications at:
  - **30 seconds**: "👋 Hi there! I'm Lexi. Looking forward to our chat!"
  - **2 minutes** (120s): "💭 By the way, how are you feeling today?"
  - **5 minutes** (300s): "🎉 Thanks for chatting with me! This has been wonderful."
- After notification #3, sets `is_demo_finished: true` for the user
- Tracks which notifications have been sent per user (via `demo_notif_0_sent`, `demo_notif_1_sent`, `demo_notif_2_sent` flags)
- Logs all events to `proactive_logs` collection

---

### 3. Scheduler Entry Point (Python)

#### `logic-python/scheduler.py`
- Added `IS_DEMO_MODE` environment variable check
- When `IS_DEMO_MODE=true`:
  - Calls `run_demo_cycle()` every 10 seconds instead of running full proactive logic
  - Displays "🎬 Lexi Demo Scheduler (DEMO MODE)" startup message
- When `IS_DEMO_MODE=false` (default):
  - Runs standard proactive cycle at fixed times
- **To enable demo mode, set environment variable**: `IS_DEMO_MODE=true`

---

### 4. Frontend (React)

**No code changes needed** — The frontend receives `is_demo_finished` flag as part of the user object from `getActiveUser()` endpoint.

The client can check:
```typescript
if (user.is_demo_finished) {
  // Show thank you screen (Step 2.4 — separate task)
}
```

---

## How to Use Demo Mode

### Setup
1. Deploy to `oxford-demo` branch
2. Set environment variable on Render/deployment platform:
   ```
   IS_DEMO_MODE=true
   ```

### During Demo
1. User registers in the app
2. Scheduler runs `run_demo_cycle()` every 10 seconds
3. User receives exactly 3 notifications at 30s, 2min, 5min post-registration
4. After 3rd notification, `is_demo_finished` is set to `true`
5. Frontend detects this and shows thank you screen

### Testing Locally
```bash
cd logic-python
IS_DEMO_MODE=true python scheduler.py
```

---

## Key Features
✅ **Deterministic** — Same 3 notifications every time
✅ **Isolated** — Demo logic doesn't affect main branch
✅ **Timestamped** — Uses registration time, not scheduler time
✅ **Trackable** — Logs all demo events for analysis
✅ **Reversible** — Can disable by setting `IS_DEMO_MODE=false` (default)

---

## Next Steps (Phase 2, Task 3)
- **Step 2.3**: Add `is_demo_finished` database check in chat endpoints (if needed)
- **Step 2.4**: Create UI thank-you screen triggered when `is_demo_finished: true`

---

## Files Modified
1. `Lexi/server/src/models/UsersModel.ts`
2. `Lexi/server/src/types/users.type.ts`
3. `Lexi/server/src/services/users.service.ts`
4. `logic-python/services/research_service.py`
5. `logic-python/scheduler.py`

All changes are backward-compatible and isolated to the `oxford-demo` branch.
