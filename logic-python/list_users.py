from utils.mongodb_client import mongodb_client

mongodb_client.connect()

print("Collections in LexiDB:", mongodb_client.db.list_collection_names())

for col in mongodb_client.db.list_collection_names():
    count = mongodb_client.db[col].count_documents({})
    print(f"  {col}: {count} documents")

print("---")
users = list(mongodb_client.db[mongodb_client.users_collection].find(
    {}, {'_id': 1, 'username': 1, 'isProactive': 1, 'fcmToken': 1}
))
print(f"Users found in '{mongodb_client.users_collection}': {len(users)}")
for u in users:
    token_status = 'has token' if u.get('fcmToken') else 'no token'
    print(f"  ID: {u['_id']}  user: {u.get('username')}  proactive: {u.get('isProactive')}  {token_status}")

mongodb_client.disconnect()
