# Stale Data Bug Fix — Proactive Cycle Runtime State

## Problem Summary

In the proactive cycle (`research_service.py`), a **stale data / runtime state bug** was causing newly extracted emotional memories to be orphaned as `used: False` in the database.

### Root Cause

The flow was:
1. **Line 891-893**: Load user + build memory from conversations (`basic` + `extracted`)
2. **Line 931**: Save memory to MongoDB → new `emotional_memories` are written with `used: False`
3. **Line 948**: `affective.analyze_and_schedule()` runs and updates MongoDB with new data
4. **Line 1140**: Call `affective.generate_affective_default(memory, ...)` with **stale in-memory `memory` dict**
   - The function looks for unused `emotional_memories` to select from
   - But the `memory` dict has old data from step 1, not the fresh values saved in step 2
   - So it defaults to cold-start message instead of using the newly saved memory
   - The memory remains orphaned: `used: False` (never consumed)

### Why This Happened

The reload logic (lines 952–975) only updated the `user` document's `proactiveMemory` nested field. It did NOT refresh the in-memory `memory` dict that was built at the start of the cycle. So:

- `user.proactiveMemory` ← ✅ Fresh from DB
- `memory` (Python dict) ← ❌ Stale (from line 893)

When `generate_affective_default(memory, ...)` was called, it read stale data.

## Solution

**File:** `logic-python/services/research_service.py`  
**Lines:** 952–975 (Step 2 reload block)

Added one line to the reload logic:

```python
memory.update(fresh_pm)  # Refresh in-memory dict alongside user dict update
```

### Updated Logic

```python
# Step 2: reload proactiveMemory from MongoDB before evaluate().
# ...
try:
    if mongodb_client.connect():
        fresh_doc = mongodb_client.db[mongodb_client.users_collection].find_one(
            {"_id": ObjectId(user_id)},
            {"proactiveMemory": 1},
        )
        if fresh_doc:
            fresh_pm = fresh_doc.get("proactiveMemory") or {}
            user = {**user, "proactiveMemory": fresh_pm}
            # Also update the in-memory memory dict to prevent stale data
            # from being used by generate_affective_default()
            memory.update(fresh_pm)
```

### Impact

Now when `affective.generate_affective_default(memory, ...)` is called:
- ✅ `memory["emotional_memories"]` contains freshly saved memories from the heuristic scans
- ✅ The function correctly selects an unused memory and marks it as `used: True` in MongoDB
- ✅ No orphaned memories remain in the database

## Testing

To verify the fix:
1. Run a proactive cycle with a user in the `affective` proactive group
2. Check the `proactiveMemory.emotional_memories` array for any stale `used: False` memories
3. All newly extracted emotional memories should be marked `used: True` after consumption

---

**Date:** June 17, 2026  
**Scope:** Single-line fix in Step 2 of `coordinated_send_and_inject()`
