"""
Test Proactive Research Flow
"""
import os
import sys
from services.research_service import research_service
from utils.mongodb_client import mongodb_client

def main():
    """Test the complete proactive research flow"""
    print("=== 🧪 Proactive Research Flow Test ===")
    
    # Test message for all proactive users
    test_message = "Hello Research Participant! This is a proactive message. Does it show up in your chat?"
    
    print(f"📝 Test message: '{test_message}'")
    
    # Run the complete proactive cycle
    print(f"\n🚀 Running Full Proactive Cycle...")
    results = research_service.run_proactive_cycle(test_message)
    
    # Display results
    if results["success"]:
        print(f"✅ {results['message']}")
        print(f"📊 Total Users: {results['total_users']}")
        print(f"💉 Injected: {results['injected_count']}")
        print(f"📤 Notifications: {results['notification_count']}")
        
        print(f"\n🎯 Test Complete!")
        print("📱 Check your mobile app/emulator:")
        print("   1. You should receive FCM notifications")
        print("   2. Click notifications to open Lexi")
        print("   3. The injected message should appear as first messages")
        print("   4. Verify the message content matches what was injected")
    else:
        print(f"❌ Test failed: {results['message']}")

if __name__ == "__main__":
    main()
