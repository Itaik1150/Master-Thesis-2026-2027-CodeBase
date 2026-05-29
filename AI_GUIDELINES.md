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


Current Phase: Phase 4 — Heuristics Engine & Final UX (June Sprint)

Phase 3 is fully complete:
- 3.1 ✅ tie isProactive to experiment settings
- 3.2 ✅ scheduling + time window (scheduler.py daemon)
- 3.3 ✅ candidate message pool (4–6 topic/news candidates per cycle)
- 3.4a ✅ basic memory (demographics + recent sent topics)
- 3.4b ✅ LLM extraction (interests / future_mentions / insight / language)
- 3.4c ✅ persist proactiveMemory to MongoDB
- 3.4d ✅ memory-aware per-user message generation (personalize_message_for_user)

Phase 4 task order (work top-to-bottom, one task at a time):
- 4.1 ✅ Deprecate news_service.py — deleted news_service.py + 2 test files; stripped headline methods from research_service.py; renamed original_headline → trigger_source in candidate dicts and proactive_logs
- 4.2 ✅ Upgrade LLM — gpt-3.5-turbo replaced with gpt-4o default; LLM_PROVIDER + LLM_MODEL env vars added; _call_llm() abstraction routes to OpenAI or Anthropic; all 4 ProactiveLogic methods unified through it
- 4.3 ✅ Temporal Heuristic — heuristics/temporal.py created; evaluate() checks future_mentions within 6–24h window; mark_fired() stamps fired_temporal_mentions in MongoDB; integrated into coordinated_send_and_inject before topic-pool path
- 4.4 ✅ Affective Heuristic — heuristics/affective.py created; analyze_conversation_emotion() added to llm_service.py; analyze_and_schedule() reads last finished conversation and stores pending_affective_followup; evaluate() fires if scheduled time has passed; clear_followup() removes it after send; priority: affective → temporal → topic
- 4.5 ✅ Behavioural Gap Heuristic — heuristics/behavioural_gap.py created; scan_for_gaps() extracts stated_intents via LLM and checks completion after 24–48h; evaluate() fires pending_gap_followup; clear_followup() removes it after send; extract_stated_intents() + check_intent_completion() added to llm_service.py; priority chain: affective → gap → temporal → topic; trigger_source="behavioural_gap"
- 4.6 ✅ High-intensity Android notifications — lexi_nudges_v2 channel (IMPORTANCE_HIGH); setFullScreenIntent wakes screen over lock; USE_FULL_SCREEN_INTENT permission + showWhenLocked + turnScreenOn in manifest; unique notificationId per nudge; BigTextStyle for long messages; app icon replaces system placeholder
- 4.7 ✅ Dashboard heuristic toggles + prompt tuning — proactiveSettings extended (heuristics.{temporal,affective,behaviouralGap} + llmModel); ProactiveSettingsModal.tsx updated with checkboxes + model dropdown; heuristics gated in research_service.py per experiment; "Cambridge" → "Ben-Gurion University (BGU)" replaced in all prompts + UI copy
- 4.8 ✅ Deferred Deep Linking onboarding — one generic APK for all experiments; web landing page GET /join/:experimentId (served by Node.js) with "Download & Join" button; download logs {ip, experimentId, timestamp} to apk_sessions collection; GET /experiments/match-session endpoint matches device IP to recent log (15-min window, FIFO); Android MainActivity calls match-session on first launch, saves experimentId to SharedPreferences; dashboard ProactiveSettingsModal shows web join URL instead of lexi:// deep link; APK_DOWNLOAD_URL env var points to hosted static APK
- 4.9 💡 Stretch: Google Calendar OAuth for Temporal heuristic; logo refresh; auto-generated documentation

Key architectural constraints for Phase 4:
- news_service.py is DEPRECATED. Do not add any new calls to it.
- The primary LLM will be GPT-4o or Claude 3.5 Sonnet. Do not use gpt-3.5-turbo for new code.
- All proactive_logs entries must include trigger_source ∈ {temporal, affective, gap, topic}.
- Each heuristic lives in its own module under logic-python/heuristics/. Do not put heuristic logic directly into research_service.py.
- Heuristics must be gated by experiment.experimentFeatures.proactiveSettings.heuristics[name] (added in 4.7). Until 4.7 is done, treat them as always-enabled.
- Institution name in ALL system prompts is "Ben-Gurion University (BGU)", not "Cambridge".


Project Context:

See PLAN.md for full system architecture, roadmap, known bugs, and current state.
Focus on Phase 4 tasks only. Do NOT implement Phase 5 or later unless explicitly asked.
Do NOT try to implement multiple Phase 4 tasks at once.


If you break any of these rules, stop and explain why.