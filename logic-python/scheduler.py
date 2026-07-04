"""
Proactive notification scheduler.

Runs as a persistent background service (e.g. a Render "Background Worker").
At startup, reads each enabled experiment's notification schedule
(experimentFeatures.proactiveSettings.schedule) from MongoDB and registers one
APScheduler job per configured fire time / random window, gated to that
experiment's own allowed days.

Falls back to a hardcoded default schedule if MongoDB is unreachable or no
experiment has proactive settings configured yet, so the service never fails
to start.

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
from utils.mongodb_client import mongodb_client

# ── Hardcoded fallback (used only if MongoDB is unreachable at startup, or no
#    experiment has a schedule configured yet) ─────────────────────────────────
FALLBACK_FIRE_TIMES = ["13:45", "17:30", "21:15"]
FALLBACK_ALLOWED_DAYS = [0, 1, 2, 3, 4, 5, 6]  # 0=Sun .. 6=Sat, all days

_DAY_ABBR = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]


def _day_of_week_str(allowed_days) -> str:
    """Convert [0,1,4] (0=Sun) into APScheduler's 'sun,mon,thu' cron format."""
    days = sorted({d for d in (allowed_days or []) if isinstance(d, int) and 0 <= d <= 6})
    if not days or len(days) == 7:
        return "*"
    return ",".join(_DAY_ABBR[d] for d in days)


def load_schedules_from_db():
    """
    Read proactiveSettings.schedule from every experiment with proactive enabled.

    Returns a list of dicts, one per experiment:
      {"experiment_id": str, "allowed_days": [int], "mode": "exact"|"random",
       "fire_times": [str], "random_windows": [{"start": str, "end": str}]}

    Returns an empty list on any MongoDB failure — caller falls back to defaults.
    """
    schedules = []
    try:
        if not mongodb_client.connect():
            print("⚠️  Scheduler: could not connect to MongoDB — using fallback schedule")
            return []

        enabled_experiments = list(mongodb_client.db["experiments"].find(
            {"experimentFeatures.proactiveSettings.enabled": True},
            {"experimentFeatures.proactiveSettings.schedule": 1},
        ))

        for exp in enabled_experiments:
            ps = (exp.get("experimentFeatures") or {}).get("proactiveSettings") or {}
            sched = ps.get("schedule") or {}
            schedules.append({
                "experiment_id":  str(exp["_id"]),
                "allowed_days":   sched.get("allowedDays") or FALLBACK_ALLOWED_DAYS,
                "mode":           sched.get("mode") or "exact",
                "fire_times":     sched.get("fireTimes") or FALLBACK_FIRE_TIMES,
                "random_windows": sched.get("randomWindows") or [],
            })

    except Exception as e:
        print(f"⚠️  Scheduler: error loading schedules from MongoDB: {e}")
        return []
    finally:
        try:
            mongodb_client.disconnect()
        except Exception:
            pass

    return schedules


def proactive_job():
    """
    Runs the full proactive cycle across ALL enabled experiments' users.

    Per-user day-of-week enforcement happens inside coordinated_send_and_inject()
    (each user is gated by their OWN experiment's allowedDays) — this job-level
    day_of_week filter is a coarse pre-filter so we don't even attempt a cycle
    on days when nobody could possibly be eligible.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n⏰ [{now_str}] Scheduled proactive cycle triggered")

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


def register_jobs(scheduler: BlockingScheduler, schedules) -> int:
    """
    Register one APScheduler job per (experiment, fire_time) or
    (experiment, random_window) pair. Returns the number of jobs registered.
    """
    job_count = 0

    for sched in schedules:
        exp_id = sched["experiment_id"]
        dow = _day_of_week_str(sched["allowed_days"])

        if sched["mode"] == "random" and sched["random_windows"]:
            for w_idx, window in enumerate(sched["random_windows"]):
                try:
                    start_h, start_m = map(int, window["start"].split(":"))
                    end_h, end_m = map(int, window["end"].split(":"))
                except (KeyError, ValueError):
                    print(f"⚠️  Skipping malformed random window for experiment {exp_id[:8]}: {window}")
                    continue
                window_seconds = max(
                    0, (end_h * 3600 + end_m * 60) - (start_h * 3600 + start_m * 60)
                )
                # Task 6.4: register `count` separate jobs per window so multiple
                # notifications can be distributed within the same time range.
                # Each job uses jitter to fire at a distinct random minute.
                count = max(1, int(window.get("count") or 1))
                for n in range(count):
                    job_id = f"proactive_{exp_id}_rand{w_idx}_{n}"
                    scheduler.add_job(
                        proactive_job, "cron",
                        day_of_week=dow, hour=start_h, minute=start_m,
                        jitter=window_seconds if window_seconds > 0 else None,
                        id=job_id, replace_existing=True,
                    )
                    job_count += 1
                print(f"   🎲 Registered {count} random job(s) in window "
                      f"{window['start']}–{window['end']} for experiment {exp_id[:8]} "
                      f"({dow}), jitter={window_seconds}s")
        else:
            # Task 6.4: no cap on exact fire times (previously capped at 3)
            for time_str in sched["fire_times"]:
                try:
                    h, m = map(int, time_str.split(":"))
                except ValueError:
                    print(f"⚠️  Skipping malformed fire time for experiment {exp_id[:8]}: {time_str}")
                    continue
                job_id = f"proactive_{exp_id}_{time_str.replace(':', '')}"
                scheduler.add_job(
                    proactive_job, "cron",
                    day_of_week=dow, hour=h, minute=m,
                    id=job_id, replace_existing=True,
                )
                print(f"   ⏰ Exact-time job [{job_id}]: {time_str} ({dow})")
                job_count += 1

    return job_count


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Jerusalem")

    print("=" * 60)
    print("🗓️  Lexi Proactive Scheduler")
    print("=" * 60)

    schedules = load_schedules_from_db()

    if schedules:
        print(f"📡 Loaded schedule(s) from MongoDB for {len(schedules)} enabled experiment(s)")
        registered = register_jobs(scheduler, schedules)
    else:
        print("⚠️  No experiment schedules found — using hardcoded fallback")
        print(f"   Fire times : {', '.join(FALLBACK_FIRE_TIMES)} (Jerusalem time, all days)")
        for time_str in FALLBACK_FIRE_TIMES:
            h, m = map(int, time_str.split(":"))
            scheduler.add_job(proactive_job, "cron", hour=h, minute=m, id=f"proactive_fallback_{time_str}")
        registered = len(FALLBACK_FIRE_TIMES)

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    print("=" * 60)
    print(f"   Jobs registered: {registered}")
    print(f"   Daily cap      : see DAILY_MESSAGE_LIMIT env var")
    print(f"   Per-user day-of-week + heuristic weights re-verified live every cycle")
    print("   Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        scheduler.start()  # blocks here; next_run_time is only available after start
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Scheduler stopped.")
