# AI Guidelines — Lexi Proactive Research Platform

Instructions for AI assistants working in this repository.

---

## Working rules

1. **Do not change code immediately.** Explain current behavior, the problem, involved files, and a minimal proposed fix first.
2. **One issue at a time.** Do not mix unrelated bugs or features in one change.
3. **Prefer minimal diffs.** Match existing naming, types, and patterns.
4. **Verify in code.** Do not assume behavior — read the actual implementation.
5. **Ask when unclear.** Do not guess architecture or data shapes.
6. **No architecture changes** unless explicitly requested.

---

## Debugging process

1. Trace the full flow step by step across Android, React, Node, Python, and MongoDB.
2. Identify where data breaks.
3. Point to the exact file/line.
4. Explain why it fails.
5. Propose the smallest fix.
6. Wait for approval before implementing (unless the user asked you to implement).

After a fix: describe how to test manually, expected behavior, and failure cases.

---

## System components

| Component | Path | Role |
|-----------|------|------|
| Android app | `android-app/` | WebView shell, FCM, deep links, session cookies |
| Lexi client | `Lexi/client/` | Participant UI + admin dashboard (React) |
| Lexi server | `Lexi/server/` | REST API, auth, conversations (Node/Express) |
| Python engine | `logic-python/` | Proactive scheduler, heuristics, LLM, FCM |
| MongoDB | Atlas | Users, experiments, conversations, logs |

Changes often affect more than one layer. Trace cross-component impact before editing.

---

## Constraints (do not violate)

- **`news_service.py` is removed.** Do not reintroduce news-based triggers.
- **Primary LLM:** `gpt-4o` or Claude 3.5 Sonnet via `LLM_PROVIDER` / `LLM_MODEL` (or per-experiment `proactiveSettings.llmModel`).
- **`proactive_logs.trigger_source`:** `temporal` | `affective` | `gap` | `topic`.
- **Heuristics** live under `logic-python/heuristics/` and are gated by `experiment.experimentFeatures.proactiveSettings.heuristics`.
- **Institution in prompts:** Ben-Gurion University (BGU), not Cambridge.
- **Secrets:** Never commit `.env`, Firebase JSON, or API keys. On Render use `SERVICE_ACCOUNT_JSON_CONTENT` or Secret File `firebase.json`.
- **Do not** refactor unrelated code, rewrite whole files, or add features unless asked.

---

## Key documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview and quick start |
| `PROJECT_DOCUMENTATION.md` | Architecture and component reference |
| `PLAN.md` | Roadmap and completed work summary |
| `PLAN_BACKLOG.md` | Remaining work ranked by importance |
| `PROACTIVE_NOTIFICATIONS.md` | **Base spec** for improving proactive notifications |
| `DEPLOYMENT.md` | Production deployment (Render + Vercel) |

---

## Next task

*(Write the next task here when starting a new session.)*

**Status:** Proactive pipeline is deployed on Render (Node + Python scheduler on one Starter instance). Notifications send automatically at scheduled times. Focus next work on notification quality — use `PROACTIVE_NOTIFICATIONS.md` as the working document.

**Suggested next steps (from backlog):**
- Wire dashboard `frequency` to scheduler (or document as UI-only until implemented).
- Phase 5 dashboard: notification log, test-push button.
- Phase 7: analytics (open rate, time to first reply).

---

## If you break these rules

Stop and explain why before continuing.
