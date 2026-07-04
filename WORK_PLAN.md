# Lexi — Final Execution Plan & Working Document

> Status legend: ✅ Done | 🔄 In Progress | ⬜ Pending

---

## Phase 1: Core System Tuning & Logic (`main` branch)

---

### ✅ Task 1: A/B Group Assignment

**Goal:** Assign every new user to one of three proactive groups at registration. The assignment is stored on the user document and read every cycle to gate notification behavior.

- **Group 1 — Affective Proactive:** Emotional, personalized notifications. Acts as a listening ear / journaling prompt to encourage emotional sharing.
- **Group 2 — Generic Proactive:** Random, generic invitations to chat. No emotional framing.
- **Group 3 — Reactive:** No proactive notifications at all.

**Relevant files:**
- `Lexi/server/src/services/experiments.service.ts` — `getActiveAgent()`: extend A/B logic to 3 groups
- `Lexi/server/src/services/users.service.ts` — assigns group at registration
- `Lexi/server/src/models/UsersModel.ts` — stores `proactiveGroup` field
- `Lexi/server/src/models/ExperimentsModel.ts` — experiment schema
- `logic-python/services/research_service.py` — reads `proactiveGroup`, routes to correct logic

---

### ✅ Task 2: System Prompt Sanitization & Strict Emotional Framing

**Goal:** Audit every string sent to the LLM. Remove all mentions of "experiment", "research", or "thesis". Enforce group-specific personas.

- **Affective group:** Persona = *"You are an empathetic agent that encourages emotional sharing."* Notifications must be generated strictly from emotional memories, not hobbies or general interests.
- **Generic group:** Persona = standard assistant, zero emotional weight, no specific topics.
- **Cold start (Affective):** If no emotional memory exists, generate a warm, generic emotional invitation (e.g., *"Hi [Name], how are you feeling today?"*).

**Relevant files:**
- `logic-python/services/llm_service.py` — all LLM prompt strings
- `logic-python/services/research_service.py` — passes framing context to LLM service
- `Lexi/server/src/services/conversations.service.ts` — in-chat system prompt assembly

---

### ✅ Task 3: Heuristic Modularity & Probability-Based Selection

**This is the biggest architectural change. Read fully before implementing.**

#### 3.1 — Probability-Based Heuristic Selection

Replace the current fixed-priority chain (affective → gap → temporal → topic) with a **researcher-controlled probability system**. Each active heuristic gets a probability weight set from the dashboard (weights across all active heuristics must sum to 100%). Each cycle, the system randomly selects one heuristic according to those weights.

The five heuristics are:
1. **Affective** — detects emotional content in past conversations
2. **Temporal** — detects upcoming events the user mentioned
3. **Behavioural Gap** — detects stated intentions the user hasn't followed up on
4. **Generic** — sends a neutral, generic invitation to chat (no memory needed)
5. **Reactive** — sends nothing; effectively the null state

**Reactive** is not a heuristic in the active sense — it is the fallback when all heuristics are toggled off, OR it can be assigned a probability weight (e.g., Affective 50%, Reactive 50% = send a notification only half the time).

**How the cycle works after this change:**
```
coordinated_send_and_inject():
  1. Read heuristic weights from experiment doc (MongoDB)
  2. Filter to active (weight > 0) heuristics
  3. Randomly select one heuristic according to its probability weight
  4. Call selected_heuristic.get_proactive_message(user)
  5. If Reactive selected (or all heuristics off) → skip this user (no notification)
  6. Otherwise: inject + FCM send (same as current)
```

