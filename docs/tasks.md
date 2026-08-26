# Tasks: Real-Time XAUUSD Multi-Timeframe Dashboard

Step states: `planned` -> `built` -> `tested` -> `committed`, or `BLOCKED: <reason>`.

Once every step for a feature is `committed`, run the `master-test` skill for a full system/e2e readiness check (not acceptance testing - that's the user's call) before moving the feature to Done.

## Session handoff
- **Last session ended:** 2026-08-26 (Feature Completed: Auto-Execution Cron Sentry to OANDA Practice Account with trailing stop and UI controls)
- **In progress:** None (All features committed, 55 tests passing)
- **Next action for builder chat:** Implement remaining Backlog items (Sound/audio alerts for Asian sweeps and FVG mitigations) or monitor live execution.
- **Architectural & Strategy specs:** Full specifications in `docs/architecture.md`, `docs/design.md`, and `docs/learnings.md`.

---

## Active feature: Auto-Execution Cron Sentry to OANDA Practice Account

| Step | State | Notes |
|---|---|---|
| **1. OANDA Order Execution API** | `committed` | Add `create_order`, `get_open_trades`, `update_trade_stop_loss`, `get_account_summary` in `src/integrations/oanda_client.py` |
| **2. AutoTrader Sentry Engine** | `committed` | Implement `src/core/auto_trader.py` with duplicate protection, killzone gating, ADR check, trailing SL, and journal logging |
| **3. Server Cron & REST Integration** | `committed` | Wire `AutoTrader` into 60s `APScheduler` cron; add `/api/autotrader/status` and `/api/autotrader/toggle` in `src/server.py` |
| **4. Frontend UI Controls & Status** | `committed` | Add Auto-Trader badge and toggle in `static/index.html`, `static/css/dashboard.css`, and `static/js/app.js` |
| **5. Verification & Tests** | `committed` | Add `tests/unit/test_auto_trader.py` and integration tests in `tests/integration/test_server.py` |

---

## Backlog
- [ ] Sound/audio alerts for Asian Range sweeps and M5 FVG mitigations

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
- Auto-Execution Cron Sentry (`AutoTrader`) with 1-min interval evaluation, duplicate position protection, Killzone gating, dynamic lot calculation, automated OANDA bracket order dispatching, +1.5R trailing stop to Break-Even, and live UI badge toggle.
- All 55 unit and integration tests passing (`tests/unit/` & `tests/integration/`).
- Strategy forensic learnings and quantitative rules documented in `docs/learnings.md`.
