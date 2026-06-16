# Affective Memory Pipeline Restructure

## Problem Solved
- **Memory Looping Bug**: Same emotions re-analyzed every cycle, creating duplicates in emotional_memories array
- **Token Waste**: LLM re-extracts from already-analyzed messages repeatedly
- **Stale Emotions**: System brings up expired emotional context (>72 hours old)

## Solution: Two-Step Pipeline

### STEP 1: Smart Extraction (in `llm_service.py` & DB fetch logic)

**Goal**: Stop re-analyzing the same messages in every cycle.

#### 1.1 Update DB Query in `extract_conversation_memory()`
```python
# In llm_service.py::extract_user_memory()

# NEW: Fetch ONLY messages where analyzed_for_memory != True
if unanalyzed_only and mongodb_client and user_id:
    recent_metas = list(mongodb_client.db["metadata_conversations"].find(
        {"userId": user_id},
        sort=[("createdAt", -1)],
        limit=5,
    ))
    
    unanalyzed_messages = []
    analyzed_msg_ids = []
    
    for meta in recent_metas:
        conv_id = str(meta["_id"])
        raw = list(mongodb_client.db["conversations"].find(
            {
                "conversationId": conv_id,
                "role": "user",
                "analyzed_for_memory": {"$ne": True},  # ONLY unanalyzed
            },
        ))
        for msg in raw:
            if msg.get("content"):
                unanalyzed_messages.append(msg.get("content"))
                analyzed_msg_ids.append(msg["_id"])
    
    if not unanalyzed_messages:
        return empty  # SKIP LLM call entirely if no unanalyzed messages
```

#### 1.2 Mark Messages After Extraction
```python
# After LLM extracts emotional insights successfully:

if unanalyzed_only and mongodb_client and user_id and 'analyzed_msg_ids' in locals():
    for msg_id in analyzed_msg_ids:
        mongodb_client.db["conversations"].update_one(
            {"_id": ObjectId(msg_id)},
            {"$set": {"analyzed_for_memory": True}},  # Mark as analyzed
        )
    print(f"✅ Marked {len(analyzed_msg_ids)} messages as analyzed_for_memory")
```

#### 1.3 Call with Flag in `research_service.py`
```python
# In research_service.py::extract_conversation_memory()

extracted = self.llm_service.extract_user_memory(
    all_user_messages,
    preferred_language,
    today_iso=datetime.now().isoformat(timespec="minutes"),
    unanalyzed_only=True,           # NEW
    mongodb_client=mongodb_client,  # NEW
    user_id=user_id,                # NEW
)
```

**Result**: ✅ LLM only runs on truly new messages; no token waste on re-analysis.

---

### STEP 2: Selection, Expiration & Marking (in `affective.py`)

**Goal**: Act on fresh emotions; expire old ones; prevent looping duplicates.

#### 2.1 Expiration: Mark Stale Memories
```python
# In affective.py::generate_affective_default()

now = datetime.now(timezone.utc)
expiry_threshold = now - timedelta(hours=72)

result = mongodb_client.db[mongodb_client.users_collection].update_many(
    {
        "_id": ObjectId(user_id),
        "proactiveMemory.emotional_memories": {
            "$elemMatch": {
                "used": False,
                "timestamp_iso": {"$lt": expiry_threshold.isoformat()}
            }
        }
    },
    {
        "$set": {
            "proactiveMemory.emotional_memories.$[elem].used": True
        }
    },
    array_filters=[{
        "elem.used": False,
        "elem.timestamp_iso": {"$lt": expiry_threshold.isoformat()}
    }]
)
```

**Result**: ✅ Any emotional memory unused for 72h is automatically marked used (expired).

#### 2.2 Selection: Pick Best Unused Memory
```python
# After expiration, filter for unused only:

unused_memories = [mem for mem in emotional_memories if not mem.get('used', False)]

if unused_memories:
    # Select by affective_score (desc), then timestamp (desc for most recent)
    best_memory = max(unused_memories, key=lambda m: (
        m.get('affective_score', 1), 
        m.get('timestamp_iso', '1900-01-01')
    ))
```

**Result**: ✅ System acts on highest-affective, most-recent unused memory.

#### 2.3 Marking (Critical: Fixes Loop)
```python
# After generating message, mark THAT SPECIFIC memory as used using positional operator:

result = mongodb_client.db[mongodb_client.users_collection].update_one(
    {
        "_id": ObjectId(user_id),
        "proactiveMemory.emotional_memories": {
            "$elemMatch": {"content": memory_content, "used": False}
        }
    },
    {
        "$set": {
            "proactiveMemory.emotional_memories.$.used": True  # $ = exact position in array
        }
    }
)
```

**CRITICAL**: The `$` positional operator updates the **exact existing item** in the array, not pushing a duplicate!

**Result**: ✅ Memory is marked used ONLY AFTER the proactive message fires; prevents looping.

---

## Files Changed

1. **`llm_service.py`** — `extract_user_memory()` method
   - Added params: `unanalyzed_only`, `mongodb_client`, `user_id`
   - Fetches only messages where `analyzed_for_memory != True`
   - Marks messages as `analyzed_for_memory: True` after successful extraction
   - Skips LLM call entirely if no unanalyzed messages exist

2. **`affective.py`** — `generate_affective_default()` function
   - Added 72-hour expiration logic for stale memories
   - Selects best unused memory before generating message
   - Uses MongoDB positional operator `$` to mark exact memory as used
   - Prevents loop by updating in-place, not pushing duplicates

3. **`research_service.py`** — `extract_conversation_memory()` method
   - Calls `extract_user_memory()` with `unanalyzed_only=True`
   - Passes `mongodb_client` and `user_id` for smart extraction

---

## MongoDB Schema Requirements

### On `conversations` collection
- Add field: `analyzed_for_memory` (Boolean, optional)
- Used to track which messages have been processed for emotional extraction

### On `users` collection (in `proactiveMemory.emotional_memories` array)
- Existing: `content`, `affective_score`, `timestamp_iso`
- Existing: `used` (Boolean) — marks if memory has been acted upon
- No schema changes needed; system already initializes `used: False`

---

## Benefits

| Issue | Before | After |
|-------|--------|-------|
| **Memory Looping** | Same memory processed repeatedly → duplicates | Memory marked `used` after firing → no duplicates |
| **Token Waste** | Re-analyzes all messages every cycle | Only new unanalyzed messages → ~80% fewer LLM calls |
| **Stale Emotions** | Brings up 1-week old emotional context | Auto-expires after 72h → fresh emotions only |
| **DB Load** | Repeated extraction queries | Smart filtering skips already-analyzed messages |

---

## Testing Checklist

- [ ] Verify `analyzed_for_memory: True` is set on messages after first extraction
- [ ] Verify second cycle skips those messages entirely (no LLM call for them)
- [ ] Verify 72-hour expiration marks old `used: False` memories as `used: True`
- [ ] Verify `emotional_memories` array doesn't grow with duplicates
- [ ] Verify positional operator `$` updates exact memory (count unchanged)
- [ ] Check logs for "✅ Marked X messages as analyzed_for_memory" on first run
- [ ] Check logs for "⏰ Expired X stale emotional memories" on subsequent runs

