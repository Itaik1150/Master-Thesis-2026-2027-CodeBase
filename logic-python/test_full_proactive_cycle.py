"""
Test the full proactive research cycle
"""

from services.research_service import ResearchService

def test_full_proactive_cycle():
    """
    Test the complete proactive research cycle
    """
    print("=== 🧪 Full Proactive Cycle Test ===")
    
    # Initialize research service
    research_service = ResearchService()
    
    # Run the full cycle
    result = research_service.run_full_proactive_cycle()
    
    # Display results
    print(f"\n📊 Final Results:")
    print(f"✅ Success: {result.get('success', False)}")
    
    if result.get('success'):
        print(f"🆔 Cycle ID: {result.get('cycle_id', 'N/A')}")
        print(f"⏱️ Duration: {result.get('duration', 0):.2f} seconds")
        
        results = result.get('results', {})
        print(f"📱 FCM Sent: {results.get('fcm_sent', 0)}")
        print(f"💬 Messages Injected: {results.get('injected', 0)}")
        print(f"❌ FCM Failed: {results.get('fcm_failed', 0)}")
        print(f"❌ Injection Failed: {results.get('injection_failed', 0)}")
        
        message_used = result.get('message_used', {})
        print(f"🎯 Message Used: {message_used.get('generated_message', 'N/A')}")
        print(f"🔖 Trigger Source: {message_used.get('trigger_source', 'N/A')}")
        
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        print(f"📝 Message: {result.get('message', 'No message')}")
    
    return result

def test_individual_components():
    """
    Test individual components of the proactive system
    """
    print("\n=== 🔧 Component Testing ===")
    
    research_service = ResearchService()
    
    # Test 1: Candidate pool (topic-only, Phase 4.1+)
    print("\n1️⃣ Testing Candidate Pool...")
    candidates = research_service.build_candidate_pool()
    print(f"💡 Candidates built: {len(candidates)}")
    for i, c in enumerate(candidates, 1):
        print(f"   {i}. [{c['topic_label']}] {c['generated_message']}")
    
    # Test 2: User targeting
    print("\n2️⃣ Testing User Targeting...")
    cycle_id = "test-cycle-123"
    eligible_users = research_service.get_proactive_users_with_rate_limit(cycle_id)
    print(f"👥 Eligible Users: {len(eligible_users)}")
    for user in eligible_users[:3]:  # Show first 3
        print(f"   👤 {user.get('username', 'Unknown')} ({user.get('isProactive', False)})")

if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Full proactive cycle test")
    print("2. Individual component tests")
    print("3. Both tests")
    
    choice = input("Enter choice (1, 2, or 3): ").strip()
    
    if choice == "1":
        test_full_proactive_cycle()
    elif choice == "2":
        test_individual_components()
    elif choice == "3":
        test_individual_components()
        test_full_proactive_cycle()
    else:
        print("⚠️ Invalid choice. Running full cycle test...")
        test_full_proactive_cycle()
