/**
 * XAUUSD Institutional Multi-Timeframe Algorithmic Terminal (M1, M15, H1, H4).
 * Pure JavaScript, 0 LLM dependencies, WebSocket live state synchronizer.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize 4-Timeframe Simultaneous Multi-Chart Grid (M1, M15, H1, H4)
  const multiChartGrid = window.initDashboardCharts ? window.initDashboardCharts() : null;

  // DOM Elements - Top Macro Bar (6 Cells)
  const elTopBid = document.getElementById('top-bid');
  const elTopAsk = document.getElementById('top-ask');
  const elTopSpread = document.getElementById('top-spread');
  const elTopVol = document.getElementById('top-vol');
  const elTopChg = document.getElementById('top-chg');

  const elTopSessPrimary = document.getElementById('top-sess-primary');
  const elTopSessSecondary = document.getElementById('top-sess-secondary');

  const elTopAdrTotal = document.getElementById('top-adr-total');
  const elTopAdrUsed = document.getElementById('top-adr-used');
  const elTopAdrPct = document.getElementById('top-adr-pct');

  const elTopDayHigh = document.getElementById('top-day-high');
  const elTopDayLow = document.getElementById('top-day-low');

  const elTopDxy = document.getElementById('top-dxy');
  const elTopUs10y = document.getElementById('top-us10y');
  const elTopNextEvent = document.getElementById('top-next-event');
  const elTopNextTime = document.getElementById('top-next-time');

  // DOM Elements - Chart Floating HUDs (Tailored per Timeframe Role)
  const elPillM1Ema9 = document.getElementById('pill-m1-ema9');
  const elPillM1Vwap = document.getElementById('pill-m1-vwap');
  const elPillM1Of = document.getElementById('pill-m1-of');
  const elPillM15Ema9 = document.getElementById('pill-m15-ema9');
  const elPillM15Ema21 = document.getElementById('pill-m15-ema21');
  const elPillM15Range = document.getElementById('pill-m15-range');
  const elPillH1Ema50 = document.getElementById('pill-h1-ema50');
  const elPillH1Ema200 = document.getElementById('pill-h1-ema200');
  const elPillH1Pp = document.getElementById('pill-h1-pp');
  const elPillH1Atr = document.getElementById('pill-h1-atr');
  const elPillH4Ema50 = document.getElementById('pill-h4-ema50');
  const elPillH4Ema200 = document.getElementById('pill-h4-ema200');
  const elPillH4Sweep = document.getElementById('pill-h4-sweep');
  const elPillH4Atr = document.getElementById('pill-h4-atr');

  // DOM Elements - Right Sidebar (Multi-TF RSI, Pivots, Order Flow)
  const elRsiM1Val = document.getElementById('rsi-m1-val');
  const elRsiM1Tag = document.getElementById('rsi-m1-tag');
  const elRsiM15Val = document.getElementById('rsi-m15-val');
  const elRsiM15Tag = document.getElementById('rsi-m15-tag');
  const elRsiH1Val = document.getElementById('rsi-h1-val');
  const elRsiH1Tag = document.getElementById('rsi-h1-tag');
  const elRsiH4Val = document.getElementById('rsi-h4-val');
  const elRsiH4Tag = document.getElementById('rsi-h4-tag');

  const elPivotPp = document.getElementById('pivot-pp');
  const elPivotR1 = document.getElementById('pivot-r1');
  const elPivotR2 = document.getElementById('pivot-r2');
  const elPivotS1 = document.getElementById('pivot-s1');
  const elPivotS2 = document.getElementById('pivot-s2');

  const elOfBuyPct = document.getElementById('of-buy-pct');
  const elWsIndicator = document.getElementById('ws-indicator');

  let ws = null;
  let reconnectTimer = null;

  // ==========================================================================
  // Real-Time WebSocket Connector
  // ==========================================================================
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    if (ws) {
      try { ws.close(); } catch (e) {}
    }

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (elWsIndicator) {
        elWsIndicator.className = 'ws-status';
        elWsIndicator.title = "Live Market Stream Connected";
      }
    };

    ws.onmessage = (event) => {
      try {
        const state = JSON.parse(event.data);
        renderState(state);
      } catch (e) {
        console.error("Error parsing WS state:", e);
      }
    };

    ws.onclose = () => {
      if (elWsIndicator) {
        elWsIndicator.className = 'ws-status offline';
        elWsIndicator.title = "WebSocket Disconnected - Reconnecting...";
      }
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = (err) => {
      console.debug("WebSocket error:", err);
      ws.close();
    };
  }

  // ==========================================================================
  // State Rendering Loop
  // ==========================================================================
  function renderState(state) {
    if (!state || !state.xauusd) return;

    const gold = state.xauusd;
    const price = gold.price;
    const bid = gold.bid || (price - 0.10);
    const ask = gold.ask || (price + 0.10);
    const spread = gold.spread || (ask - bid);

    // 1. Update 4-Timeframe Candlestick Charts
    if (multiChartGrid) {
      multiChartGrid.updateCandle(price, gold.volume || 1.0, state.timestamp || Math.floor(Date.now() / 1000));
    }

    // 2. Top Macro Bar - Cell 1 (Symbol & Bid/Ask)
    if (elTopBid) elTopBid.textContent = bid.toFixed(2);
    if (elTopAsk) elTopAsk.textContent = ask.toFixed(2);

    // Cell 2 (Spread, Vol, Change)
    if (elTopSpread) {
      elTopSpread.textContent = gold.spread_formatted || `$${spread.toFixed(2)} (${(spread / 0.1).toFixed(1)} pips)`;
    }
    if (elTopVol) {
      const volStatus = gold.volume_status || "NORMAL";
      elTopVol.textContent = volStatus === "VOLUME_CLIMAX" ? "Climax" : (volStatus === "HIGH" ? "High" : "Normal");
      elTopVol.style.color = volStatus === "VOLUME_CLIMAX" ? "var(--bear-red)" : "var(--gold-accent)";
    }
    if (elTopChg) {
      const chg = gold.change_pct || 0.0;
      elTopChg.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
      elTopChg.className = `num ${chg >= 0 ? 'chip-up' : 'chip-down'}`;
    }

    // Cell 3 (Session Status)
    if (state.session) {
      const activeSess = state.session.active_session || "LONDON";
      const killzone = state.session.killzone;
      if (elTopSessPrimary) elTopSessPrimary.textContent = `● ${activeSess} (${killzone ? 'Open' : 'Active'})`;
      if (elTopSessSecondary) {
        if (activeSess === "LONDON") elTopSessSecondary.textContent = "○ NY (Pre)";
        else if (activeSess === "NEW_YORK") elTopSessSecondary.textContent = "○ ASIA (Closed)";
        else elTopSessSecondary.textContent = "○ LONDON (Pre)";
      }
    }

    // Cell 4 (ADR 20D Capacity)
    if (state.volatility) {
      const adr = state.volatility;
      if (elTopAdrTotal) elTopAdrTotal.textContent = (adr.adr_total || 34.20).toFixed(2);
      if (elTopAdrUsed) elTopAdrUsed.textContent = (adr.adr_used || 21.80).toFixed(2);
      if (elTopAdrPct) elTopAdrPct.textContent = `${(adr.adr_used_pct || 63.7).toFixed(1)}%`;
    }

    // Cell 5 (Daily Range H-L)
    if (state.daily_range) {
      if (elTopDayHigh) elTopDayHigh.textContent = state.daily_range.high.toFixed(2);
      if (elTopDayLow) elTopDayLow.textContent = state.daily_range.low.toFixed(2);
    }

    // Cell 6 (Macro DXY, US10Y & News)
    if (state.macro) {
      if (state.macro.dxy && elTopDxy) elTopDxy.textContent = state.macro.dxy.price.toFixed(2);
      if (state.macro.us10y && elTopUs10y) elTopUs10y.textContent = `${state.macro.us10y.price.toFixed(2)}%`;
    }
    if (state.news) {
      if (elTopNextEvent) elTopNextEvent.textContent = state.news.next_event || "CPI";
      if (elTopNextTime) {
        elTopNextTime.textContent = state.news.scheduled_time_str || "13:30 GMT";
      }
    }

    // 3. Floating Chart HUDs (Role-Tailored)
    if (state.chart_pills) {
      const cp = state.chart_pills;
      if (cp.m1) {
        if (elPillM1Ema9) elPillM1Ema9.textContent = (cp.m1.ema9 || price).toFixed(2);
        if (elPillM1Vwap) elPillM1Vwap.textContent = cp.m1.vwap.toFixed(2);
        if (elPillM1Of) elPillM1Of.textContent = cp.m1.order_flow;
      }
      if (cp.m15) {
        if (elPillM15Ema9) elPillM15Ema9.textContent = cp.m15.ema9.toFixed(2);
        if (elPillM15Ema21) elPillM15Ema21.textContent = cp.m15.ema21.toFixed(2);
        if (elPillM15Range) elPillM15Range.textContent = (cp.m15.range || 0.0).toFixed(2);
      }
      if (cp.h1) {
        if (elPillH1Ema50) elPillH1Ema50.textContent = cp.h1.ema50.toFixed(2);
        if (elPillH1Ema200) elPillH1Ema200.textContent = cp.h1.ema200.toFixed(2);
        if (elPillH1Pp) elPillH1Pp.textContent = (cp.h1.pp || 0.0).toFixed(2);
        if (elPillH1Atr) elPillH1Atr.textContent = cp.h1.atr14.toFixed(2);
      }
      if (cp.h4) {
        if (elPillH4Ema50) elPillH4Ema50.textContent = (cp.h4.ema50 || cp.h1.ema50 || price).toFixed(2);
        if (elPillH4Ema200) elPillH4Ema200.textContent = (cp.h4.ema200 || cp.h1.ema200 || price).toFixed(2);
        if (elPillH4Sweep) elPillH4Sweep.textContent = cp.h4.sweep;
        if (elPillH4Atr) elPillH4Atr.textContent = cp.h4.atr14.toFixed(2);
      }
    }

    // 4. Right Sidebar - Multi-TF RSI
    if (state.multi_tf_rsi) {
      const rsi = state.multi_tf_rsi;
      const setRsi = (vEl, tEl, data) => {
        if (!vEl || !data) return;
        vEl.textContent = data.val.toFixed(1);
        if (tEl) {
          tEl.textContent = `[${data.tag}]`;
          tEl.className = data.tag === '▲' ? 'tag-bull' : (data.tag === '▼' ? 'tag-bear' : 'tag-neut');
        }
      };
      setRsi(elRsiM1Val, elRsiM1Tag, rsi.M1);
      setRsi(elRsiM15Val, elRsiM15Tag, rsi.M15);
      setRsi(elRsiH1Val, elRsiH1Tag, rsi.H1);
      setRsi(elRsiH4Val, elRsiH4Tag, rsi.H4);
    }

    // Right Sidebar - Pivot Points
    if (state.pivots) {
      const p = state.pivots;
      if (elPivotPp) elPivotPp.textContent = p.pp.toFixed(2);
      if (elPivotR1) elPivotR1.textContent = p.r1.toFixed(2);
      if (elPivotR2) elPivotR2.textContent = p.r2.toFixed(2);
      if (elPivotS1) elPivotS1.textContent = p.s1.toFixed(2);
      if (elPivotS2) elPivotS2.textContent = p.s2.toFixed(2);
    }

    // Right Sidebar - Order Flow Pressure
    if (state.order_flow) {
      const of = state.order_flow;
      const elOfBuy = document.getElementById('of-buy-pct');
      const elOfSell = document.getElementById('of-sell-pct');
      const elOfBar = document.getElementById('of-bar-buy');
      if (elOfBuy) elOfBuy.textContent = `${of.buy_pct}%`;
      if (elOfSell) elOfSell.textContent = `${of.sell_pct}%`;
      if (elOfBar) elOfBar.style.width = `${of.buy_pct}%`;
    }
  }

  // CSV Journal Export
  const btnExport = document.getElementById('btn-export-journal');
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      window.location.href = '/api/journal/export';
    });
  }

  // Connect WebSocket
  connectWebSocket();
});
