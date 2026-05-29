"""
MongoDB Client for Python Logic
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import dns.resolver

# Force dnspython to use Google DNS so mongodb+srv:// SRV lookups work
# even when the local/university DNS server blocks Atlas resolution.
_resolver = dns.resolver.Resolver(configure=False)
_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
dns.resolver.default_resolver = _resolver

# Load environment variables
load_dotenv()

class MongoDBClient:
    """MongoDB connection and query client"""
    
    def __init__(self):
        """Initialize MongoDB connection"""
        self.mongo_url = os.getenv('MONGODB_URL')
        self.db_name = os.getenv('MONGODB_DB_NAME')
        self.users_collection = os.getenv('MONGODB_USERS_COLLECTION', 'users')
        
        self.client: Optional[MongoClient] = None
        self.db = None
        
    def connect(self):
        """Establish MongoDB connection"""
        try:
            self.client = MongoClient(self.mongo_url)
            self.db = self.client[self.db_name]
            return True
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            return False
            
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            
    def get_users_with_fcm_tokens(self) -> List[Dict[str, Any]]:
        """Fetch all users who have valid FCM tokens"""
        try:
            if self.db is None:
                print("Database not connected")
                return []
                
            # Debug: Print database and collection names
            # print(f"DEBUG: Database name: '{self.db_name}'")
            # print(f"DEBUG: Collection name: '{self.users_collection}'")
            
            # Debug: List all collections in the database
            collections = self.db.list_collection_names()
            # print(f"DEBUG: All collections in database: {collections}")
            
            # Debug: Check if users collection exists
            if self.users_collection not in collections:
                print(f"DEBUG: Collection '{self.users_collection}' does not exist!")
                return []
            
            # First, show total users in database (broaden query to find all users)
            total_users = list(self.db[self.users_collection].find({}))
            # print(f"DEBUG: Total users found with broad query: {len(total_users)}")
            
            # Debug: Print first user structure (if any)
            # if total_users:
                # print(f"DEBUG: First user structure: {total_users[0]}")
            
            # Query for users with non-empty fcmToken field
            users = list(self.db[self.users_collection].find(
                {"fcmToken": {"$exists": True, "$ne": ""}}
            ))
            
            print(f"Found {len(users)} users with FCM tokens")
            return users
            
        except Exception as e:
            print(f"Error fetching users with FCM tokens: {e}")
            return []
            
    def get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get single user context by ID"""
        try:
            if self.db is None:
                print("Database not connected")
                return None
                
            user = self.db[self.users_collection].find_one({"_id": user_id})
            if user:
                print(f"Found user: {user.get('username', 'Unknown')} with FCM token")
            return user
            
        except Exception as e:
            print(f"Error fetching user {user_id}: {e}")
            return None
    
    def update_user_first_message(self, user_id: str, custom_message: str) -> bool:
        """Update user's agent firstChatSentence for prompt injection"""
        try:
            if self.db is None:
                print("Database not connected")
                return False
                
            result = self.db[self.users_collection].update_one(
                {"_id": user_id},
                {"$set": {"agent.firstChatSentence": custom_message}}
            )
            
            if result.modified_count > 0:
                print(f"Updated first message for user {user_id}")
                return True
            else:
                print(f"No user found or no changes made for {user_id}")
                return False
                
        except Exception as e:
            print(f"Error updating first message for user {user_id}: {e}")
            return False

# Singleton instance
mongodb_client = MongoDBClient()
