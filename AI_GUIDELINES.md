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
- Python proactive engine
- MongoDB

Always consider how changes affect all components.


- Do NOT refactor unrelated code
- Do NOT add new features unless asked
- Do NOT rewrite files completely
- Do NOT change naming conventions


Current Task:

Phase 3.4 is fully complete. Awaiting user direction on the next phase.

Phase 3 status:
- 3.1 ✅ tie isProactive to experiment settings
- 3.2 ✅ scheduling + time window
- 3.3 ✅ candidate message pool
- 3.4a ✅ basic memory (demographics + recent sent topics)
- 3.4b ✅ LLM extraction (interests / future_mentions / insight / language)
- 3.4c ✅ persist proactiveMemory to the user document in MongoDB
- 3.4d ✅ memory-aware per-user message generation (personalize_message_for_user)

Likely next options (ask the user):
- Phase 4 — Researcher dashboard enhancements (proactive settings UI, APK download, etc.)
- Phase 3 deferred B — Engagement tracking (per-user response-time learning)
- Phase 5 — FCM → Conversation Deep-Link (UX polish)

See PLAN.md sections 3.4 (full spec) and 4 / 5 / Phase B for what each next step entails.


Project Context:

See PROJECT_PLAN.md for full system architecture, roadmap, known bugs, and current state.

Use it only as reference.
Do NOT try to implement multiple phases at once.
Always focus only on the current task defined above.


If you break any of these rules, stop and explain why.