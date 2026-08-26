# Tasks: Real-Time XAUUSD Multi-Timeframe Dashboard

Step states: `planned` -> `built` -> `tested` -> `committed`, or `BLOCKED: <reason>`.

Once every step for a feature is `committed`, run the `master-test` skill for a full system/e2e readiness check (not acceptance testing - that's the user's call) before moving the feature to Done.

## Session handoff
- **Last session ended:** 2026-08-26 (Feature Completed: CSV Trade Journal & Export System with real-time UI download and REST APIs)
- **In progress:** None (All features committed, 51 tests passing)
- **Next action for builder chat:** Implement remaining Backlog items (Sound/audio alerts or 1-click OANDA practice order execution).
- **Architectural & Strategy specs:** Full specifications in `docs/architecture.md`, `docs/design.md`, and `docs/learnings.md`.

---

## Active feature: CSV Trade Journal & Export System

| Step | State | Notes |
|---|---|---|
| **1. Journal Storage Engine** | `committed` | Implement `src/core/trade_journal.py` with thread-safe recording, CSV persistence, and export builder |
| **2. Server REST Endpoints** | `committed` | Add `GET /api/journal/export`, `GET /api/journal/list`, `POST /api/journal/record` in `src/server.py` |
| **3. UI Export Integration** | `committed` | Add "📥 Export Journal (CSV)" buttons in header and alerts card & wire in `static/js/app.js` |
| **4. Verification & Tests** | `committed` | Add `tests/unit/test_trade_journal.py` and integration endpoint tests in `tests/integration/test_server.py` |

---

## Backlog
- [ ] Sound/audio alerts for Asian Range sweeps and M5 FVG mitigations
- [ ] Optional 1-click order execution to OANDA practice account

---

## Done
- Initial FastAPI backend, quantitative indicators (VWAP, ATR, ADR, EMAs, RSI), and basic dark terminal UI.
- OANDA v20 REST & Live Streaming integration with simulated fallback.
- 5-Point Institutional Setup Scanner with dynamic ICT Fair Value Gap (FVG) and CHoCH detection.
- Deep 65%–70% FVG mitigation entry anchoring for tighter risk bounds.
- Multi-provider AI Analyzer (Gemini, OpenAI, Ollama, and Deterministic Quant Engine) with 60-second `APScheduler` cron.
- Stateful Plan Lifecycle with silent cron handover, pre-trade trigger condition tracking, and invalidation rejection.
- Modernized 3-Panel Dark Glassmorphism UI with real-time AI card, on-demand re-scan button, and 1-click lot sizer synchronization.
- Trade Journal Manager with persistent disk CSV storage and 1-click browser CSV export.
- All 51 unit and integration tests passing (`tests/unit/` & `tests/integration/`).
- Strategy forensic learnings and quantitative rules documented in `docs/learnings.md`.
