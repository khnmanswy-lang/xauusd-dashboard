# Architecture: Real-Time XAUUSD Multi-Timeframe Dashboard

## 1. System Overview
A local, low-latency, real-time trading dashboard designed specifically for **XAUUSD (Gold)** multi-timeframe analysis across **H1 (Macro Bias)**, **M15 (Structure & Momentum)**, and **M5 (Execution & Liquidity Triggers)**.

The system consists of:
1. **Python Real-Time Streaming Backend (`FastAPI` + `WebSockets`)**: Ingests live Gold ticks, aggregates M5/M15/H1 candles, calculates quantitative indicators (VWAP, EMAs, RSI Divergence, ATR/ADR), tracks session liquidity (Asia/London/NY), and broadcasts state updates to the UI over a low-latency WebSocket connection.
2. **Trader Terminal UI (`TradingView Lightweight Charts` + Modern Dark Dashboard)**: Displays synced multi-timeframe charts, real-time confluence matrix, macro tickers (DXY, US10Y), economic news countdown, and an automated ATR-based lot size calculator.

---

## 2. Tech Stack

* **Backend & Analytics:**
  * Python 3.12
  * `FastAPI` + `Uvicorn` (Asynchronous REST API and WebSocket broadcaster)
  * `websockets` + `httpx` (Real-time live market feed and async scrapers)
  * `pandas` + `numpy` (Candle resampling, vector math for indicators & structure)
  * `yfinance` (Macro correlation tickers: DXY `DX-Y.NYB`, US10Y `^TNX`)
  * `pytest` (Unit and integration test suite)
* **Frontend:**
  * HTML5 / CSS3 (Dark terminal archetype, responsive 3-column layout)
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
├── requirements.txt               # Project dependencies
├── src/
│   ├── config/
│   │   └── settings.py            # Environment configuration, data sources, thresholds
│   ├── integrations/
│   │   ├── market_data.py         # Live XAUUSD WebSocket stream & historical bar seeder
│   │   ├── macro_feed.py          # Background polling for DXY, US10Y, and VIX
│   │   └── economic_calendar.py   # High-impact USD news scraper & countdown timer
│   ├── core/
│   │   ├── indicators.py          # Multi-TF VWAP, ATR, ADR, EMAs (20/50/200), RSI Divergence
│   │   ├── structure.py           # Session levels (Asia High/Low), PDH/PDL, FVGs, Sweeps
│   │   └── risk_calculator.py     # Dynamic ATR-based lot size & risk calculator
│   └── server.py                  # FastAPI app, REST routes, WebSocket broadcaster
├── static/
│   ├── index.html                 # 3-panel dashboard layout
│   ├── css/
│   │   └── dashboard.css          # Dark financial terminal styling
│   └── js/
│       ├── chart.js               # Lightweight Charts manager (H1/M15/M5 toggle & overlays)
│       └── app.js                 # WebSocket client, DOM updates, risk calculator
├── scripts/
│   └── start_dashboard.py         # Launch backend server and open local browser
└── tests/
    ├── test_indicators.py         # Unit tests for VWAP, EMA, ATR, ADR, RSI divergence
    ├── test_structure.py          # Unit tests for session levels and liquidity sweeps
    └── test_risk.py               # Unit tests for position sizing calculations
```

---

## 4. Data Flow & Streaming Architecture

```
[External Feeds]
  │
  ├──> Public Gold WebSocket Stream (PAXGUSDT / OANDA / MT5 Bridge) ──> [src/integrations/market_data.py]
  ├──> Macro Tickers (DXY, US10Y via Yahoo Finance) ──────────────────> [src/integrations/macro_feed.py]
  └──> High-Impact USD News Scraper ──────────────────────────────────> [src/integrations/economic_calendar.py]
                                                                                      │
                                                                                      ▼
                                                                       [src/core/ Analytics Engine]
                                                                         - Multi-TF Candle Resampler
                                                                         - Indicators (VWAP, ATR, EMA, RSI)
                                                                         - Structure (Asia Sweep, FVG, PDH/L)
                                                                         - Dynamic Lot Calculator
                                                                                      │
                                                                                      ▼
                                                                        [src/server.py (FastAPI)]
                                                                         - Broadcasts JSON via /ws/stream
                                                                                      │
                                                                                      ▼ (WebSocket)
                                                                       [Browser UI (static/)]
                                                                         - Lightweight Charts (H1/M15/M5)
                                                                         - MTF Confluence Matrix
                                                                         - Candle Timer & Risk Panel
