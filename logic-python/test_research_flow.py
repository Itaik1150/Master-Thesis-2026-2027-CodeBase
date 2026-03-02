"""
Test Proactive Research Flow
"""
import os
import sys
from services.research_service import research_service
from utils.mongodb_client import mongodb_client

def main():
    """Test the complete proactive research flow"""
    print("=== Proactive Research Flow Test ===")
    
    # Connect to MongoDB
    if not mongodb_client.connect():
        print("X Failed to connect to MongoDB")
        return
    
    try:
        # 1. Get research statistics
        print("\n1. Research Statistics:")
        stats = research_service.get_research_statistics()
        print(f"Total users with FCM: {stats['total_users_with_fcm']}")
        print(f"Proactive users: {stats['proactive_users']}")
        print(f"Control users: {stats['control_users']}")
        print(f"Proactive percentage: {stats['proactive_percentage']}%")
        
        # 2. Get proactive users
        print("\n2. Proactive Users:")
        proactive_users = research_service.get_proactive_users()
        print(f"Found {len(proactive_users)} proactive users with FCM tokens")
        
        if not proactive_users:
            print("X No proactive users found. Testing with sample user...")
            # Create a test prompt injection for demonstration
            test_user_id = "test_user_id"
            custom_message = "Hello! This is a research prompt to test our proactive system. How are you feeling today?"
            
            print(f"\n3. Testing Prompt Injection (Sample):")
            message_id = research_service.inject_prompt_and_notify(
                user_id=test_user_id,
                custom_message=custom_message,
                notification_title="Research Test",
                notification_body="Testing proactive notification system"
            )
            
            if message_id:
                print(f"+ Test injection successful: {message_id}")
            else:
                print("X Test injection failed (expected - no real user)")
        else:
            # 3. Test single user injection
            test_user = proactive_users[0]
            print(f"\n3. Testing Single User Injection:")
            print(f"Test user: {test_user.name}")
            
            custom_message = "🔬 Research Prompt: Hello! This is a special research message designed to study user engagement. What are your thoughts on this proactive approach?"
            
            message_id = research_service.inject_prompt_and_notify(
                user_id=test_user.user_id,
                custom_message=custom_message,
                notification_title="Research Study Active",
                notification_body=f"Hi {test_user.name}! Check your updated conversation."
            )
            
            if message_id:
                print(f"+ Single injection successful: {message_id}")
                
                # 4. Run full experiment (optional - comment out for testing)
                print(f"\n4. Full Experiment (Optional):")
                print("To run full experiment on all proactive users, uncomment the code below:")
                print("# results = research_service.run_proactive_experiment(custom_message)")
                print("# print(f'Full experiment results: {results}')")
            else:
                print("X Single injection failed")
        
        print(f"\n=== Test Complete ===")
        print(f"Research infrastructure is ready!")
        
    except Exception as e:
        print(f"X Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        mongodb_client.disconnect()

if __name__ == "__main__":
    main()
