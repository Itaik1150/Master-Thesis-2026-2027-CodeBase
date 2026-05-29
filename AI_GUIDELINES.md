The goal is to develop and debug the Lexi proactive experiment system step-by-step.
Focus on understanding the system and making safe, minimal changes.

1. Do NOT make code changes immediately.

2. Always explain BEFORE editing:
   - What the current behavior is
   - What the problem is
   - Which files are involved
   - What minimal fix is proposed

3. Work on ONE issue at a time.
   Never jump between multiple bugs or features.

4. Prefer minimal changes over large refactors.

5. Do NOT assume things — verify using the actual code.

6. If something is unclear, ask questions instead of guessing.

7. Do NOT change architecture unless explicitly asked.


When debugging:

1. Trace the full flow step-by-step
2. Identify exactly where the data breaks
3. Show the exact line/file where the issue occurs
4. Explain why it fails
5. Propose the smallest fix possible
6. Wait for approval before implementing


After every fix:

1. Explain how to test it manually
2. Define "expected behavior"
3. Define "failure case"


The system consists of:
- Android app (WebView + FCM)
- Lexi Web (React + Node.js)
- Python proactive engine (heuristics engine — Temporal / Affective / Behavioural Gap)
- MongoDB

Always consider how changes affect all components.


- Do NOT refactor unrelated code
- Do NOT add new features unless asked
- Do NOT rewrite files completely
- Do NOT change naming conventions


Current Phase: Phase 6 complete — moving to Phase 7 / Phase 5 dashboard enhancements.

Phase 3 is fully complete:
- 3.1 ✅ tie isProactive to experiment settings
- 3.2 ✅ scheduling + time window (scheduler.py daemon)
- 3.3 ✅ candidate message pool (4–6 topic/news candidates per cycle)
- 3.4a ✅ basic memory (demographics + recent sent topics)
- 3.4b ✅ LLM extraction (interests / future_mentions / insight / language)
- 3.4c ✅ persist proactiveMemory to MongoDB
- 3.4d ✅ memory-aware per-user message generation (personalize_message_for_user)

Phase 4 — fully complete:
- 4.1 ✅ Deprecate news_service.py
- 4.2 ✅ Upgrade LLM (gpt-4o default; LLM_PROVIDER + LLM_MODEL env vars; _call_llm() abstraction)
- 4.3 ✅ Temporal Heuristic (heuristics/temporal.py; future_mentions window 6–24h)
- 4.4 ✅ Affective Heuristic (heuristics/affective.py; emotion detection; pending_affective_followup)
- 4.5 ✅ Behavioural Gap Heuristic (heuristics/behavioural_gap.py; stated_intents; 24–48h gap check)
- 4.6 ✅ High-intensity Android notifications (IMPORTANCE_HIGH; setFullScreenIntent; WakeLock)
- 4.7 ✅ Dashboard heuristic toggles + prompt tuning (proactiveSettings.heuristics + llmModel; BGU branding)
- 4.8 ✅ Deferred Deep Linking onboarding (generic APK; /join/:experimentId landing page; IP-based match-session)
- 4.9 💡 Stretch: Google Calendar OAuth; logo refresh; auto-generated documentation

Phase 5 — pending (dashboard enhancements):
- 5.1 ⬜ Proactive settings UI: schedule picker, notification log table, test-push button

Phase 6 — fully complete (FCM → conversation deep-link):
- 6.1 ✅ Python pre-creates conversation via POST /conversations/create before sending FCM
- 6.2 ✅ conversationId + experimentId embedded in FCM data payload (fcm_service.py extra_data)
- 6.3 ✅ LexiMessagingService.kt extracts deep-link URL from FCM data; passes as intent extra
- 6.4 ✅ MainActivity handles deepLinkUrl in onCreate (cold tap) and onNewIntent (app running)
- 6.5 ✅ LoginForm + RegisterForm read ?returnTo= param and redirect to conversation after login
- 6.6 ✅ WebView third-party cookies enabled (setAcceptThirdPartyCookies) — session persists across launches
- 6.7 ✅ Auth cookie extended from 24h to 30 days — participants stay logged in throughout experiment
- 6.8 ✅ isProactive flag bidirectional sync: toggling experiment proactive ON/OFF auto-updates all users
- 6.9 ✅ Python cycle self-heals isProactive=true for users missing the field; respects explicit false

Key architectural constraints:
- news_service.py is DEPRECATED. Do not add any new calls to it.
- The primary LLM is GPT-4o or Claude 3.5 Sonnet. Do not use gpt-3.5-turbo for new code.
- All proactive_logs entries must include trigger_source ∈ {temporal, affective, gap, topic}.
- Each heuristic lives in its own module under logic-python/heuristics/.
- Heuristics are gated by experiment.experimentFeatures.proactiveSettings.heuristics[name].
- Institution name in ALL system prompts is "Ben-Gurion University (BGU)", not "Cambridge".
- Android APK versionCode is currently 5 / versionName 1.4.
- Auth cookie maxAge is 30 days (usersController.controller.ts).

Project Context:

See PLAN.md for full system architecture, roadmap, known bugs, and current state.
Next work: Phase 5 dashboard enhancements OR Phase 7 quality/analytics.
Do NOT try to implement multiple tasks at once.


If you break any of these rules, stop and explain why.