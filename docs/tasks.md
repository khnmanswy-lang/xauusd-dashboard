# Tasks: Real-Time XAUUSD Multi-Timeframe Dashboard

Step states: `planned` -> `built` -> `tested` -> `committed`, or `BLOCKED: <reason>`.

Once every step for a feature is `committed`, run the `master-test` skill for a full system/e2e readiness check (not acceptance testing - that's the user's call) before moving the feature to Done.

## Session handoff
- **Last session ended:** 2026-08-26 (Feature Completed: Auto-Execution Cron Sentry to OANDA Practice Account with trailing stop and UI controls)
- **In progress:** None (All features committed, 55 tests passing)
- **Next action for builder chat:** Implement remaining Backlog items (Sound/audio alerts for Asian sweeps and FVG mitigations) or monitor live execution.
- **Architectural & Strategy specs:** Full specifications in `docs/architecture.md`, `docs/design.md`, and `docs/learnings.md`.

---

## Active feature: Complete Purge of AI Elements & 100% Pure Quantitative MTF Terminal

### Strategy & Architecture Overview
Remove all leftover "AI" naming, cards, buttons, badges, robot icons, and AI endpoints. Replace them with 100% pure deterministic quantitative modules:
- **Algorithmic Setup Scanner**: Pure rule-based ICT/SMC & Quant breakout/pullback setup card with dynamic SL/TP, R:R calculation, and technical checklist.
- **Pure MTF Confluence & Volatility Risk Manager**: 1% risk lot sizing, ATR-based SL buffer, and ADR capacity sentry.
- **Clean GitHub Primer UI**: No robot emojis, no AI mentions, strictly quantitative, technical, and institutional metrics.

### Step-by-Step Plan

| Step | State | Notes |
|---|---|---|
| **1. UI Purge & Technical Re-Branding in `static/index.html`** | `tested` | Replaced all AI references and robot icons with Algorithmic Setup Scanner, technical icons, and quantitative checklists |
| **2. Client State & Action Purge in `static/js/app.js` & `static/js/chart.js`** | `tested` | Updated client triggers and alerts to pure quantitative setup scans |
| **3. Server Endpoints & Sentry Clean-up in `src/server.py`** | `tested` | Added `/api/setup/latest` and `/api/setup/scan` deterministic quantitative endpoints |
| **4. CSS Class Refactoring in `static/css/dashboard.css`** | `tested` | Clean GitHub Primer styling for `.setup-card` |
| **5. Full Verification & Live Host Reload** | `tested` | 65/65 tests passing; live daemon running on port 8000 |

