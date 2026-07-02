# Lexi - Final Execution Plan & Working Document

## Phase 1: Core System Tuning & Logic (Run on `main` branch)


**Task 1: A/B Testing Group Assignment**
    * **Goal:** Dynamically assign new users to one of 3 groups (Affective Proactive, Generic Proactive, Reactive). The system must log this assignment and read it to determine notification behavior. Replace old generic topics with the new Generic Proactive group.
    * *Group 1 (Affective Proactive):* Emotional, personal notifications (acts like a listening ear/journaling prompt to increase emotional sharing).
    * *Group 2 (Generic Proactive):* Random, generic notifications inviting the user to chat. (Note: Replace the old generic topic triggers with this group).
    * *Group 3 (Reactive):* No proactive notifications at all.

   **Upgrade Affective Proactive (Group 1) Logic (Crucial):**
     * **Memory Extraction Update:** Modify the memory extraction logic (which analyzes recent conversations) to explicitly detect and flag emotional expressions or sensitive topics with a `sensitivity_score` (e.g., 1-10).
     * **Cold Start (No/Low Data):** When no high-sensitivity memories exist, the LLM must generate a gentle, emotionally inviting prompt that includes the user's name (e.g., "Hi [Name], just checking in. I'm here if you need a listening ear today.").
     * **Context-Rich (With Data):** Once sensitive memories are accumulated, the LLM must use the highest `sensitivity_score` topics to craft a highly personalized, relevant, and empathetic emotional check-in, rather than a generic prompt.
  3. Replace the old generic topics with the new Generic Proactive group (Group 2), and ensure the Reactive group (Group 3) receives zero notifications.
* **Relevant Files:**
  * **Server — group assignment & user model:**
    * `Lexi/server/src/services/experiments.service.ts` — `getActiveAgent()`: the existing random A/B agent-assignment logic to extend to 3 groups
    * `Lexi/server/src/services/users.service.ts` — assigns agent to user at registration
    * `Lexi/server/src/controllers/usersController.controller.ts` — registration endpoint that triggers agent assignment
    * `Lexi/server/src/models/UsersModel.ts` — user schema (stores assigned agent / group)
    * `Lexi/server/src/models/ExperimentsModel.ts` — experiment schema (A/B agents, proactive settings)
    * `Lexi/server/src/types/experiments.type.ts` — `ABAgents`, `agentsMode`, `abAgents` types
    * `Lexi/server/src/types/common.type.ts` — `AgentsMode` enum (`Single` / `A/B`)
  * **Python — reads group, gates & personalizes notifications:**
    * `logic-python/services/research_service.py` — main orchestrator: reads user's assigned agent/group, skips Reactive users, branches logic for Affective vs Generic
    * `logic-python/services/llm_service.py` — `extract_user_memory()` (add `sensitivity_score`), `personalize_message_for_user()` (cold-start vs context-rich branching)
    * `logic-python/core/models.py` — Python data models (extend to hold `sensitivity_score`)
    * `logic-python/scheduler.py` — entry point for scheduled cycle
  * **Admin UI — configure the 3 agents:**
    * `Lexi/client/src/screens/Admin/components/agents-panel/active-agents/AbAgents.tsx` — A/B agent distribution config UI
    * `Lexi/client/src/screens/Admin/components/agents-panel/agent-form/AgentForm.tsx` — create/edit each agent (group 1, 2, 3)
    * `Lexi/client/src/screens/Admin/components/experiments-panel/ExperimentForm.tsx` — experiment-level agent mode selection