**Relevant files:**
- `logic-python/services/research_service.py` — `coordinated_send_and_inject()`: replace priority chain with probability selector
- `Lexi/server/src/models/ExperimentsModel.ts` — add `heuristicWeights` field to `proactiveSettings`
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx` — probability sliders (see Task 4.1)

---

#### 3.2 — Heuristic Class Architecture (Modularity)

Each heuristic becomes a **self-contained class** responsible for its own memory extraction and message generation. This follows agent-task specialization: one focused LLM call per task, not one large call that does everything at once.

**Base class (shared by all heuristics):**
```python
class BaseHeuristic:
    memory_prompt: str       # prompt for extracting this heuristic's relevant memories
    message_prompt: str      # prompt for generating the proactive message

    def __init__(self, user, llm_service, mongodb_client, prompts_from_db):
        # Load memory_prompt and message_prompt from DB (set by researcher in dashboard)
        # Fall back to hardcoded defaults if not set

    def create_memory(self) -> None:
        # Read recent conversations for this user
        # Call LLM with memory_prompt to extract relevant memories
        # Write extracted memories to the user's proactiveMemory in MongoDB
        # Mark analyzed messages so they are not re-processed next cycle

    def get_proactive_message(self) -> str | None:
        # Call self.create_memory() — always refresh before generating
        # Read unused memories from proactiveMemory (specific to this heuristic)
        # If memories exist: call LLM with message_prompt + best memory → personalized message
        # If no memories (cold start): call LLM with cold-start framing → generic but warm invite
        #   (LLM-generated, not a static string, so it varies each time)
        # Return the final message string
```

**Concrete classes — each overrides only what differs:**

| Class | Memory it extracts | MongoDB field | Message style |
|---|---|---|---|
| `AffectiveHeuristic` | Emotional expressions, personal struggles | `emotional_memories` (affective_score 1-10) | Empathetic check-in referencing the specific memory |
| `TemporalHeuristic` | Future events/plans the user mentioned | `future_mentions` (when_iso) | Timely reminder or excited question about the event |
| `BehaviouralGapHeuristic` | Stated intentions not followed up | `open_intents` (stated_at) | Gentle follow-up: "Did you end up doing X?" |
| `GenericHeuristic` | None (no memory needed) | — | Neutral, emotionless chat invitation |

**Important:** All classes use `llm_service.py` (the existing `ProactiveLogic` class and its `_call_llm()`) for every LLM call. No LLM calls live directly in the heuristic files — they pass prompts to the service.

**Relevant files:**
- `logic-python/heuristics/affective.py` — refactor to class
- `logic-python/heuristics/temporal.py` — refactor to class
- `logic-python/heuristics/behavioural_gap.py` — refactor to class
- `logic-python/heuristics/generic.py` — **create new file**
- `logic-python/heuristics/base_heuristic.py` — **create new base class file**
- `logic-python/services/llm_service.py` — `_call_llm()` remains the single LLM dispatch point
- `logic-python/services/research_service.py` — `coordinated_send_and_inject()` calls `heuristic.get_proactive_message(user)`

---

### ✅ Task 4: Dashboard Wiring

**Goal:** Give the researcher full control over the proactive system from the admin UI. Every setting must flow from UI → MongoDB → Python code.

---

#### 4.1 — Heuristic On/Off Toggles & Probability Weights

The proactive settings modal must have one row per heuristic (Affective, Temporal, Behavioural Gap, Generic). Each row has:
- A toggle (on/off)
- A probability input (0–100) — only editable when toggled on
- The weights of all active heuristics must sum to 100% (UI enforces this with real-time feedback)

**UI must clearly state:** *"If all heuristics are turned off, the system enters Reactive mode — no notifications will be sent."*

**Data flow:** UI → `experiments.proactiveSettings.heuristicWeights` (MongoDB) → Python reads at cycle start.

**Relevant files:**
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`
- `Lexi/client/src/DAL/server-requests/experiments.ts`
- `Lexi/client/src/models/AppModels.ts`
- `Lexi/server/src/models/ExperimentsModel.ts` — add `heuristicWeights: { affective, temporal, behaviouralGap, generic }` to schema
- `Lexi/server/src/types/experiments.type.ts`

**✅ Implemented.**

---

#### 4.2 — Per-Heuristic Prompt Editor

Under each heuristic toggle in the UI, add two editable text fields:
- **Memory Prompt** — instructs the LLM on what to extract from conversations (maps to `memory_prompt` in the heuristic class)
- **Message Prompt** — instructs the LLM on what kind of proactive message to generate (maps to `message_prompt`)

Each field is pre-populated with the default prompt for that heuristic. A short description below each field explains what it controls. The researcher can edit to customize the heuristic's behavior without touching code.

**Data flow:** UI → `experiments.proactiveSettings.heuristicPrompts` (MongoDB) → read in `BaseHeuristic.__init__()` before each cycle.

