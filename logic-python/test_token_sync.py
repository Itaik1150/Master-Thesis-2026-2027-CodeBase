"""
Test Token Synchronization System
"""
import os
import sys
from utils.mongodb_client import mongodb_client

def test_token_sync():
    """Test the token synchronization system"""
    print("=== 🔧 Testing Token Synchronization System ===")
    
    if not mongodb_client.connect():
        print("❌ Failed to connect to MongoDB")
        return
    
    try:
        print("📊 Checking user FCM token status...")
        
        # Get all users with FCM tokens
        users_with_tokens = list(mongodb_client.db[mongodb_client.users_collection].find({
            "fcmToken": {"$exists": True, "$ne": ""}
        }))
        
        print(f"📱 Found {len(users_with_tokens)} users with FCM tokens")
        
        for user in users_with_tokens:
            username = user.get('username', 'Unknown')
            user_id = user.get('_id', 'Unknown')
            fcm_token = user.get('fcmToken', '')
            token_updated_at = user.get('fcmTokenUpdatedAt', 'Never')
            is_proactive = user.get('isProactive', False)
            
            print(f"\n👤 User: {username}")
            print(f"   📋 ID: {user_id}")
            print(f"   📱 Token: {fcm_token[:20]}... (length: {len(fcm_token)})")
            print(f"   🕒 Updated: {token_updated_at}")
            print(f"   🔔 Proactive: {is_proactive}")
            
            # Validate token format
            if len(fcm_token) < 100:
                print(f"   ⚠️ WARNING: Token seems too short!")
            else:
                print(f"   ✅ Token format looks good")
        
        # Check for users without tokens (should be admins or inactive)
        users_without_tokens = list(mongodb_client.db[mongodb_client.users_collection].find({
            "$or": [
                {"fcmToken": {"$exists": False}},
                {"fcmToken": {"$eq": ""}}
            ]
        }))
        
        print(f"\n📊 Users without FCM tokens: {len(users_without_tokens)}")
        
        for user in users_without_tokens[:5]:  # Show first 5
            username = user.get('username', 'Unknown')
            is_admin = user.get('isAdmin', False)
            print(f"   👤 {username} (Admin: {is_admin})")
        
        print(f"\n🎯 Token Sync Analysis Complete!")
        print(f"💡 Recommendations:")
        print(f"   1. All non-admin users should have FCM tokens")
        print(f"   2. Tokens should be updated regularly")
        print(f"   3. Token length should be > 100 characters")
        
    except Exception as e:
        print(f"❌ Error during token sync test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        mongodb_client.disconnect()

def simulate_token_update():
    """Simulate a token update to test the system"""
    print(f"\n=== 🔄 Simulating Token Update ===")
    
    if not mongodb_client.connect():
        print("❌ Failed to connect to MongoDB")
        return
    
    try:
        # Find a user to simulate token update for
        user = mongodb_client.db[mongodb_client.users_collection].find_one({
            "fcmToken": {"$exists": True}
        })
        
        if not user:
            print("❌ No users with FCM tokens found")
            return
        
        user_id = user.get('_id')
        username = user.get('username', 'Unknown')
        
        # Simulate new token
        new_token = "simulated_token_" + "x" * 120  # Make it proper length
        
        print(f"🔄 Simulating token update for user: {username}")
        print(f"   📱 New token: {new_token[:20]}...")
        
        # Update the token
        result = mongodb_client.db[mongodb_client.users_collection].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "fcmToken": new_token,
                    "fcmTokenUpdatedAt": "2024-01-01T12:00:00Z"
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"✅ Token update simulated successfully")
            
            # Verify the update
            updated_user = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": user_id})
            updated_token = updated_user.get('fcmToken', '')
            updated_at = updated_user.get('fcmTokenUpdatedAt', '')
            
            print(f"   📱 Updated token: {updated_token[:20]}...")
            print(f"   🕒 Updated at: {updated_at}")
        else:
            print(f"❌ Token update simulation failed")
        
    except Exception as e:
        print(f"❌ Error simulating token update: {e}")
    
    finally:
        mongodb_client.disconnect()

if __name__ == "__main__":
    test_token_sync()
    simulate_token_update()
