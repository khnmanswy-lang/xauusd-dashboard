# Design System: XAUUSD Real-Time Terminal

## 1. Locked Archetype: Deep Dark Financial Terminal
* **Aesthetic:** Tactical, clean, Bloomberg/TradingView terminal style.
* **Density:** High density with clear spatial hierarchy (1px subtle borders, no floating glassmorphism or pastel gradients).
* **Target Audience:** Active intraday & scalping traders needing split-second clarity.

---

## 2. Color Palette

```css
:root {
  /* Surface & Backgrounds */
  --bg-app: #0a0e17;            /* Deep obsidian background */
  --bg-panel: #111722;          /* Card & container panels */
  --bg-panel-header: #161f2e;   /* Panel headers & widget caps */
  --border-subtle: #1e293b;     /* 1px structural borders */
  --border-active: #334155;     /* Highlighted/focused borders */

  /* Asset & Status Colors */
  --gold-accent: #f0b90b;       /* Gold (XAUUSD) primary brand */
  --gold-dim: #997819;          /* Secondary gold accents */
  --bullish-green: #00c076;     /* Bullish / Up ticks / Buys */
  --bearish-red: #ff4d4f;       /* Bearish / Down ticks / Sells */
  --neutral-gray: #64748b;      /* Neutral / Inactive states */
  --alert-yellow: #fbbf24;      /* Warnings / News alerts */

  /* Text & Typography */
  --text-primary: #f8fafc;      /* Primary readable text */
  --text-secondary: #94a3b8;    /* Labels & timestamps */
  --text-muted: #475569;        /* Disabled & subtle hints */
}
```

---

## 3. Typography & Numerical Display
* **Headings & UI Labels:** `Inter`, `-apple-system`, `system-ui`, sans-serif.
* **Prices, Timers, Lot Sizes, Indicator Numbers:** `JetBrains Mono`, `Roboto Mono`, monospace (with tabular figures `font-variant-numeric: tabular-nums` to eliminate jitter when live ticks arrive).

---

## 4. UI Layout & Component Grid
* **Header (48px fixed):**
  * Ticker badges: Live XAUUSD, Spread, DXY, US10Y.
  * Active Session tag with pulse indicator (Asia: 🟡, London: 🔵, New York: 🟢).
  * High-Impact News countdown with warning badge if $< 15\text{m}$.
* **Main Canvas (3-column responsive grid):**
  * **Left Column (280px):** Multi-Timeframe Confluence Matrix & ADR Progress Meter.
  * **Center Column (Flex 1):** TradingView Lightweight Chart canvas with timeframe buttons (H1, M15, M5) and overlay toggles.
  * **Right Column (300px):** M5 Candle Countdown circular/digital gauge, Dynamic Lot Calculator, Real-Time Alert Log.
