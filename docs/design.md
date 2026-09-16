# Design System: XAUUSD Real-Time Terminal (GitHub Primer Dark Style)

## 1. Locked Archetype: GitHub Dark Primer Terminal
* **Aesthetic:** Clean, utilitarian, developer-centric GitHub Dark UI.
* **Density:** Crisp 1px `#30363d` borders, `#0d1117` canvas, `#161b22` panels, `#21262d` headers, rounded-md (6px) corners.
* **Badges & Pills:** GitHub CounterBadge and Label styling (`border: 1px solid`, subtle alpha backgrounds).
* **Target Audience:** Traders & developers wanting high information density with zero eye strain and zero AI slop.

---

## 2. Color Palette (GitHub Primer Dark)

```css
:root {
  /* Surfaces & Backgrounds (GitHub Primer Dark) */
  --bg-app: #0d1117;              /* GitHub main canvas default */
  --bg-panel: #161b22;            /* GitHub elevated panel/card */
  --bg-panel-header: #21262d;     /* GitHub subheader / table header */
  --bg-subtle: #1f242c;           /* Hover / inset background */
  
  /* Borders (GitHub Primer) */
  --border-subtle: #30363d;       /* GitHub default 1px border */
  --border-muted: #21262d;        /* Sub-divider line */
  --border-active: #58a6ff;       /* GitHub focus / active state */

  /* Semantic & Financial Colors */
  --gold-accent: #e3b341;         /* GitHub attention yellow / Gold */
  --gold-dim: #9e6a03;            /* Dark gold border/badge */
  --bullish-green: #3fb950;       /* GitHub success green */
  --bullish-green-bg: rgba(46, 160, 67, 0.15);
  --bearish-red: #f85149;         /* GitHub danger red */
  --bearish-red-bg: rgba(248, 81, 73, 0.15);
  --accent-blue: #58a6ff;         /* GitHub link / info blue */
  --accent-purple: #bc8cff;       /* GitHub purple / secondary */
  --neutral-gray: #8b949e;        /* GitHub muted gray */
  --neutral-bg: #21262d;

  /* Typography Colors */
  --text-primary: #f0f6fc;        /* Primary heading / crisp readable */
  --text-secondary: #c9d1d9;      /* Body / metrics text */
  --text-muted: #8b949e;          /* Muted labels & timestamps */
}
```

---

## 3. Typography & Numerical Display
* **Headings & UI Labels:** `-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"`.
* **Numbers, Indicators, Timers, Prices:** `ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace` (`font-variant-numeric: tabular-nums`).

---

## 4. UI Layout & Component Grid
* **Header (44px fixed):**
  * Breadcrumb style: `octicon` + **XAUUSD** `/` **Multi-Timeframe Terminal**
  * Ticker badges: Live XAUUSD price, Spread, DXY, US10Y in GitHub pill badges.
  * Session tag (Asia: 🟡, London: 🔵, NY: 🟢) with commit-badge style pill.
  * News countdown chip.
* **Main 3-Column Layout:**
  * **Left Column (300px):** Multi-Timeframe Confluence Matrix & Indicator Table (EMA, VWAP, Bollinger, RSI, MACD, Stoch RSI, OBV, CMF, VWMA, RVol).
  * **Center Column (Flex 1):** Lightweight Chart canvas with GitHub-styled tab bar (`M1`, `M5`, `M15`, `H1`, `H4`, `D1`), indicator toggle toolbar (`EMA`, `VWAP`, `BB`, `VWMA`, `FVG/OB`), and bottom volume / oscillator pane.
  * **Right Column (320px):** Institutional Setup Card, Risk Calculator, and Commit-Log styled Live Signal & Trade Journal.


