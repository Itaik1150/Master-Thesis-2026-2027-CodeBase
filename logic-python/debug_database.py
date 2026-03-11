"""
Debug database injection issue
"""

from utils.mongodb_client import mongodb_client
from bson import ObjectId

def debug_database():
    """Debug the database injection issue"""
    print("=== 🔍 Database Debug ===")
    
    if not mongodb_client.connect():
        print("❌ Failed to connect to MongoDB")
        return
    
    try:
        # Check all users
        users = list(mongodb_client.db[mongodb_client.users_collection].find({}))
        print(f"📊 Total users: {len(users)}")
        
        for user in users:
            user_id = str(user["_id"])
            username = user.get("username", "Unknown")
            is_proactive = user.get("isProactive", False)
            fcm_token = user.get("fcmToken", "")
            
            print(f"\n👤 User: {username}")
            print(f"   🆔 ID: {user_id}")
            print(f"   🔔 Proactive: {is_proactive}")
            print(f"   📱 FCM Token: {fcm_token[:20]}..." if fcm_token else "   📱 FCM Token: None")
            
            # Check if user exists by ObjectId
            user_by_id = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(user_id)})
            if user_by_id:
                print(f"   ✅ Found by ObjectId")
            else:
                print(f"   ❌ NOT found by ObjectId")
            
            # Check agent structure
            agent = user.get("agent", {})
            if agent:
                print(f"   🤖 Agent fields: {list(agent.keys())}")
                first_sentence = agent.get("firstChatSentence", "None")
                print(f"   💬 First sentence: {first_sentence}")
            else:
                print(f"   ❌ No agent field")
        
        # Test injection on a specific user
        if users:
            test_user = users[0]
            test_user_id = str(test_user["_id"])
            
            print(f"\n🧪 Testing injection on user: {test_user.get('username')}")
            
            # Test update with ObjectId
            result = mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(test_user_id)},
                {"$set": {"agent.firstChatSentence": "TEST MESSAGE"}}
            )
            
            print(f"📊 Update result:")
            print(f"   Matched: {result.matched_count}")
            print(f"   Modified: {result.modified_count}")
            
            # Verify the update
            updated_user = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(test_user_id)})
            if updated_user:
                agent = updated_user.get("agent", {})
                first_sentence = agent.get("firstChatSentence", "None")
                print(f"💬 Updated first sentence: {first_sentence}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        mongodb_client.disconnect()

if __name__ == "__main__":
    debug_database()