### Files Touched
- [`src/core/indicators.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/indicators.py) - Full quantitative & volume indicator suite
- [`src/core/structure.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/structure.py) - Order Blocks, Break of Structure, SMC
- [`src/core/setup_scanner.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/setup_scanner.py) - Dynamic SL/TP bounds and risk-reward calculation

---

## Active feature: Zero-Dependency Multi-Timeframe Rich Quantitative Indicator Dashboard

### Strategy & Architecture Overview
Purely deterministic, ultra-low-latency, zero-dependency multi-timeframe analytics engine. Math, SMC/ICT structure, momentum, volatility, and trend indicators calculated in Python with sub-millisecond execution and real-time WebSocket streaming.

### Step-by-Step Plan

| Step | State | Notes |
## Active feature: Exact Institutional 4-TF Terminal (Wireframe Alignment & Full LLM Removal)

### Strategy & Architecture Overview
Build the exact institutional layout specified in the user's wireframe with **zero LLM/AI remnants**:
1. **Top Macro & Session Bar (6 Cells)**:
   - Cell 1: `SYMBOL: XAU/USD`, `BID`, `ASK`
   - Cell 2: `SPREAD: 1.2 pip`, `VOL: High`, `CHG: +X.XX%`
   - Cell 3: `SESSION STATUS` (`● LONDON (Open)`, `○ NY (Pre)`, `○ ASIA (Closed)`)
   - Cell 4: `ADR (20D): $XX.XX`, `TODAY: $XX.XX`, `ADR USED: [XX.X%]`
   - Cell 5: `DAILY RANGE (H-L)` (`High: $XXXX.XX`, `Low: $XXXX.XX`)
   - Cell 6: `DXY INDEX`, `US10Y`, `NEXT: Economic Event (Time GMT)`
2. **Main Workspace (4-TF 2x2 Grid + Right Technical Sidebar)**:
   - **4 Synchronized Charts**:
     - `M1`: Scalping / Execution + `[VWAP]` + `[Order Flow Lots]`
     - `M15`: Intraday Structure + `[EMA 9]` + `[EMA 21]`
     - `H1`: Trend / Dynamic S&R + `[EMA 50]` + `[EMA 200]` + `14-ATR`
     - `H4`: Macro Bias & Supply/Demand + `[H4 Liquidity Sweep]` + `14-ATR`
   - **Right Technical Indicator Sidebar**:
     - `[MULTI-TF RSI]` (M1, M15, H1, H4 live values & directional arrows)
     - `[PIVOT POINTS]` (Classic Standard Floor: PP, R1, R2, S1, S2)
     - `[ORDER FLOW]` (Buy% vs Sell% delta distribution)
3. **Bottom Execution Dock**:
   - `[Lots: 1.00]` `[SL: $XXXX.XX]` `[TP: $XXXX.XX]` `[BUY MARKET (Ask)]` `[SELL MARKET (Bid)]`
4. **Complete LLM Purge**:
   - Remove any remaining AI endpoints, headline cards, psychology text, or prompt generators. Keep pure deterministic Python math.

## Active feature: Comprehensive Panel-by-Panel Audit Fixes & Execution Dock Removal

### Strategy & Architecture Overview
Fix all 9 specific review findings and remove execution dock:
1. **Remove Execution Dock Entirely**:
   - Delete `.execution-dock` from `static/index.html`, `static/css/dashboard.css`, and `static/js/app.js`.
   - Reclaim full bottom viewport height for the 4-chart quad grid.
2. **Synchronize Order Flow Numbers (Single Source of Truth)**:
   - Calculate 30m rolling net delta in ounces / contracts: `Net Delta: -42 oz (-56% Sell)`
   - Mirror the exact same numbers in both the M1 chart sub-pill and right sidebar.
3. **Fix Indicator Label Collisions on Price Scale**:
   - On `LightweightCharts`: set `lastValueVisible: false` on volume series and Bollinger/VWMA secondary lines so volume strings ("71.97K") do not crowd or collide with the price axis tags.
   - Adjust `scaleMargins` and `rightOffset` (12 bars padding).
4. **Distinct Color Palette**:
   - `VWAP`: `#e3b341` (Gold)
   - `EMA 9`: `#58a6ff` (Light Blue)
   - `EMA 20`: `#f0883e` (Vibrant Orange)
   - `EMA 50`: `#bc8cff` (Purple)
   - `EMA 200`: `#ffffff` (Pure White Benchmark)
   - `VWMA 20`: `#39c5bb` (Teal)
5. **Fix H4 RSI = 50.0 Placeholder**:
   - Ensure H4 and D1 history have 30+ historical bars by combining daily history so H4 RSI calculates true mathematical RSI.
6. **Fix Spread Display**:
   - Format spread cleanly as `$0.20 (2.0 pips)` where 1 pip = $0.10.
7. **Fix CPI / Economic Release Times**:
   - Ensure US CPI is timed at `13:30 GMT` (8:30 AM ET) in `src/integrations/market_data.py`.
8. **Fix Toggle State Sync**:
   - Ensure initial visibility for Bollinger and VWMA is explicitly `visible: false` on chart creation.
9. **Fix Date/Time Axis Formatting**:
   - Add explicit day-of-month and hour:minute formatter: `DD MMM HH:mm` on time axis.

## Active feature: Purpose-Built Indicator Matrix per Timeframe Role

### Purpose-Built Matrix Specification

| Timeframe | Institutional Role | Active On-Chart Overlays | Floating Top-Right HUD Items | Dropped / Excluded |
|---|---|---|---|---|
| **M1** | **Scalp / Immediate Execution** | `EMA 9` (1.5px), `VWAP` (2px) | `● EMA 9` \| `● VWAP` \| `● Net OF (oz)` | EMA 50, EMA 200, Bollinger, Pivots |
| **M15** | **Intraday Structure** | `EMA 9` (1.5px), `EMA 21` (1.5px), `VWAP ±1/2σ Bands` (faint) | `● EMA 9` \| `● EMA 21` \| `● Range (H-L)` | EMA 200, Order Flow |
| **H1** | **Trend / Dynamic S&R** | `EMA 50` (1.5px), `EMA 200` (2px), `Daily Pivots (PP, R1, S1)` | `● EMA 50` \| `● EMA 200` \| `PP` \| `ATR` | VWAP, EMA 9/21, Order Flow |
| **H4** | **Macro Bias & Supply/Demand** | `EMA 50` (1.5px), `EMA 200` (2px), `Major S/D Liquidity Level` | `● EMA 50` \| `● EMA 200` \| `Liq Level` \| `ATR` | EMA 9/21, VWAP, VWAP bands, Order Flow |

### Step-by-Step Plan

| Step | State | Notes |
|---|---|---|
| **1. Tailor `SingleTimeframeChart` Series Creation per Role in `chart.js`** | `tested` | Only created exact series for each role (M1: EMA9+VWAP; M15: EMA9+EMA21+Bands; H1: EMA50+EMA200; H4: EMA50+EMA200) |
| **2. Update `setData` and `updateCandle` to Map Dedicated Data in `chart.js`** | `tested` | Populated and bound role-tailored datasets and muted volume histograms (15% opacity) |
| **3. Update Floating In-Graph HUDs in `index.html` and `dashboard.css`** | `tested` | Clean, non-overflowing HUD badges with color-coded dot legends |
| **4. Verify Full Test Suite & Relaunch Live Terminal** | `tested` | 54/54 tests passing; live server running on port 8000 |

## Session Handoff
- **Active Task**: Post-Audit Visual & Data Discrepancy Fixes.
- **Current Step**: Planning Gate (Audit complete, awaiting user confirmation on remediation).
- **Next Action**: Execute Step 1 upon confirmation.
- [`src/integrations/market_data.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/integrations/market_data.py)
- [`static/index.html`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/index.html)
- [`static/js/app.js`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/js/app.js)

## Active feature: Post-Audit Visual & Data Discrepancy Fixes

### Audit Findings from Live Screenshot (`docs/assets/live_dashboard_audit.png`):
1. **HUD EMA Number Disconnect**:
   - `M1`, `M15`, `H1`, `H4` floating HUDs displayed stale EMAs (~$3,500–$3,878) while real price was $4,400.
   - **Root Cause**: `chart_pills` in `market_data.py` was pulling from `self._indicators_matrix["ema"]` which was calculated on an un-updated `_m5_df`. Each chart HUD should read directly from its own native timeframe dataframe (`_m1_df`, `_m15_df`, `_h1_df`, `_h4_df`).
2. **Top Bar Trailing "pip" Label**:
   - Cell 2 renders `SPREAD: $0.25 (2.5 pips) pip` due to redundant `pip` static string following dynamic `spread_formatted`.
3. **Sidebar Vertical Space Optimization**:
   - Consolidate layout to eliminate excess dead space below overlay buttons.

### Step-by-Step Plan

| Step | State | Notes |
|---|---|---|
| **1. Fix Floating HUD EMA Calculations in `market_data.py`** | `tested` | Timeframe-native EMAs computed directly from `_m1_df`, `_m15_df`, `_h1_df`, and `_h4_df` |
| **2. Remove Redundant Trailing "pip" Label in `index.html`** | `tested` | Cleaned `top-spread` to display `$0.23 (2.3 pips)` without duplicate label |
| **3. Re-Verify with Playwright Live Screenshot & Master Test Suite** | `tested` | Verified screenshot at `docs/assets/live_dashboard_audit.png` and 54/54 pytest pass |

## Session Handoff
- **Active Task**: Post-Audit Visual & Data Discrepancy Fixes.
- **Current Step**: ALL STEPS COMPLETED & VERIFIED (54/54 tests passing).
- **Live Terminal**: [http://localhost:8000](http://localhost:8000)
- **Zero-Dependency Startup Command**: `pip install -r requirements.txt && uvicorn src.server:app --host 0.0.0.0 --port 8000`
- **Test Command**: `PYTHONPATH=. .venv/bin/pytest tests/ -v`
- [`src/integrations/market_data.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/integrations/market_data.py)
- [`static/index.html`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/index.html)
- [`static/css/dashboard.css`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/css/dashboard.css)
- [`static/js/chart.js`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/js/chart.js)
- [`static/js/app.js`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/js/app.js)

## Session Handoff
- **Active Task**: 4-Timeframe Simultaneous Multi-Chart Grid (M1, M15, H1, H4) & Trade Sim Removal.
- **Current Step**: Planning Gate (Awaiting user approval before code changes).
- **Next Action**: Execute Step 1 upon confirmation.
- [`src/config/settings.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/config/settings.py)
- [`src/integrations/market_data.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/integrations/market_data.py)
- [`src/core/auto_trader.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/auto_trader.py)
- [`src/server.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/server.py)
- [`static/index.html`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/index.html)
- [`static/js/app.js`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/js/app.js)
- [`static/js/chart.js`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/static/js/chart.js)

### Step-by-Step Plan

| Step | State | Notes |
|---|---|---|
| **1. Purge AI Client & Settings in `src/integrations/ai_client.py` & `src/config/settings.py`** | `tested` | Removed external AI dependencies, LLM calls, and API key requirements; replaced with pure `AlgoSettings` |
| **2. Pure Algorithmic Setup Analyzer in `src/core/algo_analyzer.py`** | `tested` | Created pure deterministic `AlgoSetupAnalyzer` evaluating SMC/ICT order flow, FVG pullbacks, sweeps, and quantitative indicators |
| **3. Default Zero-Auth Binance Public WebSocket in `src/integrations/market_data.py`** | `tested` | Public WebSocket proxy active with zero credential requirements and offline stochastic simulation fallback |
| **4. Server & Sentry Refactor in `src/server.py` & `src/core/auto_trader.py`** | `tested` | Wired server and sentry directly to `AlgoSetupAnalyzer` and `/api/setup` endpoints |
| **5. Test Suite Verification & Live Hosting** | `tested` | All 63 unit and integration tests passing cleanly; live server hosted on port 8000 |

### Files Touched
- [`src/config/settings.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/config/settings.py)
- [`src/core/algo_analyzer.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/algo_analyzer.py)
- [`src/core/ai_analyzer.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/ai_analyzer.py)
- [`src/server.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/server.py)
- [`src/core/auto_trader.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/src/core/auto_trader.py)
- [`tests/unit/test_ai_analyzer.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/tests/unit/test_ai_analyzer.py)
- [`tests/unit/test_oanda_client.py`](file:///home/inonniiz/projects/antigravity/XAUUSD%20Dashboard/tests/unit/test_oanda_client.py)

## Session Handoff
- **Active Task**: 100% Zero-Dependency Pure Algorithmic Terminal (No AI, Pure Algo).
- **Current Step**: ALL 5 STEPS COMPLETED & TESTED (63/63 tests passing).
- **Live Terminal**: [http://localhost:8000](http://localhost:8000)
- **Run Command**: `PYTHONPATH=. .venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8000`
- **Test Command**: `PYTHONPATH=. .venv/bin/pytest tests/ -v`
- **Next Action**: Dashboard is running live. Ready for user inspection.

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
