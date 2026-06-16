# Quick Reference: Affective Memory Pipeline Implementation

## Code Changes Summary

### 1. llm_service.py::extract_user_memory()

**Added Parameters:**
```python
unanalyzed_only: bool = False,
mongodb_client = None,
user_id: str = "",
```

**Key Logic:**
```python
# Skip LLM if no unanalyzed messages exist
if unanalyzed_only and not unanalyzed_messages:
    return empty

# Mark messages as analyzed after successful extraction
for msg_id in analyzed_msg_ids:
    mongodb_client.db["conversations"].update_one(
        {"_id": ObjectId(msg_id)},
        {"$set": {"analyzed_for_memory": True}},
    )
```

---

### 2. affective.py::generate_affective_default()

**NEW Step 1: Expiration (lines 251-275)**
```python
expiry_threshold = now - timedelta(hours=72)
result = mongodb_client.db[...].update_many(
    {
        "_id": ObjectId(user_id),
        "proactiveMemory.emotional_memories": {
            "$elemMatch": {
                "used": False,
                "timestamp_iso": {"$lt": expiry_threshold.isoformat()}
            }
        }
    },
    {"$set": {"proactiveMemory.emotional_memories.$[elem].used": True}},
    array_filters=[{"elem.used": False, "elem.timestamp_iso": {...}}]
)
```

**NEW Step 3: Marking with Positional Operator (lines 313-329)**
```python
result = mongodb_client.db[...].update_one(
    {
        "_id": ObjectId(user_id),
        "proactiveMemory.emotional_memories": {
            "$elemMatch": {"content": memory_content, "used": False}
        }
    },
    {"$set": {"proactiveMemory.emotional_memories.$.used": True}}  # $ = exact position
)
```

---

### 3. research_service.py::extract_conversation_memory()

**Updated Call:**
```python
extracted = self.llm_service.extract_user_memory(
    all_user_messages,
    preferred_language,
    today_iso=datetime.now().isoformat(timespec="minutes"),
    unanalyzed_only=True,           # NEW
    mongodb_client=mongodb_client,  # NEW
    user_id=user_id,                # NEW
)
```

---

## MongoDB Positional Operator ($)

### Why NOT $push (wrong):
```javascript
// ❌ WRONG: Creates duplicate in array
db.users.updateOne(
    { _id: user_id },
    { $push: { "proactiveMemory.emotional_memories": {..., used: true} } }
)
// Result: Array grows, memory loop persists
```

### Why $ (correct):
```javascript
// ✅ CORRECT: Updates exact existing element in array
db.users.updateOne(
    {
        _id: user_id,
        "proactiveMemory.emotional_memories": {
            $elemMatch: { content: "...", used: false }
        }
    },
    { $set: { "proactiveMemory.emotional_memories.$.used": true } }
)
// Result: Array unchanged size, element marked used
```

The `$` operator replaces the element's position with the update, preventing duplicates.

---

## Data Flow

```
Cycle N:
├─ extract_conversation_memory()
│  └─ extract_user_memory(unanalyzed_only=True)
│     ├─ Query: analyzed_for_memory != True
│     ├─ LLM call (only if unanalyzed messages exist)
│     └─ Mark: analyzed_for_memory = True on each message
│
├─ generate_affective_default()
│  ├─ Step 1 (Expiration): Mark stale (>72h) as used=True
│  ├─ Step 2 (Selection): Pick best unused memory
│  ├─ LLM: Generate empathetic message
│  └─ Step 3 (Marking): Update emotion_memories[i].used = True using $
│
└─ Result: No duplicates, fresh emotions, minimal tokens

Cycle N+1:
├─ extract_conversation_memory()
│  └─ extract_user_memory(unanalyzed_only=True)
│     ├─ Query: analyzed_for_memory != True
│     ├─ ✅ Skips previous messages (already marked analyzed)
│     ├─ LLM call only for NEW messages (massive token savings)
│     └─ Mark: analyzed_for_memory = True on new messages
│
└─ Result: No re-analysis, clean pipeline
```

---

## Verification Commands (MongoDB)

### Check analyzed_for_memory flag:
```javascript
db.conversations.find(
    { userId: "...", analyzed_for_memory: true },
    { content: 1, analyzed_for_memory: 1 }
).limit(5)
```

### Check emotional_memories for duplicates:
```javascript
db.users.aggregate([
    { $match: { _id: ObjectId("...") } },
    { $unwind: "$proactiveMemory.emotional_memories" },
    { $group: { 
        _id: "$proactiveMemory.emotional_memories.content",
        count: { $sum: 1 }
    }},
    { $match: { count: { $gt: 1 } } }  // Only duplicates
])
```

### Check expiration working:
```javascript
db.users.findOne(
    { _id: ObjectId("...") },
    { "proactiveMemory.emotional_memories": 1 }
)
// All memories >72h old should have used: true
```

### Verify positional operator (check array size unchanged):
```javascript
// Before and after marking — array length should stay same
db.users.findOne({ _id: ObjectId("...") })
// "proactiveMemory.emotional_memories" length unchanged
```

---

## Expected Log Output

**Cycle 1 (First Run):**
```
✅ Marked 7 messages as analyzed_for_memory
⏰ Expired 2 stale emotional memories for user123
💛 Marked emotional memory as used for user123: 'felt anxious about...'
```

**Cycle 2:**
```
✅ Marked 2 messages as analyzed_for_memory  # Only NEW messages
⏰ Expired 1 stale emotional memories for user123
💛 Marked emotional memory as used for user123: 'mentioned difficulty with...'
```

**Token Reduction:**
- Cycle 1: Full extraction on all messages = ~800 tokens
- Cycle 2: Only new messages = ~150 tokens (81% reduction)

---

## Rollback (if needed)

To safely rollback without losing data:

1. Stop the scheduler
2. Remove `unanalyzed_only=True` from research_service.py call
3. Remove Steps 1 & 3 from affective.py (keep Step 2 selection logic)
4. Existing `emotional_memories` array preserved; won't be re-queried

The `analyzed_for_memory` flag is harmless if ignored; legacy messages won't have it.

