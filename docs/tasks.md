# Tasks: Real-Time XAUUSD Multi-Timeframe Dashboard

Step states: `planned` -> `built` -> `tested` -> `committed`, or `BLOCKED: <reason>`.

Once every step for a feature is `committed`, run the `master-test` skill for a full system/e2e readiness check (not acceptance testing - that's the user's call) before moving the feature to Done.

## Session handoff
- **Last session ended:** 2026-08-24 (Step 1 Completed: Config & OANDA Integration)
- **In progress:** `Active feature: AI Setup Scanner & Right-Panel Analysis (Cron + OANDA v20)` (State: Step 1 `committed`, Step 2 `planned`)
- **Next action for builder chat:** Start Step 2 — Implement `src/core/setup_scanner.py` (5-point confluence: Asia sweep, M5 CHoCH, FVG mitigation, VWAP, ADR guard) + unit tests.
- **Architectural spec:** Full specifications, scanner rules, AI prompt format, and UI wireframes are documented in `docs/architecture.md` and `docs/design.md`.

---

## Active feature: AI Setup Scanner & Right-Panel Analysis (Cron + OANDA v20)

| Step | State | Notes |
|---|---|---|
| **1. Config & OANDA Integration** | `committed` | Implement `src/integrations/oanda_client.py` (v20 Practice REST/Stream) and wire into `src/config/settings.py` + `.env` |
| **2. Setup Scanner Engine** | `planned` | Implement `src/core/setup_scanner.py` (5-point confluence: Asia sweep, M5 CHoCH, FVG mitigation, VWAP, ADR guard) + unit tests |
| **3. AI Analyzer & Cron Job** | `planned` | Implement `src/integrations/ai_client.py` and `src/core/ai_analyzer.py`; schedule via `APScheduler` cron in `src/server.py` |
| **4. UI Refactor (3-Panel Layout)** | `planned` | Update `static/index.html`, `static/css/dashboard.css`, and `static/js/app.js` (Left: Indicators, Center: Chart + FVGs, Right: AI Analysis Card) |
| **5. Verification & E2E Tests** | `planned` | Add `tests/test_setup_scanner.py`, `tests/test_ai_analyzer.py` and verify full live stream in browser |

---

## Backlog
- [ ] Sound/audio alerts for Asian Range sweeps and M5 FVG mitigations
- [ ] Optional 1-click order execution to OANDA practice account
- [ ] Export session journal / trade log to CSV

---

## Done
- Initial FastAPI backend, quantitative indicators (VWAP, ATR, ADR, EMAs, RSI), and basic dark terminal UI.
- All 28 existing unit and integration tests passing.
- `docs/architecture.md`, `docs/design.md`, and `.env.example` updated with complete AI Scanner and OANDA specifications.