**Task 2: System Prompt Sanitization & Strict Emotional Framing**
* **Goal:** 1. **Audit & Sanitize:** Locate the exact system prompts sent to the LLM. Strictly remove any instructions or context that mention this is an "experiment", a "research study", or a "thesis". The LLM must act completely natural.
  2. **Strict Emotional Focus (Group 1 - Affective):** * Explicitly define the persona in the prompt: "You are an empathetic agent that encourages emotional sharing." 
     * **Crucial Rule:** Proactive notifications must NO LONGER be based on general user insights (e.g., hobbies, work). They must be generated STRICTLY based on emotional memories and the `sensitivity_score`.
     * Instruct the LLM: "Analyze the user's emotional memories to find the personal emotional focus that needs to be raised in the next conversation." 
     * Cold Start: If no emotional memory exists, fall back to a warm, gentle invitation purely focused on emotional sharing (e.g., "Hi [Name], how are you feeling today?").
  3. **Group 2 Prompt (Generic):** Instruct the LLM to act as a standard assistant generating a completely generic, standard invitation to chat, with zero emotional weight and no specific topics.
* **Relevant Files:**
  * `logic-python/services/llm_service.py` — Primary target. Contains the strings sent to the LLM for proactive generation.
  * `logic-python/services/research_service.py` — Calls `llm_service` and passes framing context.
  * `Lexi/server/src/models/AgentsModel.ts` — In-chat persona prompt fields (if in-chat behavior needs to match).
  * `Lexi/server/src/services/conversations.service.ts` — Assembles the in-chat system prompt.

**Task 4: Dashboard Wiring**
* **Goal:** Connect React UI to backend logic. Add toggles for heuristics, input fields for allowed notification hours - Restrict firing days to Monday–Thursday only. Set timezone to CET (Central European Time), and ensure the UI LLM selector overrides codebase defaults. 
* **Relevant Files:**
  * **React UI (proactive settings modal):**
    * `Lexi/client/src/screens/Admin/components/experiments-panel/ProactiveSettingsModal.tsx` — heuristic toggles, LLM model selector, notification-hours input; primary UI file to extend
    * `Lexi/client/src/DAL/server-requests/experiments.ts` — client API calls to persist proactive settings
    * `Lexi/client/src/models/AppModels.ts` — client-side experiment type (add new fields)
  * **Server — schema & API:**
    * `Lexi/server/src/models/ExperimentsModel.ts` — `experimentFeatures.proactiveSettings` schema; add `allowedHours`, `allowedDays` fields
    * `Lexi/server/src/types/experiments.type.ts` — TypeScript types for the new fields
    * `Lexi/server/src/controllers/experimentsController.controller.ts` — experiment CRUD endpoints
    * `Lexi/server/src/services/experiments.service.ts` — experiment business logic
  * **Python — reads settings at runtime:**
    * `logic-python/scheduler.py` — `FIRE_TIMES` list and timezone (`Jerusalem` → change to `CET`); restrict to Mon–Thu here
    * `logic-python/services/research_service.py` — reads `proactiveSettings` from experiment doc to respect `allowedHours`, `allowedDays`, and `llmModel` override