```

### WebSocket Payload Specification (`/ws/stream`)
Every price tick or candle update broadcasts a unified state frame:
```json
{
  "timestamp": 1740212400,
  "xauusd": {
    "price": 2935.40,
    "bid": 2935.30,
    "ask": 2935.50,
    "spread": 0.20,
    "candle_timer_m5": 142
  },
  "macro": {
    "dxy": {"price": 104.25, "change_pct": -0.12, "bias": "BEARISH"},
    "us10y": {"yield": 4.22, "change_pct": 0.05}
  },
  "confluence_matrix": {
    "h1": {"bias": "BULLISH", "ema_200": 2912.50, "rsi": 58.4},
    "m15": {"structure": "BULLISH_CHOUCH", "vwap": 2931.20, "rsi_div": null},
    "m5": {"signal": "BUY_TRIGGER", "sweep": "ASIA_LOW_SWEPT", "fvg": [2932.10, 2934.00]},
    "overall_score": "+3 BULLISH"
  },
  "volatility": {
    "adr_used_pct": 54.2,
    "adr_total": 32.00,
    "adr_used": 17.40,
    "atr_m5": 1.90,
    "atr_m15": 3.50,
    "atr_h1": 7.80
  },
  "session": {
    "active_session": "LONDON",
    "killzone": "LONDON_OPEN",
    "asia_high": 2940.50,
    "asia_low": 2928.00,
    "pdh": 2948.10,
    "pdl": 2918.00
  },
  "news": {
    "next_event": "US Core CPI",
    "countdown_seconds": 11700,
    "impact": "HIGH",
    "guard_active": false
  }
}
```

---

## 5. Multi-Timeframe Strategy Engine Specifications

### A. H1 Timeframe (Macro Bias & Boundaries)
* **200 EMA & 50 EMA:** Determines long-term directional bias. Longs favored when price > 200 EMA.
* **Key Reaction Zones:** Previous Day High/Low (PDH/PDL), Weekly Open, and H1 Order Blocks.
* **H1 RSI (14):** Identifies macro overbought/oversold boundaries and cycle health.

### B. M15 Timeframe (Structure & Value Benchmarks)
* **Session VWAP with Standard Deviation Bands:**
  * Price above Session VWAP = Bullish intraday positioning.
  * $+2\sigma / -2\sigma$ standard deviation bands mark mean-reversion pullback targets.
* **Market Structure:** Automated tracking of BOS (Break of Structure) and CHoCH (Change of Character).
* **RSI Divergence Scanner:** Flags regular divergence (reversal alert) and hidden divergence (trend continuation).

### C. M5 Timeframe (Execution & Liquidity Triggers)
* **Asian Session Range Tracker (00:00 - 08:00 UTC):** Records Asia High and Asia Low. Flags real-time "Liquidity Sweeps" during London/NY open when price pierces and rejects the Asian boundary.
* **Fair Value Gap (FVG) Detector:** Highlights 3-candle price imbalances on M5.
* **Candle Countdown Clock:** Real-time second countdown to candle close to ensure no premature execution.
* **Dynamic Stop Loss & Lot Size Calculator:**
  $$\text{Dynamic SL} = 1.5 \times \text{ATR}_{M5}$$
  $$\text{Lot Size} = \frac{\text{Account Balance} \times \text{Risk \%}}{\text{SL Distance (\$) } \times 100}$$

---

## 6. UI Layout & Component Blueprint

```
+---------------------------------------------------------------------------------------------------------+
| [HEADER] XAUUSD: $2,935.40 | Spread: 0.20 | DXY: 104.25 (▼0.12%) | US10Y: 4.22% | News: CPI in 3h 15m   |
+-----------------------------------+-------------------------------------+-------------------------------+
| LEFT PANEL (Macro & Structure)    | CENTER PANEL (Interactive Chart)    | RIGHT PANEL (Execution & Risk)|
+-----------------------------------+-------------------------------------+-------------------------------+
| • Multi-TF Confluence Score       | • Synced Lightweight Chart          | • M5 Candle Timer: [02:22]    |
|   - H1: 🟢 Bullish (Above 200EMA) |   - Timeframe Switcher (H1/M15/M5)  | • Live Signal / Setup Status  |
|   - M15: 🟢 Above Session VWAP    |   - Automated Overlays:             |   - Asia Low Swept: [YES]     |
|   - M5: 🟢 Bullish CHoCH + FVG    |     * Asia High/Low Range Box       |   - FVG Mitigation: [ACTIVE]  |
| • ADR Range Progress Bar          |     * Session VWAP ±1/2σ Lines      | • Dynamic Lot Calculator:     |
|   - 54% Used ($17.40 / $32.00)    |     * M5/M15 Fair Value Gaps        |   - Balance: $10,000          |
| • Session Reference Levels:       |     * PDH / PDL Horizontal Lines    |   - Risk (1%): $100           |
|   - Asia High: $2,940.50          |                                     |   - SL (1.5x ATR): $2.85      |
|   - Asia Low: $2,928.00 (Swept)   |                                     |   - Calculated Lots: 0.35     |
|   - PDH: $2,948.10 | PDL: $2,918  |                                     | • Real-time Alerts Log Feed   |
+-----------------------------------+-------------------------------------+-------------------------------+
```

---

## 7. Key Decisions & Rationale

1. **Zero-Auth Public WebSocket Proxy by Default:** Allows immediate local testing and running on Linux without installing Windows MT5 emulators or managing paid API subscriptions. Architecture includes config switches for OANDA API or MT5 bridge.
2. **Lightweight Charts v4 over Heavy Charting Libraries:** High frame-rate, sub-millisecond DOM updates, lightweight footprint, and official TradingView open-source library.
3. **Background Indicator Calculation:** Indicators are calculated by the Python backend on incoming bars, sending clean summarized badges to the frontend to keep the visual charts clean and eliminate chart lag.

