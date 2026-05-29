from utils.mongodb_client import mongodb_client

mongodb_client.connect()
db = mongodb_client.db

print("=== EXPERIMENTS ===")
for e in db["experiments"].find({}, {"_id": 1, "title": 1, "experimentFeatures": 1}):
    ps = (e.get("experimentFeatures") or {}).get("proactiveSettings") or {}
    print(f"  id={e['_id']}  title={e.get('title')}  proactive_enabled={ps.get('enabled')}")

print()
print("=== ALL USERS ===")
for u in db["users"].find({}, {"_id": 1, "username": 1, "experimentId": 1, "isProactive": 1, "fcmToken": 1}):
    has_tok = bool(u.get("fcmToken"))
    print(f"  id={u['_id']}  user={u.get('username')}  expId={u.get('experimentId')}  isProactive={u.get('isProactive')}  fcmToken={'YES' if has_tok else 'NO'}")

mongodb_client.disconnect()