**Task 5: Data Logging & Questionnaires**
* **Goal:** Ensure comprehensive tracking of all interactions for thesis analysis. Verify the app correctly serves the selected pre/post-experiment questionnaires.
* **Relevant Files:**
  * **Data logging — server:**
    * `Lexi/server/src/models/ConversationsModel.ts` — message storage schema
    * `Lexi/server/src/models/MetadataConversationsModel.ts` — conversation metadata (`userId`, `isFinished`, timestamps)
    * `Lexi/server/src/services/dataAggregation.service.ts` — data export / aggregation logic
    * `Lexi/server/src/controllers/dataAggregationController.controller.ts` — `/dataAggregation` API endpoints
    * `Lexi/server/src/routers/dataAggregationRouter.router.ts` — route registration
  * **Data logging — Python (proactive audit trail):**
    * `logic-python/services/research_service.py` — writes to `proactive_logs` collection (trigger source, message, status, group)
    * `logic-python/utils/mongodb_client.py` — Python MongoDB connection
  * **Data logging — client:**
    * `Lexi/client/src/screens/Admin/components/data-panel/DataPanel.tsx` — admin data download UI
    * `Lexi/client/src/DAL/server-requests/dataAggregation.ts` — client API for data export
    * `Lexi/client/src/screens/Chat/components/UserAnnotation.tsx` — user message annotations logged during chat
  * **Questionnaires — server:**
    * `Lexi/server/src/models/FormsModel.ts` — form/questionnaire MongoDB model
    * `Lexi/server/src/services/forms.service.ts` — form business logic
    * `Lexi/server/src/controllers/formsController.ts` — form API endpoints
    * `Lexi/server/src/routers/formsRouter.ts` — form routes
    * `Lexi/server/src/types/forms.type.ts` — form/question type definitions
  * **Questionnaires — client:**
    * `Lexi/client/src/screens/Chat/ChatPage.tsx` — triggers pre/post-conversation form flow
    * `Lexi/client/src/components/forms/conversation-form/ConversationForm.tsx` — pre/post-conversation questionnaire wrapper
    * `Lexi/client/src/screens/Chat/components/side-bar-chat/SideBarChat.tsx` — chat sidebar that manages form state
    * `Lexi/client/src/screens/Admin/components/forms-panel/FormsPanel.tsx` — admin questionnaire builder
    * `Lexi/client/src/screens/Admin/components/forms-panel/create-form/CreateForm.tsx` — create/edit form
    * `Lexi/client/src/components/questions/Question.tsx` — question renderer (dispatches to type-specific components)
    * `Lexi/client/src/components/questions/ScaleRadio.tsx` — Likert/scale question
    * `Lexi/client/src/components/questions/RadioSelection.tsx` — radio question
    * `Lexi/client/src/components/questions/BinaryRadioSelector.tsx` — yes/no question
    * `Lexi/client/src/components/questions/NumberInput.tsx` — numeric input question
    * `Lexi/client/src/components/questions/SelectionTextInput.tsx` — selection + text question
    * `Lexi/client/src/DAL/server-requests/forms.ts` — client form API calls


Phase 2: EIF CogAI 2026 Oxford Demo (Branch: oxford-demo)
Specifically designed for the EIF CogAI 2026 conference presentation on June 25-26.

Note: This phase will be executed on a separate Git branch to avoid polluting the main thesis logic.

Step 2.1: Environment Setup & Abstraction
Action: Create a new branch git checkout -b oxford-demo.

Goal: Isolation. In this branch, we will disable the original scheduler.py and research_service.py logic, replacing them with a simplified "Demo Runner" that executes only the 3 predefined notifications.

Result: The system becomes deterministic and optimized for live demonstration.

Step 2.2: Hardcoding Notifications & Logic
Action: Create a simple run_demo_cycle() function in research_service.py.

Goal: Predefine the 3 notification sequence (e.g., triggered by timers: 30 seconds, 2 minutes, 5 minutes post-registration).

Result: Regardless of user input, the demo follows the specific conference "storyline."

Step 2.3: "Experiment Termination" (The Dead End)
Action: Add a database flag is_demo_finished.

Goal: Once the 3rd notification is fired, the system sets is_demo_finished: true for the user.

Result: The proactive loop effectively "dies" for that user, and the app triggers the final UI state.

Step 2.4: UI Update (Thank You & Contact Screen)
Action: Create a static React screen that displays when the app detects is_demo_finished: true.

Goal: Present the contact and project details to conference attendees:

Itai Kohn: itaikoh@post.bgu.ac.il | LinkedIn

Guy Laban: laban@bgu.ac.il

Lab Website: https://labalab.li/

GitHub Repo: https://github.com/Itaik1150/Master-Thesis-2026-2027-CodeBase


## Phase 3: Repository Cleanup
* **Goal:** Rename project, update UI screenshots, move `AI Guidelines` to `.gitignore`.
**GitHub Overhaul:** Rename the project appropriately, add updated UI screenshots, and move `AI Guidelines` and other similar files to `.gitignore`.