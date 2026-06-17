"""
Proactive notification scheduler.

Fires run_full_proactive_cycle() at fixed times each day,
only within the allowed time window.

Usage:
    cd logic-python
    python scheduler.py

To stop: Ctrl+C
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

def _has_firebase_credentials() -> bool:
    if os.getenv("SERVICE_ACCOUNT_JSON_CONTENT", "").strip():
        return True
    if (os.getenv("SERVICE_ACCOUNT_JSON") or "").strip().startswith("{"):
        return True
    for path in (
        "/etc/secrets/firebase.json",
        "/etc/secrets/service_account.json",
        "/etc/secrets/SERVICE_ACCOUNT_JSON_CONTENT",
    ):
        if os.path.isfile(path):
            return True
    return False


if _has_firebase_credentials():
    print("🔑 Firebase credentials detected")
else:
    print("❌ Firebase: no credentials found.")
    print("   On Render → Environment → add SERVICE_ACCOUNT_JSON_CONTENT")
    print("   (paste full JSON from lexi-72330-firebase-adminsdk-....json)")
    sys.exit(1)

from services.research_service import get_research_service

# ── Configuration ────────────────────────────────────────────────────────────
# Times to fire (24-hour clock, Jerusalem time).
# Change these here until a Phase-4 dashboard setting is available.
# FIRE_TIMES = ["13:45", "17:30", "21:15"]
FIRE_TIMES = ["00:06", "00:08", "00:10"]
# Notifications will only be sent if the current hour falls inside this window.
# This is a safety net on top of the cron schedule.
WINDOW_START_HOUR = 9    # inclusive
WINDOW_END_HOUR   = 21   # exclusive
# ─────────────────────────────────────────────────────────────────────────────


def within_window() -> bool:
    """Return True if the current Jerusalem hour is inside the allowed window."""
    hour = datetime.now(ZoneInfo("Asia/Jerusalem")).hour
    return WINDOW_START_HOUR <= hour < WINDOW_END_HOUR


def proactive_job():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n⏰ [{now_str}] Scheduled proactive cycle triggered")

    # Conference demo bypass always runs (has its own time-gate logic).
    try:
        get_research_service().run_oxford_demo_cycle()
    except Exception as e:
        print(f"❌ Unhandled error in demo cycle: {e}")

    if not within_window():
        print(f"⏸️  Outside allowed window ({WINDOW_START_HOUR}:00–{WINDOW_END_HOUR}:00), skipping standard cycle")
        return

    try:
        result = get_research_service().run_full_proactive_cycle()
        if result.get("success"):
            r = result.get("results", {})
            print(f"✅ Cycle done — FCM sent: {r.get('fcm_sent', 0)}, injected: {r.get('injected', 0)}")
        else:
            print(f"⚠️  Cycle finished with issues: {result.get('message', 'unknown')}")
    except Exception as e:
        print(f"❌ Unhandled error in proactive_job: {e}")


def job_listener(event):
    if event.exception:
        print(f"❌ Scheduler job raised an exception: {event.exception}")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Jerusalem")

    for time_str in FIRE_TIMES:
        h, m = map(int, time_str.split(":"))
        scheduler.add_job(proactive_job, "cron", hour=h, minute=m, id=f"proactive_{time_str}")

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    print("=" * 55)
    print("🗓️  Lexi Proactive Scheduler")
    print(f"   Fire times : {', '.join(FIRE_TIMES)} (Jerusalem time)")
    print(f"   Time window: {WINDOW_START_HOUR}:00 – {WINDOW_END_HOUR}:00")
    print(f"   Daily cap  : see DAILY_MESSAGE_LIMIT env var")
    print("   Press Ctrl+C to stop.")
    print("=" * 55)

    try:
        scheduler.start()  # blocks here; next_run_time is only available after start
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Scheduler stopped.")