**Relevant files:**
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`
- `Lexi/server/src/models/ExperimentsModel.ts` — add `heuristicPrompts` object to schema
- `logic-python/heuristics/base_heuristic.py` — `__init__()` reads prompts from experiment doc

**✅ Implemented.**

---

#### 4.3 — Scheduling: Days & Hours

Replace the current "interval in minutes" field with a proper schedule UI:
- **Allowed Days:** Day-range picker (e.g., Mon–Thu). Multiple non-consecutive ranges allowed.
- **Notification Times:** Choose between:
  - **Exact times** — researcher specifies 1–3 fixed times (e.g., 13:00, 17:30, 21:00)
  - **Random window** — researcher sets a time range (e.g., 12:00–14:00) and the system fires once at a random minute within that window each cycle

**Data flow:** UI → `experiments.proactiveSettings.schedule` (MongoDB) → `scheduler.py` reads at startup.

**Relevant files:**
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`
- `Lexi/server/src/models/ExperimentsModel.ts` — add `schedule: { allowedDays, fireTimes, randomWindows }` to schema
- `logic-python/scheduler.py` — read `schedule` from DB instead of hardcoded `FIRE_TIMES`

**✅ Implemented.** Day picker (Sun–Sat chips) + exact-times (up to 3) / random-window toggle, all saved to
`proactiveSettings.schedule`. `scheduler.py` registers one APScheduler job per (experiment, fire time / window)
at startup, gated by that experiment's own allowed days (`day_of_week` cron filter); random windows use
APScheduler's `jitter` to fire once at a random minute inside the window. `coordinated_send_and_inject()` also
re-checks the user's own experiment's allowed days every cycle as a per-user safety net (see 4.5).

---

#### 4.4 — Scheduler Validation & Cleanup

- Connect `scheduler.py` to MongoDB so `FIRE_TIMES` and allowed days are read from the experiment doc at startup (not hardcoded).
- Validate `run_cycle.py` works correctly as the Render entry point.
- **Remove** all references to "Render Cron" from comments and documentation — the scheduling is managed by `scheduler.py` running as a persistent service.

**Relevant files:**
- `logic-python/scheduler.py`
- `logic-python/run_cycle.py`

**✅ Implemented.** `scheduler.py` now reads schedules from MongoDB at startup (falls back to a hardcoded
default only if MongoDB is unreachable or nothing is configured yet). `run_cycle.py` is repurposed as a
manual/testing one-shot trigger; all "Render Cron" wording removed from both files.

---

#### 4.5 — Verify MongoDB Wiring for Heuristic Config

Confirm that `coordinated_send_and_inject()` correctly reads the live values from MongoDB on every cycle:
- Heuristic weights (on/off + probability)
- Heuristic prompts (memory prompt + message prompt)
- Schedule settings

Write a simple validation log at cycle start: print the active heuristics and their weights so it is visible in Render logs.

**Relevant files:**
- `logic-python/services/research_service.py`
- `logic-python/utils/mongodb_client.py`

**✅ Implemented.** `_load_experiment_settings()` now also returns `schedule`, logged per-user alongside
active weights and whether custom prompts are set. A new `_is_today_allowed()` check skips the user if today
isn't in their experiment's allowed days. The cycle-start banner documents that weights, prompts, and schedule
are all read live from MongoDB.

---

#### 4.6 — LLM Model Selector (including Claude)

The dashboard already has an LLM model selector. Validate end-to-end:
- API key for the selected provider (OpenAI / Anthropic) is correctly loaded from environment variables.
- `llm_service.override_model()` is called at cycle start with the model from the experiment doc.
- Add a clear explanation in the UI **next to the model selector**: *"This controls which AI model generates all proactive notifications for this experiment. Changing this affects message quality, cost, and generation style."*

**Relevant files:**
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx` — add tooltip/description
- `logic-python/services/llm_service.py` — `override_model()`, `_call_llm()`
- `logic-python/services/research_service.py` — where `override_model()` is called

**✅ Implemented.**

---

#### 4.7 — Heuristic Descriptions in the UI

Each heuristic toggle in the dashboard should have a short, plain-language description that mirrors what the code actually does. Suggested text:

- **Generic:** *"Sends a simple, friendly invitation to chat — no emotional framing, no specific topic. Used as a control condition or baseline."*
- **Temporal:** *"Detects when the user has mentioned an upcoming event or plan. Sends a timely message asking how they're preparing or how it went."*
- **Behavioural Gap:** *"Notices when the user stated an intention (e.g., 'I'll go to the gym tomorrow') but hasn't mentioned it since. Sends a gentle follow-up to check in."*
- **Affective:** *"Scans the user's recent conversations for emotional content (stress, sadness, joy). When emotional expressions are found, sends a warm, personalized check-in referencing what the user shared."*

**Relevant files:**
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`

