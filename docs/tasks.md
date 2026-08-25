# Tasks: Real-Time XAUUSD Multi-Timeframe Dashboard

Step states: `planned` -> `built` -> `tested` -> `committed`, or `BLOCKED: <reason>`.

Once every step for a feature is `committed`, run the `master-test` skill for a full system/e2e readiness check (not acceptance testing - that's the user's call) before moving the feature to Done.

## Session handoff
- **Last session ended:** 2026-08-25 (Feature Completed: AI Setup Scanner, 1-Min Cron, Stateful Handover Lifecycle, and 3-Panel Dashboard)
- **In progress:** None (All 5 Steps `committed` and verified via master test suite)
- **Next action for builder chat:** Implement items from Backlog (Audio alerts, 1-click execution, or CSV journal export) or expand live feeds.
- **Architectural & Strategy specs:** Full specifications in `docs/architecture.md`, `docs/design.md`, and `docs/learnings.md`.

---

## Active feature: AI Setup Scanner & Right-Panel Analysis (Cron + OANDA v20)

| Step | State | Notes |
|---|---|---|
| **1. Config & OANDA Integration** | `committed` | Implement `src/integrations/oanda_client.py` (v20 Practice REST/Stream) and wire into `src/config/settings.py` + `.env` |
| **2. Setup Scanner Engine** | `committed` | Implement `src/core/setup_scanner.py` (5-point confluence: Asia sweep, M5 CHoCH, FVG mitigation, VWAP, ADR guard) + unit tests |
| **3. AI Analyzer & Cron Job** | `committed` | Implement `src/integrations/ai_client.py` and `src/core/ai_analyzer.py`; schedule via `APScheduler` cron in `src/server.py` |
| **4. UI Refactor (3-Panel Layout)** | `committed` | Update `static/index.html`, `static/css/dashboard.css`, and `static/js/app.js` (Left: Indicators, Center: Chart + FVGs, Right: AI Analysis Card) |
| **5. Verification & E2E Tests** | `committed` | Master test pass (49 unit/integration tests green), live backtest runner & stateful plan lifecycle verification |

---

## Backlog
- [ ] Sound/audio alerts for Asian Range sweeps and M5 FVG mitigations
- [ ] Optional 1-click order execution to OANDA practice account
- [ ] Export session journal / trade log to CSV

---

## Done
- Initial FastAPI backend, quantitative indicators (VWAP, ATR, ADR, EMAs, RSI), and basic dark terminal UI.
- OANDA v20 REST & Live Streaming integration with simulated fallback.
- 5-Point Institutional Setup Scanner with dynamic ICT Fair Value Gap (FVG) and CHoCH detection.
- Multi-provider AI Analyzer (Gemini, OpenAI, Ollama, and Deterministic Quant Engine) with 60-second `APScheduler` cron.
- Stateful Plan Lifecycle with silent cron handover, pre-trade trigger condition tracking, and invalidation rejection.
- Modernized 3-Panel Dark Glassmorphism UI with real-time AI card, on-demand re-scan button, and 1-click lot sizer synchronization.
- All 49 unit and integration tests passing (`tests/unit/` & `tests/integration/`).
- Strategy forensic learnings and quantitative rules documented in `docs/learnings.md`.
