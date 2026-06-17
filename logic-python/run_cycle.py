"""
One-shot entry point for the Render Cron Job.
Render calls: python run_cycle.py
The script runs the full proactive cycle once and exits.
"""
import sys
import os

# Make sure imports resolve correctly when run from the repo root
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from services.research_service import research_service

if __name__ == "__main__":
    # Conference demo bypass (has its own time-gate; always run first).
    print("🎯 Running Oxford demo cycle...")
    research_service.run_oxford_demo_cycle()

    print("🚀 Render cron: starting proactive cycle...")
    result = research_service.run_full_proactive_cycle()
    if result.get("success"):
        r = result.get("results", {})
        print(f"✅ Done — FCM sent: {r.get('fcm_sent', 0)}, injected: {r.get('injected', 0)}")
        sys.exit(0)
    else:
        print(f"❌ Cycle failed: {result.get('message', 'unknown error')}")
        sys.exit(1)