**✅ Implemented.** Display order updated to generic → temporal → behavioural gap → affective.

---

### ✅ Task 5: Bugs & Cleanup

---

#### 5.1 — Remove Candidate Pool Entirely

The topic-based candidate pool (`build_candidate_pool`, `select_message_for_user`, `MAX_CANDIDATES`, `BLOCK_LAST_N_TOPICS`) is no longer needed. Every message now comes from a heuristic class. If no heuristic is active (all off or Reactive selected), no notification is sent.

**Changes:**
- Delete `build_candidate_pool()` from `research_service.py`
- Delete `select_message_for_user()` from `research_service.py`
- Remove `MAX_CANDIDATES`, `BLOCK_LAST_N_TOPICS` constants
- Remove the `candidates` parameter from `coordinated_send_and_inject()` and `run_full_proactive_cycle()`
- Remove the topic fallback branch from `_resolve_message()`
- Delete `generate_topic_message()` from `llm_service.py` (now unused)

**Relevant files:**
- `logic-python/services/research_service.py`
- `logic-python/services/llm_service.py`

**✅ Implemented.** Also removed the now-unreachable Phase-1 experiment helpers that only the candidate pool
fed into (`_resolve_message()`, `_personalize_context()`, `_generate_affective_default_message()`,
`_build_generic_message()`, `build_basic_memory()`, `extract_conversation_memory()`, `save_user_memory()`),
plus the now-unused `NudgeContext`/`DecisionResult` dataclasses in `core/models.py`.

---

#### 5.2 — Clean Each Heuristic to Its Single Responsibility

Each heuristic's `create_memory()` must extract **only** what it needs and nothing else. Remove all stale fields and the two-step scan-then-fire pattern (which will be gone after Task 3.2).

**Affective (`affective.py`):**
- `create_memory()` extracts: `emotional_memories` — list of `{ content, affective_score (1-10), timestamp_iso, used: false }`
- Remove: `pending_affective_followup`, `last_affective_analyzed_msg_count`, `analyze_and_schedule()`, `evaluate()` (all replaced by the class pattern)

**Temporal (`temporal.py`):**
- `create_memory()` extracts: `future_mentions` — list of `{ text, when_iso }`
- Remove: `fired_temporal_mentions`, `mark_fired()`, `evaluate()` (replaced by class pattern)

**Behavioural Gap (`behavioural_gap.py`):**
- `create_memory()` extracts: `open_intents` — list of `{ intent, stated_at, checked: false }`
- Remove: `pending_gap_followup`, `last_intent_scan_conversation_id`, `scan_for_gaps()`, `evaluate()` (replaced by class pattern)
- `clear_followup()` is kept — it is still called from `BehaviouralGapHeuristic.clear_after_send()`

**Note:** The `proactiveMemory` document structure in MongoDB should also be reviewed after this change to remove fields that are no longer written.

**Relevant files:**
- `logic-python/heuristics/affective.py`
- `logic-python/heuristics/temporal.py`
- `logic-python/heuristics/behavioural_gap.py`
- `logic-python/services/llm_service.py` — remove `analyze_conversation_emotion()`, `extract_stated_intents()`, `_tag_future_mentions()`, `extract_user_memory()`, `personalize_from_context()`, `generate_topic_message()` (all replaced by per-class LLM calls). `check_intent_completion()` is **kept** — it's still called live from `BehaviouralGapHeuristic.create_memory()`.

