# Architecture: Real-Time XAUUSD Multi-Timeframe Dashboard with AI Setup Scanner

## 1. System Overview
A local, low-latency, real-time trading dashboard designed specifically for **XAUUSD (Gold)** multi-timeframe analysis across **H1 (Macro Bias)**, **M15 (Structure & Momentum)**, and **M5 (Execution & Liquidity Triggers)**.

The system combines:
1. **Real-Time Data & Analytics Engine (`FastAPI` + `WebSockets` + `APScheduler`)**:
   - Ingests live Gold pricing and historical candles from OANDA v20 Practice API (with zero-config public WebSocket fallback).
   - Computes multi-timeframe indicators (Session VWAP, EMAs, RSI Divergence, ATR, ADR).
   - Scans for high-probability setups (Liquidity Sweeps, M5 CHoCH, Fair Value Gaps / FVGs).
   - Runs a **Scheduled Cron Job** evaluating market structure and invoking an **AI Analysis Engine** to generate instant trade plans and risk commentary.
2. **Trader Terminal UI (`TradingView Lightweight Charts` + Modern Dark Dashboard)**:
   - **Top & Left Panel:** Live market tickers, session status, news countdown, and technical indicator confluence matrix.
   - **Center Panel:** Interactive Multi-Timeframe Chart with automated overlays for FVGs, Asian Range boxes, and Session VWAP bands.
   - **Right Panel:** Real-time **AI Analysis Card**, setup grade/confidence score, dynamic lot size calculator, and execution plan.

---

## 2. Tech Stack

* **Backend & Automation:**
  * Python 3.12
  * `FastAPI` + `Uvicorn` (Asynchronous REST API and WebSocket broadcaster)
  * `APScheduler` (Background cron jobs for periodic 60s / 5m market structure & AI evaluation)
  * `httpx` + `websockets` (Async OANDA v20 API & live WebSocket streaming)
  * `pandas` + `numpy` (Candle aggregation, vector math for indicators, FVGs & structure)
  * `yfinance` (Macro correlation feeds: DXY `DX-Y.NYB`, US10Y `^TNX`)
  * `google-genai` / `openai` (AI trade setup analysis and reasoning engine)
  * `pytest` (Unit and integration test suite)
* **Frontend:**
  * HTML5 / CSS3 (Dark financial terminal archetype, responsive 3-column grid)
  * Vanilla JavaScript (ES6 Modules, reactive WebSocket state manager)
  * `TradingView Lightweight Charts v4` (Hardware-accelerated canvas chart with custom overlays)

---

## 3. Directory & File Structure

```
XAUUSD Dashboard/
├── docs/
│   ├── architecture.md            # System architecture, data flow & specifications (this file)
│   ├── design.md                  # Locked visual design specs (palette, fonts, components)
│   └── tasks.md                   # Step tracker & session handoff
├── .env                           # Local secrets & API keys (OANDA, AI Provider)
├── .env.example                   # Template for environment configuration
├── requirements.txt               # Project dependencies
├── src/
│   ├── config/
│   │   └── settings.py            # Environment configuration, data sources, thresholds
│   ├── integrations/
│   │   ├── oanda_client.py        # OANDA v20 Practice REST & streaming client
│   │   ├── market_data.py         # Unified market data distributor (OANDA / Public WS)
│   │   ├── macro_feed.py          # Background polling for DXY, US10Y, and VIX
│   │   ├── economic_calendar.py   # High-impact USD news scraper & countdown timer
│   │   └── ai_client.py           # LLM client (Gemini / OpenAI / Ollama)
│   ├── core/
│   │   ├── indicators.py          # Multi-TF VWAP, ATR, ADR, EMAs (20/50/200), RSI Divergence
│   │   ├── structure.py           # Session levels (Asia High/Low), PDH/PDL, FVGs, Sweeps
│   │   ├── setup_scanner.py       # High-probability setup detection engine (Sweeps + FVG + CHoCH)
│   │   ├── ai_analyzer.py         # Scheduled cron analyzer generating trade plans & reasoning
│   │   └── risk_calculator.py     # Dynamic ATR-based lot size & risk calculator
│   └── server.py                  # FastAPI app, WebSocket broadcaster, background cron scheduler
├── static/
│   ├── index.html                 # 3-panel dashboard layout (Left: Indi, Center: Chart, Right: AI)
│   ├── css/
│   │   └── dashboard.css          # Dark financial terminal styling
│   └── js/
│       ├── chart.js               # Lightweight Charts manager (H1/M15/M5 toggle & overlays)
│       └── app.js                 # WebSocket client, AI card renderer, DOM updates, risk calculator
├── scripts/
│   └── start_dashboard.py         # Launch backend server and open local browser
└── tests/
    ├── test_indicators.py         # Unit tests for VWAP, EMA, ATR, ADR, RSI divergence
    ├── test_structure.py          # Unit tests for session levels, FVGs, and sweeps
    ├── test_setup_scanner.py      # Unit tests for setup recognition logic
    └── test_risk.py               # Unit tests for position sizing calculations
```

---

## 4. End-to-End Data & Execution Flow

```
[OANDA v20 API / Public Stream] ──> [market_data.py]
[Macro Feed (DXY, US10Y)]       ──> [macro_feed.py]
[High-Impact News Scraper]      ──> [economic_calendar.py]
                                          │
                                          ▼
                         [src/core/ Real-Time Analytics]
                           - Multi-TF Candle Aggregator (M5, M15, H1)
                           - Indicators (VWAP, ATR, ADR, EMAs, RSI)
                           - Structure Engine (Asia Sweep, FVG, PDH/L)
                           - Setup Scanner (Evaluates A+ Confluence)
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
        [FastAPI /ws/stream]                      [APScheduler Background Cron]
   (Broadcasts live price, indicators,             (Every 60s / M5 candle close:
    active FVGs, countdown timer)                   invokes ai_analyzer.py -> ai_client.py)
                   │                                             │
                   ▼                                             ▼
         [Browser UI (static/)] <───────────────── [Broadcasts AI Analysis Card]
           • Top/Left: Live Indicators & Bias
           • Center: Lightweight Charts + Overlays
           • Right: Real-time AI Trade Plan
```

