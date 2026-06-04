# Plan Backlog — Not Yet Done

Items from `PLAN.md` and ongoing research needs that are **not** implemented (or only partially implemented). Use this file to prioritize future work.

**Importance legend**

| Level | Meaning |
|-------|---------|
| **Critical** | Blocks correct or safe production experiments |
| **High** | Strongly affects thesis quality or researcher control |
| **Medium** | Improves UX, analysis, or maintainability |
| **Low** | Polish or convenience |
| **Nice-to-have** | Stretch goals |

---

## Critical

| Item | Why it matters | Notes |
|------|----------------|-------|
| Rotate Firebase key if ever committed to git | Security | Use Secret File on Render; confirm repo has no live JSON |
| Production env: remove test flags | Wrong behavior in the field | e.g. `AFFECTIVE_DELAY_HOURS=0`, `PROMPT_EXPIRY_HOURS=0` on Render |
| Verify `MAX_DAILY_NOTIFICATIONS` / daily cap in production | Spam risk | Check `research_service.py` and env `DAILY_MESSAGE_LIMIT` |

---

## High — Proactive notifications (see `PROACTIVE_NOTIFICATIONS.md`)

| Item | Why it matters | Notes |
|------|----------------|-------|
| **Notification quality & tone** | Core thesis contribution | Hebrew tone, emotion matching, less generic topic fallbacks |
| **Dashboard `frequency` not wired to scheduler** | Researcher sets minutes in UI; code uses hardcoded `FIRE_TIMES` in `scheduler.py` | Either implement or hide/disable field in `ProactiveSettingsModal.tsx` |
| **Dashboard schedule picker** (fixed times vs interval) | Phase 5.1 | Store in `proactiveSettings`, read in `scheduler.py` |
| **Test notification button** | Phase 5.1 | Admin sends one push to own device without waiting for cron |
| **Notification log in dashboard** | Phase 5.1 | Table from `proactive_logs` per participant/heuristic |
| **Analytics funnel** | Phase 7.2 | Sent → opened → first reply → conversation length |
| **Per-experiment daily cap / fire times in DB** | Ops without redeploy | Today: edit `scheduler.py` + push |

---

## High — Platform & research

| Item | Why it matters | Notes |
|------|----------------|-------|
| Conversation quality / prompt tuning | Phase 7.1 | System prompts, opener agent, A/B tones per heuristic |
| `UserContext` / `decision_engine` cleanup | Medium tech debt | Legacy demo code removed; ensure no dead imports |
| Export metrics in admin Data Panel | Thesis analysis | Open/response rates by heuristic |

---

## Medium

| Item | Why it matters | Notes |
|------|----------------|-------|
| Google Calendar OAuth for temporal heuristic | Richer than `future_mentions` only | Phase 4.9 stretch |
| `preferred_send_hours` from engagement (Phase B) | Personalize send time | Needs response-time data in `proactiveMemory` |
| Parsed `future_mentions` with anchor dates | Better temporal firing | Partially in `heuristics/temporal.py` — verify completeness |
| Logo refresh (app + dashboard) | Professional study appearance | Phase 4.9 |
| MkDocs / auto-generated API docs | Thesis appendix | Phase 4.9 |
| Remove cleartext HTTP from production APK | Security | `network_security_config.xml` debug vs release |
| Stale `logic/decision_engine.py` removal | Repo clarity | If still unused after cleanup |

---

## Low

| Item | Why it matters | Notes |
|------|----------------|-------|
| GitHub Actions APK build per experiment | Was Phase 4.8 | Replaced by generic APK + `/join/:experimentId` — document only |
| Web search for agents | Phase 7 | Not started |
| Admin: per-agent LLM override | Phase 4.9 | Global/per-experiment model exists |

---

## Nice-to-have

| Item | Notes |
|------|-------|
| UptimeRobot ping to reduce Render cold start | Less relevant on Starter 24/7 |
| Separate Python worker service | Superseded by combined Render instance |
| Cambridge → BGU in every legacy string | Audit `Lexi/server` prompts if any remain |

---

## Partially done (do not re-implement from scratch)

| Item | Status |
|------|--------|
| Heuristics (temporal, affective, behavioural gap) | Implemented; tune quality in `PROACTIVE_NOTIFICATIONS.md` |
| LLM upgrade (GPT-4o / Claude) | Done |
| High-intensity Android notifications | Done |
| Deep link + session persistence | Done |
| Deferred deep linking (`/join`, IP match) | Done |
| `firstChatSentence` reset (message / finish / 2h) | Done on Node; expiry also in Python cycle |
| `isProactive` sync with experiment toggle | Done |
| Combined Render deploy (Node + scheduler) | Done |

---

*Update this file when closing backlog items or adding new thesis requirements.*
