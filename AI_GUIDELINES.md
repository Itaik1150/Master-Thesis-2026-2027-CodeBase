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

3.4b — LLM conversation extraction (Phase 3 — Proactive Logic Improvements)

Goal: For each proactive user, fetch their recent conversation messages from MongoDB
(via metadata_conversations → conversations), then call the LLM once to extract:
- interests (list of topics the user cares about)
- future_mentions (events/plans they mentioned)
- conversation_insight (one sentence summarizing communication style + language)

Store these in a `proactiveMemory` dict to be merged with the basic memory from 3.4a.
See PLAN.md section 3.4b for the full spec.


Project Context:

See PROJECT_PLAN.md for full system architecture, roadmap, known bugs, and current state.

Use it only as reference.
Do NOT try to implement multiple phases at once.
Always focus only on the current task defined above.


If you break any of these rules, stop and explain why.