---

## 5. Setup Scanner & AI Analysis Engine Specifications

### A. The Setup Scanner (`src/core/setup_scanner.py`)
Scans for the 5-point institutional confluence setup:
1. **Session Liquidity Sweep:** Price pierces and rejects the Asian Range High/Low or Previous Day High/Low (PDH/PDL).
2. **Micro Structure Shift (M5 CHoCH):** Clean displacement breaking the recent fractal high/low.
3. **Fair Value Gap (FVG) Retest:** Active M5/M15 FVG formed during displacement; price retraces to the $50\%$ Consequent Encroachment (CE) level.
4. **Macro Confluence:** Alignment with H1 200 EMA and Session VWAP.
5. **Exhaustion Guard:** ADR used $< 80\%$ and no high-impact USD economic news within 15 minutes.

### B. Scheduled AI Analyzer (`src/core/ai_analyzer.py`)
Runs on a periodic cron (via `APScheduler` every 60s or on M5 candle close) or upon event trigger:
* Ingests the current market payload (Multi-TF Matrix + Scanner result + DXY + News).
* Prompts the AI model to generate a structured trade plan:
  * **Setup Grade:** `GRADE_A` (High Confluence) | `GRADE_B` | `NO_SETUP`
  * **Setup Type:** e.g., *"Bullish London Sweep of Asian Low + M5 FVG Retest"*
  * **Trade Thesis:** 2-sentence rationale on institutional order flow.
  * **Actionable Execution Levels:**
    * Suggested Entry: e.g., `$2,932.50`
    * Invalidation / Stop Loss: e.g., `$2,929.80` ($1.5 \times \text{M5 ATR}$)
    * Target 1 (TP1): `$2,938.00` ($1:2$ RR)
    * Target 2 (TP2): `$2,945.00` (Asian High Liquidity Target)
  * **Invalidation Trigger:** Condition that invalidates the trade before entry.
  * **Trader Psychology Reminder:** Anti-revenge trading and risk sizing warnings.

---

## 6. UI Layout & Component Blueprint

```
+-------------------------------------------------------------------------------------------------------------------+
| [HEADER] XAUUSD: $2,935.40 | Spread: 0.20 | DXY: 104.25 (▼0.12%) | US10Y: 4.22% | News: CPI in 3h 15m (🟢 Clear)  |
+-----------------------------------+-------------------------------------+-----------------------------------------+
| LEFT PANEL (Indicators & Bias)    | CENTER PANEL (Interactive Chart)    | RIGHT PANEL (AI Analysis & Trade Setup) |
+-----------------------------------+-------------------------------------+-----------------------------------------+
| • Multi-TF Confluence Score       | • Synced Lightweight Chart          | 🤖 AI SCANNER: [GRADE A LONG DETECTED]  |
|   - H1: 🟢 Bullish (Above 200EMA) |   - Timeframe Switcher (H1/M15/M5)  | • Confidence: 92% (High Confluence)     |
|   - M15: 🟢 Above Session VWAP    |   - Automated Overlays:             | • Thesis: London sweep of Asian Low     |
|   - M5: 🟢 Bullish CHoCH + FVG    |     * Asia High/Low Range Box       |   ($2928.00) followed by M5 CHoCH and   |
| • Indicators & Volatility:        |     * Session VWAP ±1/2σ Lines      |   clean FVG retest at $2932.50.         |
|   - Session VWAP: $2,931.20       |     * Active M5/M15 FVGs (Shaded)   | • Actionable Trade Plan:                |
|   - M5 ATR: $1.90 | H1: $7.80     |     * Sweep Level Markers           |   - Entry: $2,932.50                    |
|   - RSI(14): M5 (52) | M15 (58)   |     * PDH / PDL Horizontal Lines    |   - Stop Loss: $2,929.80 (1.5x ATR)     |
| • ADR Progress Bar:               | • M5 Candle Timer: [02:45]          |   - TP1 (1:2 RR): $2,938.00             |
|   - 54% Used ($17.40 / $32.00)    |                                     |   - TP2 (Asia High): $2,945.00          |
| • Session Reference Levels:       |                                     | • Dynamic Lot Sizer:                    |
|   - Asia High: $2,940.50          |                                     |   - Balance: $10,000 | Risk: 1% ($100)  |
|   - Asia Low: $2,928.00 (SWEPT)   |                                     |   - Recommended Lots: 0.37              |
|   - PDH: $2,948.10 | PDL: $2,918  |                                     | • Invalidation Condition & Alert Log    |
+-----------------------------------+-------------------------------------+-----------------------------------------+
```

---

## 7. Key Decisions & Rationale

1. **OANDA v20 Practice API + Public WebSocket Fallback:** Direct live institutional quotes via user's OANDA token, with automatic fallback to public zero-auth feeds if no API key is provided.
2. **Background Cron for AI Analysis:** Running the AI analysis via `APScheduler` decoupled from the UI keeps the UI responsive (sub-100ms WebSocket streaming) while calling LLMs only when candles close or setups are detected.
3. **Structured JSON Output from AI:** Enforces deterministic formatting for entry, stop loss, targets, and trade grades so the frontend can render clean metric cards alongside markdown analysis.

