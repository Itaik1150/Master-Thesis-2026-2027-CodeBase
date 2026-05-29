from utils.mongodb_client import mongodb_client

mongodb_client.connect()
db = mongodb_client.db

exps = list(db["experiments"].find(
    {"experimentFeatures.proactiveSettings.enabled": True}, {"_id": 1}
))
enabled_ids = [exp["_id"] for exp in exps]

id_variants = []
for eid in enabled_ids:
    id_variants.append(str(eid))
    id_variants.append(eid)

print("Enabled experiment id_variants:", id_variants)

users = list(db["users"].find({
    "experimentId": {"$in": id_variants},
    "fcmToken": {"$exists": True, "$ne": ""},
}))
print(f"Matched users: {len(users)}")
for u in users:
    print(f"  {u.get('username')}  expId={u.get('experimentId')}  type={type(u.get('experimentId')).__name__}")

mongodb_client.disconnect()