**✅ Implemented.** `affective.py`'s module-level `evaluate()`/`analyze_and_schedule()`/`AffectiveNudge` and its
now-vestigial `clear_followup()` were removed — nothing writes `pending_affective_followup` anymore (memories
are marked `used` the instant they're selected), so `AffectiveHeuristic` has no `clear_after_send()` override
and simply inherits the base no-op. `temporal.py` and `behavioural_gap.py` had their module-level `evaluate()`
and dataclasses (`TemporalNudge`, `GapNudge`) removed, keeping `mark_fired()` / `clear_followup()` since those
classes' `clear_after_send()` still calls them.

---

### ⬜ Task 6: System Hardening & Architectural Refinement

---

#### 6.1 — Experiment-Level Group Assignment

**Goal:** Remove the user-level A/B group (`proactiveGroup`) entirely. Proactive behavior is defined exclusively by the experiment's `heuristicWeights` — no user document should carry a type override.

**Current state:** `users.service.ts` randomly assigns every new user to `'affective' | 'generic' | 'reactive'`. `get_all_proactive_users()` filters on `"proactiveGroup": {"$ne": "reactive"}`. `coordinated_send_and_inject()` reads `user.proactiveGroup` and passes it to `log_proactive_event()`.

**Changes required:**
- `Lexi/server/src/services/users.service.ts` — Delete the 3-line random group assignment block (~lines 38–40). Remove `proactiveGroup` from the `UsersModel.create(...)` call.
- `Lexi/server/src/models/UsersModel.ts` — Change `proactiveGroup` to optional (`required: false`). **Do not delete the field** — existing user docs in MongoDB still carry it and must not break reads.
- `Lexi/server/src/types/users.type.ts` — Confirm `proactiveGroup?` is already optional.
- `logic-python/services/research_service.py` → `get_all_proactive_users()`: Remove `"proactiveGroup": {"$ne": "reactive"}` filter. The Reactive gate is enforced exclusively by `_select_heuristic()`.
- `logic-python/services/research_service.py` → `coordinated_send_and_inject()`: Remove `proactive_group = user.get('proactiveGroup', 'generic')`. Derive `experiment_type` from the dominant heuristic weight (key with highest non-reactive weight) and pass to `log_proactive_event()`.
- `logic-python/services/research_service.py` → `log_proactive_event()`: Rename `proactive_group` → `experiment_type`.

**Data flow:**
```
Experiment doc (heuristicWeights) → _select_heuristic() → heuristic class → message sent
                                                                           ↓
                                                             log_proactive_event(experiment_type=dominant_key)
```

---

#### 6.2 — Uniform Heuristic Fallbacks

**Goal:** Every heuristic that can be selected must always return a message. No heuristic may silently return `None` when selected — this corrupts the researcher's intended probability distribution.

**Current state:** `AffectiveHeuristic` and `GenericHeuristic` already guarantee a message. `TemporalHeuristic.get_proactive_message()` returns `None` when no event is in the 6–24 h window. `BehaviouralGapHeuristic.get_proactive_message()` returns `None` when no `pending_gap_followup` exists.

**Changes required:**
- `logic-python/heuristics/base_heuristic.py` → `BaseHeuristic`: Add shared helper `_cold_start_message(prompt, static_fallback, user_content=None) -> str` that encapsulates the LLM call + static-string fallback pattern (DRY).
- `logic-python/heuristics/temporal.py` → `TemporalHeuristic`: Add `_COLD_START_PROMPT` class attribute. Replace `return None` (when `not self._fired_nudge`) with a cold-start LLM call via `_cold_start_message()`, static fallback: `f"Hi {self.name}, anything exciting coming up soon?"`. Log: `🕐 [{username}] Temporal cold-start — no event in window`.
- `logic-python/heuristics/behavioural_gap.py` → `BehaviouralGapHeuristic`: Add `_COLD_START_PROMPT`. Replace all `return None` guards with cold-start fallback, static fallback: `f"Hi {self.name}, how have you been doing with your plans lately?"`. Log: `🔍 [{username}] Gap cold-start — no pending followup`.
- `logic-python/services/research_service.py` → `_run_selected_heuristic()`: Update the `if not text` guard to emit `❌ UNEXPECTED: {selected} returned None after fallback`.

**Integration note:** `BaseHeuristic` already exposes `self.name` and `self._target_lang`; cold-start prompts use both.

---

#### 6.3 — Language Preference Fix

**Goal:** Proactive notifications must be sent in the user's preferred language, consistently, via a single authoritative cascade.

**Current state:** `BaseHeuristic.__init__` reads only `user.proactiveMemory.preferred_language`, defaulting to `"he"`. New users silently default to Hebrew regardless of their actual preference.

**Changes required:**
- `logic-python/heuristics/base_heuristic.py` → `BaseHeuristic.__init__()`: Implement a 3-level language cascade: (1) `proactiveMemory.preferred_language`, (2) `user.language` top-level field, (3) `default_language` param from experiment settings, (4) hardcoded `"he"`. Add `default_language: str = "he"` to `__init__` signature. Log: `🌐 [{username}] Language resolved: {self.language}`.
- `logic-python/services/research_service.py` → `_load_experiment_settings()`: Read `ps.get("defaultLanguage", "he")` and return it as the 6th element of the return tuple.
- `logic-python/services/research_service.py` → `_run_selected_heuristic()`: Add `default_language` parameter; pass to all heuristic constructors.
- `logic-python/services/research_service.py` → `coordinated_send_and_inject()`: Remove the standalone `language = existing_pm.get(...)` line — language is now fully owned by `BaseHeuristic`.
- `Lexi/server/src/models/ExperimentsModel.ts` → `proactiveSettings`: Add `defaultLanguage: { type: String, default: 'he' }`.

**Data flow:**
```
user.proactiveMemory.preferred_language
  → user.language (top-level)
    → experiment.proactiveSettings.defaultLanguage
      → "he" (absolute last resort)
        → BaseHeuristic.self.language → _target_lang → {language} in prompts
```

---

#### 6.4 — Advanced Scheduling Flexibility

**Goal:** Allow unlimited exact fire times; let researchers specify how many notifications fire within a random window; display the active timezone on the UI.

**Current state:** `fireTimes` is capped at 3 by the UI. Random windows have no count field. Timezone is not displayed.

**Changes required:**

- `Lexi/server/src/models/ExperimentsModel.ts`: Extend `randomWindows` schema to include `count: { type: Number, default: 1 }`.
- `Lexi/client/src/models/AppModels.ts`: Update `RandomWindow` interface to `{ start: string; end: string; count: number }`.
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`:
  - Remove `prev.fireTimes.length >= 3` guard in `addFireTime()`. Change button label from `"+ Add time (up to 3)"` to `"+ Add time"`.
  - `setRandomWindow()`: extend to handle `count` field mutations.
  - Add count `TextField` (`type="number"`, min 1, max 20) next to each random window row.
  - Add static `Typography`: `Timezone: Asia/Jerusalem (Israel Standard Time / Israel Daylight Time)` below the schedule section. Non-editable.
- `logic-python/scheduler.py` → `register_jobs()`: For random-window mode, remove `[:3]` cap on exact times. For each window, register `count` separate APScheduler jobs, each with `jitter` so they fire at distinct random minutes within the window.

---

#### 6.5 — Prompt Safety & Separation

**Goal:** Researchers write only the persona/task portion of prompts. All structural formatting instructions live exclusively in the backend.

**Current state:** `DEFAULT_MEMORY_PROMPT` strings embed JSON schema instructions. If a researcher omits them while editing in the dashboard, the LLM returns malformed output and the cycle crashes on `json.loads()`.

**Changes required:**

- `logic-python/heuristics/base_heuristic.py` → `BaseHeuristic`: Add `STRUCTURAL_JSON_SUFFIX` and `STRUCTURAL_MESSAGE_SUFFIX` class constants. Add helpers `_safe_memory_prompt(prompt) -> str` and `_safe_message_prompt(prompt) -> str` that append the respective suffix.
- `logic-python/heuristics/affective.py`, `temporal.py`, `behavioural_gap.py`, `generic.py`:
  - `DEFAULT_MEMORY_PROMPT`: Remove `"Return ONLY valid JSON: ..."` lines — handled by `_safe_memory_prompt()`.
  - `DEFAULT_MESSAGE_PROMPT` and `_COLD_START_PROMPT`: Remove `"Return ONLY the final message..."` lines — handled by `_safe_message_prompt()`.
  - In `create_memory()`: wrap `self.memory_prompt` with `self._safe_memory_prompt(...)`.
  - In `get_proactive_message()`: wrap message system prompt with `self._safe_message_prompt(...)`.
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`:
  - Strip the structural `"Return ONLY..."` lines from `defaultMemoryPrompt` / `defaultMessagePrompt` in the `HEURISTICS` constant (so reset-to-defaults reflects the clean researcher-facing text).
  - Add helper text below Memory Prompt and Message Prompt `TextField`s: `"Write the persona and task instructions only. Formatting and output constraints are automatically added by the system."`

---

#### 6.6 — Independent Conversation Analysis

**Goal:** Each heuristic tracks which conversations it has processed using its own independent field. No heuristic's scan state can block another heuristic from reading the same conversation.

**Current state:** `BehaviouralGapHeuristic` uses a single `last_intent_scan_conversation_id` cursor — once it scans a conversation, that conversation is forever excluded even if new messages were added. No protection against future accidental cross-heuristic field writes.

**Changes required:**

- `logic-python/heuristics/behavioural_gap.py` → `BehaviouralGapHeuristic.create_memory()`:
  - Replace `last_intent_scan_conversation_id` (single cursor) with `gap_scanned_conversation_ids` (set of IDs). On each call: load the set, scan all recent conversations (last 3) whose IDs are NOT in the set, extract intents, then add their IDs using `$addToSet` (idempotent).
- `logic-python/heuristics/affective.py` → `AffectiveHeuristic.create_memory()`: Add comment that `last_affective_analyzed_msg_count` is private to this heuristic and must never be read or written by sibling heuristics.
- `logic-python/heuristics/temporal.py` → `TemporalHeuristic`: Add comment confirming independence (deduplicates by mention text, no shared scan cursor).
- `logic-python/heuristics/base_heuristic.py` → `BaseHeuristic` docstring: Add tracking field convention rule: *"Each subclass MUST use its own namespaced tracking field inside `proactiveMemory`. Prefix with the heuristic name (e.g., `affective_`, `gap_`, `temporal_`). Never read or write a sibling heuristic's tracking field."*

**MongoDB field rename (migration):** `last_intent_scan_conversation_id` → replaced by `gap_scanned_conversation_ids`. Existing documents with the old field are ignored (harmless). No migration script needed.

---

#### 6.7 — Metrics & Logging Organization

**Goal:** Every `proactive_logs` document contains sufficient structured data for thesis analysis without post-hoc joins.

**Current log schema (as-is):** `cycle_id`, `timestamp`, `user_id`, `trigger_source`, `generated_message`, `topic_label`, `status`, `notification_id`, `proactive_group`, `llm_response` (always `{}`).

**New fields to add:**

| Field | Type | Source | Analytical value |
|---|---|---|---|
| `experiment_id` | str | `user.experimentId` | Group logs by experiment |
| `experiment_type` | str | dominant heuristic key | Identify condition |
| `heuristic_selected` | str | selected name (explicit) | Frequency distribution |
| `was_fallback` | bool | `heuristic.used_fallback` | Measure cold-start rate |
| `memory_content` | str (≤120 chars) | `heuristic.memory_content` | Qualitative audit |
| `language` | str (`he`/`en`) | `heuristic.language` | Language distribution |
| `heuristic_weights_snapshot` | dict | active weights | Reproduce randomisation |
| `llm_model` | str | `experiment_llm_model` | Cost/quality attribution |

**Changes required:**
- `logic-python/heuristics/base_heuristic.py` → `BaseHeuristic.__init__()`: Add `self.used_fallback: bool = False` and `self.memory_content: str = ""`.
- `logic-python/heuristics/affective.py`, `temporal.py`, `behavioural_gap.py`, `generic.py`: In `get_proactive_message()`: set `self.used_fallback = True` on cold-start path; `self.memory_content = content[:120]` when a specific memory is selected.
- `logic-python/services/research_service.py` → `_run_selected_heuristic()`: After `h.get_proactive_message()`, read `h.used_fallback`, `h.memory_content`, `h.language` and add to returned message dict.
- `logic-python/services/research_service.py` → `log_proactive_event()`: Extend signature and log entry with all new fields.
- `logic-python/services/research_service.py` → `coordinated_send_and_inject()`: Pass `experiment_id`, `heuristic_weights`, `llm_model` to `log_proactive_event()`.

**Deducible metrics for thesis:**
- Heuristic selection frequency (GROUP BY `heuristic_selected`)
- Cold-start rate per heuristic (WHERE `was_fallback = true`)
- Notification volume per user per day (GROUP BY `user_id, date(timestamp)`)
- Language distribution (GROUP BY `language`)
- LLM model cost attribution (GROUP BY `llm_model`)
- Delivery success rate (WHERE `status = "sent"` / total)

---

#### 6.8 — Dashboard Control for Daily Notification Limit

**Goal:** Remove `MAX_DAILY_NOTIFICATIONS = 999` hardcoded constant; give the researcher full control from the dashboard.

**Current state:** `research_service.py` line 13: `MAX_DAILY_NOTIFICATIONS = 999`, read in `get_proactive_users_with_rate_limit()`.

**Changes required:**
- `Lexi/server/src/models/ExperimentsModel.ts` → `proactiveSettings`: Add `maxDailyNotifications: { type: Number, default: 3 }`.
- `Lexi/client/src/models/AppModels.ts` → `proactiveSettings`: Add `maxDailyNotifications?: number`.
- `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx`: Add `TextField` (`type="number"`, min 1) labelled `"Max notifications per user per day"` below the schedule section. Initialize from `ps.maxDailyNotifications ?? 3`. Include in `handleSave()`.
- `logic-python/services/research_service.py`:
  - Delete `MAX_DAILY_NOTIFICATIONS = 999`.
  - `_load_experiment_settings()`: Read `ps.get("maxDailyNotifications", 3)`, return as 5th element of tuple.
  - `get_proactive_users_with_rate_limit()`: Cache per-experiment caps by experiment ID. Load cap from `_load_experiment_settings()` per experiment (not per user). Use per-experiment cap instead of the removed constant. Restructure the loop to open/close a connection per-user (avoids conflict with `_load_experiment_settings()`'s own connection lifecycle).

**Data flow:**
```
Dashboard (maxDailyNotifications) → MongoDB (proactiveSettings.maxDailyNotifications)
  → _load_experiment_settings() [5th return value]
    → get_proactive_users_with_rate_limit() [per-experiment cap]
      → daily_count >= cap → skip
```

---




































### ⬜ Task 7: Data Logging & Questionnaires

**Goal:** Ensure comprehensive tracking of all interactions for thesis analysis. Verify the app correctly serves the selected pre/post-experiment questionnaires.

**Relevant files:**
- **Data logging — server:**
  - `Lexi/server/src/models/ConversationsModel.ts`
  - `Lexi/server/src/models/MetadataConversationsModel.ts`
  - `Lexi/server/src/services/dataAggregation.service.ts`
  - `Lexi/server/src/controllers/dataAggregationController.controller.ts`
  - `Lexi/server/src/routers/dataAggregationRouter.router.ts`
- **Data logging — Python:**
  - `logic-python/services/research_service.py` — writes to `proactive_logs` (trigger source, message, group, heuristic, probability used)
  - `logic-python/utils/mongodb_client.py`
- **Data logging — client:**
  - `Lexi/client/src/screens/Admin/components/data-panel/DataPanel.tsx`
  - `Lexi/client/src/DAL/server-requests/dataAggregation.ts`
  - `Lexi/client/src/screens/Chat/components/UserAnnotation.tsx`
- **Questionnaires — server:**
  - `Lexi/server/src/models/FormsModel.ts`
  - `Lexi/server/src/services/forms.service.ts`
  - `Lexi/server/src/controllers/formsController.ts`
  - `Lexi/server/src/routers/formsRouter.ts`
  - `Lexi/server/src/types/forms.type.ts`
- **Questionnaires — client:**
  - `Lexi/client/src/screens/Chat/ChatPage.tsx`
  - `Lexi/client/src/components/forms/conversation-form/ConversationForm.tsx`
  - `Lexi/client/src/screens/Chat/components/side-bar-chat/SideBarChat.tsx`
  - `Lexi/client/src/screens/Admin/components/forms-panel/FormsPanel.tsx`
  - `Lexi/client/src/screens/Admin/components/forms-panel/create-form/CreateForm.tsx`
  - `Lexi/client/src/components/questions/Question.tsx`
  - `Lexi/client/src/DAL/server-requests/forms.ts`

---

### ⬜ Task 8: Repository Cleanup

**Goal:** Rename project, update UI screenshots, move `AI Guidelines` and similar files to `.gitignore`.

- Rename GitHub repository appropriately
- Add updated UI screenshots to README
- Add `AI Guidelines`, local dev notes, and similar files to `.gitignore`

---

<!-- Phase 2: EIF CogAI 2026 Oxford Demo (Branch: oxford-demo) — COMPLETE, branch archived -->
