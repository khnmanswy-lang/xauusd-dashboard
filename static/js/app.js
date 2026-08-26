/**
 * Main Application Client for XAUUSD Multi-Timeframe Dashboard.
 * Coordinates WebSocket streaming, reactive DOM updates, dynamic risk sizing,
 * and comprehensive Quantitative Indicator Interpretation Matrix.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Clean Chart (Candles + EMA 50 + EMA 200)
  const dashboardChart = new DashboardChart('chart-canvas');

  // State caches
  let latestState = null;
  let lastPrice = null;
  let m5SecondsRemaining = 300;
  let newsSecondsRemaining = 0;
  let ws = null;
  let reconnectTimer = null;

  // DOM Elements - Header
  const elTzLabel = document.getElementById('tz-label');
  const elPrice = document.getElementById('xauusd-price');
  const elSpread = document.getElementById('xauusd-spread');
  const elDxyVal = document.getElementById('dxy-val');
  const elDxyChg = document.getElementById('dxy-chg');
  const elUs10yVal = document.getElementById('us10y-val');
  const elUs10yChg = document.getElementById('us10y-chg');
  const elSessionDot = document.getElementById('session-dot');
  const elSessionLabel = document.getElementById('session-label');
  const elKillzoneLabel = document.getElementById('killzone-label');
  const elNewsChip = document.getElementById('news-chip');
  const elNewsName = document.getElementById('news-name');
  const elNewsTimer = document.getElementById('news-timer');
  const elWsIndicator = document.getElementById('ws-indicator');

  // Detect and display User Local Timezone
  const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';
  const tzOffsetMin = -new Date().getTimezoneOffset();
  const tzOffsetHours = Math.floor(Math.abs(tzOffsetMin) / 60);
  const tzOffsetMins = Math.abs(tzOffsetMin) % 60;
  const tzSign = tzOffsetMin >= 0 ? '+' : '-';
  const tzFormatted = `UTC${tzSign}${tzOffsetHours}${tzOffsetMins > 0 ? `:${tzOffsetMins}` : ''}`;
  if (elTzLabel) {
    elTzLabel.textContent = `${tzFormatted} (${userTimezone.split('/').pop()})`;
    elTzLabel.title = `Detected Local Timezone: ${userTimezone} (${tzFormatted})`;
  }

  // DOM Elements - Left Column: Confluence & Interpretations Matrix
  const elConfluenceBanner = document.getElementById('overall-confluence-banner');
  const elH1Badge = document.getElementById('h1-badge');
  const elM15Badge = document.getElementById('m15-badge');
  const elM5Badge = document.getElementById('m5-badge');

  // Matrix items
  const elMatrixVwapVal = document.getElementById('matrix-vwap-val');
  const elMatrixVwapBadge = document.getElementById('matrix-vwap-badge');
  const elMatrixVwapInterp = document.getElementById('matrix-vwap-interp');

  const elMatrixRsiVal = document.getElementById('matrix-rsi-val');
  const elMatrixRsiBadge = document.getElementById('matrix-rsi-badge');
  const elMatrixRsiInterp = document.getElementById('matrix-rsi-interp');

  const elMatrixEmaBadge = document.getElementById('matrix-ema-badge');
  const elMatrixEmaInterp = document.getElementById('matrix-ema-interp');

  const elMatrixSweepBadge = document.getElementById('matrix-sweep-badge');
  const elMatrixSweepInterp = document.getElementById('matrix-sweep-interp');
  const elAsiaHigh = document.getElementById('level-asia-high');
  const elAsiaLow = document.getElementById('level-asia-low');

  const elAdrPctTag = document.getElementById('adr-pct-tag');
  const elAdrBarFill = document.getElementById('adr-bar-fill');
  const elAdrUsed = document.getElementById('adr-used');
  const elAdrTotal = document.getElementById('adr-total');
  const elMatrixAdrInterp = document.getElementById('matrix-adr-interp');

  // DOM Elements - Right Column: AI Setup Scanner & Lot Calculator
  const elBtnRescanAi = document.getElementById('btn-rescan-ai');
  const elBtnApplyAiRisk = document.getElementById('btn-apply-ai-risk');
  const elAiGradeBadge = document.getElementById('ai-grade-badge');
  const elAiConfidenceBadge = document.getElementById('ai-confidence-badge');
  const elAiHeadline = document.getElementById('ai-headline');
  const elAiThesis = document.getElementById('ai-thesis');
  const elAiBreakdownList = document.getElementById('ai-breakdown-list');
  const elAiEntryPrice = document.getElementById('ai-entry-price');
  const elAiSlPrice = document.getElementById('ai-sl-price');
  const elAiTp1Price = document.getElementById('ai-tp1-price');
  const elAiTp2Price = document.getElementById('ai-tp2-price');
  const elAiInvalidationText = document.getElementById('ai-invalidation-text');
  const elAiPsychologyText = document.getElementById('ai-psychology-text');

  const elM5TimerDisplay = document.getElementById('m5-timer-display');
  const elCalcBalance = document.getElementById('calc-balance');
  const elCalcRiskSlider = document.getElementById('calc-risk-slider');
  const elCalcRiskDisplay = document.getElementById('calc-risk-display');
  const elCalcSlSlider = document.getElementById('calc-sl-slider');
  const elCalcSlDisplay = document.getElementById('calc-sl-display');
  const elCalculatedLot = document.getElementById('calculated-lot-size');
  const elCalcRiskDollars = document.getElementById('calc-risk-dollars');
  const elCalcSlDistance = document.getElementById('calc-sl-distance');
  const elCalcSlPrice = document.getElementById('calc-sl-price');
  const elCalcTp2Price = document.getElementById('calc-tp2-price');
  const elAlertFeedList = document.getElementById('alert-feed-list');

  let latestAiAnalysis = null;
  let customAiSlDistance = null;

  // ==========================================================================
  // WebSocket Client
  // ==========================================================================
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("Connected to XAUUSD WebSocket stream.");
      elWsIndicator.classList.remove('ws-offline');
      elWsIndicator.title = "WebSocket Connected";
      addAlert("Live market feed connected.", "system");
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'pong') return;

        if (message.type === 'AI_ANALYSIS_UPDATE') {
          renderAiAnalysis(message.data);
          addAlert(`AI Setup Updated: [${message.data.setup_grade}] ${message.data.headline}`, 'sweep');
          return;
        }

        if (message.type === 'AUTO_TRADE_UPDATE') {
          const tData = message.data;
          if (tData.status === 'EXECUTED') {
            addAlert(`🚀 Auto-Executed: [${tData.direction}] ${tData.units} units @ $${tData.entry_price.toFixed(2)} | SL: $${tData.stop_loss.toFixed(2)}`, 'sweep');
          } else if (tData.status === 'TRAILING_UPDATED') {
            addAlert(`🛡️ Trailed SL to Break-Even: Trade #${tData.trade_id} (SL: $${tData.new_stop_loss.toFixed(2)}) | Profit: +$${tData.profit_usd.toFixed(2)}`, 'sweep');
          }
          return;
        }

        latestState = message;
        renderState(message);
      } catch (e) {
        console.error("Error parsing WS state:", e);
      }
    };

    ws.onclose = () => {
      elWsIndicator.classList.add('ws-offline');
      elWsIndicator.title = "WebSocket Disconnected - Reconnecting...";
      reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.warn("WebSocket error:", err);
      ws.close();
    };
  }

  // ==========================================================================
  // State Rendering
  // ==========================================================================
  function renderState(state) {
    if (!state || !state.xauusd) return;

    const gold = state.xauusd;
    const currentPrice = gold.price;

    // 1. Render Price with Tick Color Flash
    elPrice.textContent = `$${currentPrice.toFixed(2)}`;
    elSpread.textContent = gold.spread.toFixed(2);

    if (lastPrice !== null && lastPrice !== currentPrice) {
      if (currentPrice > lastPrice) {
        elPrice.classList.remove('price-flash-down');
        elPrice.classList.add('price-flash-up');
      } else {
        elPrice.classList.remove('price-flash-up');
        elPrice.classList.add('price-flash-down');
      }
      setTimeout(() => {
        elPrice.classList.remove('price-flash-up', 'price-flash-down');
      }, 300);
    }
    lastPrice = currentPrice;

    // 2. Macro Tickers
    if (state.macro) {
      if (state.macro.dxy) {
        elDxyVal.textContent = state.macro.dxy.price.toFixed(2);
        const chg = state.macro.dxy.change_pct;
        elDxyChg.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
        elDxyChg.className = `num ${chg >= 0 ? 'chip-up' : 'chip-down'}`;
      }
      if (state.macro.us10y) {
        elUs10yVal.textContent = `${state.macro.us10y.price.toFixed(2)}%`;
        const chg = state.macro.us10y.change_pct;
        elUs10yChg.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
        elUs10yChg.className = `num ${chg >= 0 ? 'chip-up' : 'chip-down'}`;
      }
    }

    // 3. Active Session & Killzone
    if (state.session) {
      const sess = state.session.active_session;
      elSessionLabel.textContent = sess;
      elKillzoneLabel.textContent = `[${state.session.killzone || 'NONE'}]`;

      elSessionDot.className = 'session-dot';
      if (sess === 'ASIA') elSessionDot.classList.add('dot-asia');
      else if (sess === 'LONDON') elSessionDot.classList.add('dot-london');
      else if (sess === 'NEW_YORK') elSessionDot.classList.add('dot-ny');
      else elSessionDot.classList.add('dot-closed');

      if (elAsiaHigh) elAsiaHigh.textContent = state.session.asia_high ? `$${state.session.asia_high.toFixed(2)}` : '--';
      if (elAsiaLow) elAsiaLow.textContent = state.session.asia_low ? `$${state.session.asia_low.toFixed(2)}` : '--';

      if (state.session.recent_sweep) {
        addAlert(`Liquidity Sweep: ${state.session.recent_sweep} at $${currentPrice.toFixed(2)}`, 'sweep');
      }
    }

    // 4. News Countdown
    if (state.news) {
      elNewsName.textContent = state.news.next_event;
      newsSecondsRemaining = state.news.countdown_seconds;
      if (state.news.guard_active) {
        elNewsChip.classList.add('news-alert-active');
      } else {
        elNewsChip.classList.remove('news-alert-active');
      }
    }

    // 5. MTF Confluence Bias
    if (state.confluence_matrix) {
      const conf = state.confluence_matrix;
      elConfluenceBanner.textContent = conf.overall_score || '0 NEUTRAL';
      elConfluenceBanner.className = 'confluence-banner';
      if (conf.score_value > 0) elConfluenceBanner.classList.add('banner-bullish');
      else if (conf.score_value < 0) elConfluenceBanner.classList.add('banner-bearish');
      else elConfluenceBanner.classList.add('banner-neutral');

      if (conf.h1) {
        elH1Badge.textContent = `${conf.h1.bias} (> 200 EMA)`;
        elH1Badge.className = `tf-badge ${conf.h1.bias === 'BULLISH' ? 'badge-bull' : 'badge-bear'}`;
      }
      if (conf.m15) {
        elM15Badge.textContent = conf.m15.structure;
        elM15Badge.className = `tf-badge ${conf.m15.structure.includes('BULLISH') ? 'badge-bull' : 'badge-bear'}`;
      }
      if (conf.m5) {
        elM5Badge.textContent = conf.m5.signal;
        elM5Badge.className = `tf-badge ${conf.m5.signal.includes('BUY') ? 'badge-bull' : (conf.m5.signal.includes('SELL') ? 'badge-bear' : 'badge-neut')}`;
      }
    }

    // 6. Quantitative Indicator Matrix with Interpretations
    if (state.indicators_matrix) {
      const mat = state.indicators_matrix;

      // VWAP Interpretation
      if (mat.vwap) {
        elMatrixVwapVal.textContent = mat.vwap.value ? `$${mat.vwap.value.toFixed(2)}` : '--';
        elMatrixVwapBadge.textContent = mat.vwap.status;
        elMatrixVwapBadge.className = `tf-badge ${mat.vwap.status.includes('BULLISH') ? 'badge-bull' : (mat.vwap.status.includes('BEARISH') ? 'badge-bear' : 'badge-neut')}`;
        elMatrixVwapInterp.textContent = mat.vwap.interpretation;
      }

      // RSI Interpretation
      if (mat.rsi) {
        elMatrixRsiVal.textContent = mat.rsi.value ? mat.rsi.value.toFixed(1) : '--';
        elMatrixRsiBadge.textContent = mat.rsi.status;
        elMatrixRsiBadge.className = `tf-badge ${mat.rsi.status.includes('BULLISH') ? 'badge-bull' : (mat.rsi.status.includes('BEARISH') ? 'badge-bear' : 'badge-neut')}`;
        elMatrixRsiInterp.textContent = mat.rsi.interpretation;
      }

      // EMA Interpretation
      if (mat.ema) {
        elMatrixEmaBadge.textContent = mat.ema.status;
        elMatrixEmaBadge.className = `tf-badge ${mat.ema.status.includes('BULLISH') ? 'badge-bull' : (mat.ema.status.includes('BEARISH') ? 'badge-bear' : 'badge-neut')}`;
        elMatrixEmaInterp.textContent = mat.ema.interpretation;
      }

      // Structure / Liquidity Interpretation
      if (mat.structure) {
        elMatrixSweepBadge.textContent = mat.structure.status;
        elMatrixSweepBadge.className = `tf-badge ${mat.structure.status.includes('BULLISH') ? 'badge-bull' : (mat.structure.status.includes('BEARISH') ? 'badge-bear' : 'badge-neut')}`;
        elMatrixSweepInterp.textContent = mat.structure.interpretation;
      }

      // ADR Interpretation
      if (mat.adr) {
        elMatrixAdrInterp.textContent = mat.adr.interpretation;
      }

      // FVG Interpretation
      if (mat.fvg && elMatrixFvgInterp) {
        elMatrixFvgInterp.textContent = mat.fvg.interpretation;
      }
    }

    // 7. Volatility & ADR meter
    if (state.volatility) {
      const vol = state.volatility;
      elAdrPctTag.textContent = `${vol.adr_used_pct}%`;
      elAdrBarFill.style.width = `${Math.min(vol.adr_used_pct, 100)}%`;
      elAdrUsed.textContent = vol.adr_used ? vol.adr_used.toFixed(2) : '--';
      elAdrTotal.textContent = vol.adr_total ? vol.adr_total.toFixed(2) : '--';
    }

    // 8. Update Chart (Live Candle)
    dashboardChart.updateCandle(gold);

    // 9. Update M5 Timer
    m5SecondsRemaining = gold.candle_timer_m5 || 300;

    // 10. Update AI Analysis Card if present
    if (state.ai_analysis) {
      renderAiAnalysis(state.ai_analysis);
    }

    // 11. Recalculate Dynamic Lot Sizer
    recalculateLotSize();
  }

  // ==========================================================================
  // AI Setup Analysis Renderer
  // ==========================================================================
  function renderAiAnalysis(aiData) {
    if (!aiData) return;
    latestAiAnalysis = aiData;

    // 1. Grade Badge & Plan Status
    const grade = aiData.setup_grade || 'NO_SETUP';
    const dir = aiData.direction || 'NEUTRAL';
    const status = aiData.plan_status || 'NO_SETUP';

    if (elAiGradeBadge) {
      let statusText = `${grade.replace('_', ' ')} ${dir === 'BULLISH_LONG' ? 'LONG' : (dir === 'BEARISH_SHORT' ? 'SHORT' : '')}`.trim();
      if (status === 'WAITING_FOR_TRIGGER') {
        statusText = `⏳ PENDING TRIGGER (${dir.replace('_', ' ')})`;
      } else if (status === 'PLAN_REJECTED') {
        statusText = `❌ PLAN CANCELLED`;
      } else if (status === 'ACTIVE_MANAGEMENT') {
        statusText = `🛡️ ACTIVE (TRAILING)`;
      }

      elAiGradeBadge.textContent = statusText;
      elAiGradeBadge.className = `tf-badge ${
        status === 'READY_TO_EXECUTE' ? (dir === 'BULLISH_LONG' ? 'badge-bull' : 'badge-bear') :
        (status === 'WAITING_FOR_TRIGGER' ? 'badge-neut' :
        (status === 'PLAN_REJECTED' ? 'badge-bear' : 'badge-neut'))
      }`;
    }

    // 2. Confidence Tag
    if (elAiConfidenceBadge) {
      const conf = Math.round((aiData.confidence_score || 0.0) * 100);
      elAiConfidenceBadge.textContent = `${conf}%`;
    }

    // 3. Headline & Thesis
    if (elAiHeadline) elAiHeadline.textContent = aiData.headline || 'Analyzing market structure...';
    if (elAiThesis) elAiThesis.textContent = aiData.thesis || '';

    // 4. Breakdown Bullets (including handover notes or rejection reason)
    if (elAiBreakdownList && Array.isArray(aiData.order_flow_breakdown)) {
      elAiBreakdownList.innerHTML = '';
      
      if (aiData.handover_notes) {
        const liHandover = document.createElement('li');
        liHandover.style.color = 'var(--gold-accent)';
        liHandover.style.fontWeight = '600';
        liHandover.textContent = `📋 Handover: ${aiData.handover_notes}`;
        elAiBreakdownList.appendChild(liHandover);
      }
      
      if (aiData.rejection_reason) {
        const liRejection = document.createElement('li');
        liRejection.style.color = '#fb7185';
        liRejection.style.fontWeight = '600';
        liRejection.textContent = `🚫 Rejection: ${aiData.rejection_reason}`;
        elAiBreakdownList.appendChild(liRejection);
      }

      aiData.order_flow_breakdown.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        elAiBreakdownList.appendChild(li);
      });
    }

    // 5. Actionable Execution Levels
    const exec = aiData.execution_plan || {};
    if (elAiEntryPrice) elAiEntryPrice.textContent = exec.entry ? `$${exec.entry.toFixed(2)}` : '--';
    if (elAiSlPrice) elAiSlPrice.textContent = exec.stop_loss ? `$${exec.stop_loss.toFixed(2)}` : '--';
    if (elAiTp1Price) elAiTp1Price.textContent = exec.take_profit_1 ? `$${exec.take_profit_1.toFixed(2)}` : '--';
    if (elAiTp2Price) elAiTp2Price.textContent = exec.take_profit_2 ? `$${exec.take_profit_2.toFixed(2)}` : '--';

    // 6. Invalidation & Psychology Callouts
    if (elAiInvalidationText) {
      if (aiData.rejection_reason) {
        elAiInvalidationText.textContent = `INVALIDATED: ${aiData.rejection_reason}`;
      } else if (aiData.trigger_condition && aiData.trigger_condition.description) {
        elAiInvalidationText.textContent = `CRON CONDITION: ${aiData.trigger_condition.description}`;
      } else {
        elAiInvalidationText.textContent = exec.invalidation || 'Awaiting setup confirmation.';
      }
    }
    if (elAiPsychologyText) elAiPsychologyText.textContent = aiData.psychology_warning || 'Maintain strict 1% risk discipline.';

    // 7. Render Visual Trade Setup & Rate Zone Lines on Interactive Chart
    if (dashboardChart && typeof dashboardChart.renderTradeSetupOverlay === 'function') {
      dashboardChart.renderTradeSetupOverlay(aiData);
    }
  }

  // ==========================================================================
  // Dynamic Lot Calculator Logic
  // ==========================================================================
  function recalculateLotSize() {
    const balance = parseFloat(elCalcBalance.value) || 10000.0;
    const riskPct = parseFloat(elCalcRiskSlider.value) || 1.0;
    const slMult = parseFloat(elCalcSlSlider.value) || 1.5;
    
    elCalcRiskDisplay.textContent = `${riskPct.toFixed(2)}%`;
    elCalcSlDisplay.textContent = `${slMult.toFixed(1)}x`;

    const atrM5 = (latestState && latestState.volatility && latestState.volatility.atr_m5) ? latestState.volatility.atr_m5 : 2.20;
    const currentPrice = (latestState && latestState.xauusd) ? latestState.xauusd.price : 2935.0;

    const riskAmount = balance * (riskPct / 100.0);
    const slDistance = customAiSlDistance || Math.max(0.20, atrM5 * slMult);
    const calculatedLots = Math.max(0.01, roundNum(riskAmount / (slDistance * 100.0), 2));

    elCalculatedLot.textContent = calculatedLots.toFixed(2);
    elCalcRiskDollars.textContent = riskAmount.toFixed(2);
    elCalcSlDistance.textContent = slDistance.toFixed(2);

    const slPrice = currentPrice - slDistance;
    const tp2Price = currentPrice + (2.0 * slDistance);

    elCalcSlPrice.textContent = `$${slPrice.toFixed(2)}`;
    elCalcTp2Price.textContent = `$${tp2Price.toFixed(2)}`;
  }

  // Bind calculator inputs & buttons
  elCalcBalance.addEventListener('input', () => { customAiSlDistance = null; recalculateLotSize(); });
  elCalcRiskSlider.addEventListener('input', () => { recalculateLotSize(); });
  elCalcSlSlider.addEventListener('input', () => { customAiSlDistance = null; recalculateLotSize(); });

  if (elBtnApplyAiRisk) {
    elBtnApplyAiRisk.addEventListener('click', () => {
      if (latestAiAnalysis && latestAiAnalysis.execution_plan) {
        const exec = latestAiAnalysis.execution_plan;
        if (exec.entry && exec.stop_loss) {
          const dist = Math.abs(exec.entry - exec.stop_loss);
          customAiSlDistance = dist;
          recalculateLotSize();
          addAlert(`Applied AI Levels: Entry $${exec.entry.toFixed(2)} | SL $${exec.stop_loss.toFixed(2)} (Dist: $${dist.toFixed(2)})`, 'general');
        }
      }
    });
  }

  // ==========================================================================
  // On-Demand AI Market Re-Evaluation
  // ==========================================================================
  async function triggerAiRescan() {
    if (!elBtnRescanAi) return;
    elBtnRescanAi.classList.add('scanning');
    elBtnRescanAi.disabled = true;
    elBtnRescanAi.innerHTML = `<span class="btn-icon">⏳</span><span>Scanning...</span>`;

    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('request_ai_analysis');
      } else {
        const res = await fetch('/api/ai/analyze', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          renderAiAnalysis(data);
          addAlert(`AI Setup Re-Scanned: [${data.setup_grade}] ${data.headline}`, 'sweep');
        }
      }
    } catch (e) {
      console.error("Error triggering AI re-scan:", e);
    } finally {
      setTimeout(() => {
        elBtnRescanAi.classList.remove('scanning');
        elBtnRescanAi.disabled = false;
        elBtnRescanAi.innerHTML = `<span class="btn-icon">⚡</span><span>Re-Scan AI</span>`;
      }, 600);
    }
  }

  if (elBtnRescanAi) {
    elBtnRescanAi.addEventListener('click', triggerAiRescan);
  }

  // ==========================================================================
  // Clocks & Timers Loop (1 Second Interval)
  // ==========================================================================
  setInterval(() => {
    // M5 Countdown
    if (m5SecondsRemaining > 0) m5SecondsRemaining--;
    const m5Mins = Math.floor(m5SecondsRemaining / 60);
    const m5Secs = m5SecondsRemaining % 60;
    elM5TimerDisplay.textContent = `${String(m5Mins).padStart(2, '0')}:${String(m5Secs).padStart(2, '0')}`;

    // News Countdown
    if (newsSecondsRemaining > 0) newsSecondsRemaining--;
    const nHours = Math.floor(newsSecondsRemaining / 3600);
    const nMins = Math.floor((newsSecondsRemaining % 3600) / 60);
    const nSecs = newsSecondsRemaining % 60;
    elNewsTimer.textContent = `${String(nHours).padStart(2, '0')}:${String(nMins).padStart(2, '0')}:${String(nSecs).padStart(2, '0')}`;
  }, 1000);

  // ==========================================================================
  // Alerts Feed Helper
  // ==========================================================================
  const alertCache = new Set();
  function addAlert(message, type = 'general') {
    const timeStr = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    const key = `${timeStr}-${message}`;
    if (alertCache.has(key)) return;
    alertCache.add(key);

    const item = document.createElement('div');
    item.className = `alert-item ${type === 'sweep' ? 'alert-item-sweep' : (type === 'news' ? 'alert-item-news' : '')}`;
    item.innerHTML = `
      <div class="alert-time num">${timeStr} Local</div>
      <div class="alert-msg">${message}</div>
    `;

    elAlertFeedList.prepend(item);
    if (elAlertFeedList.children.length > 25) {
      elAlertFeedList.removeChild(elAlertFeedList.lastChild);
    }
  }

  // ==========================================================================
  // Toolbar Buttons: Timeframe & EMA Toggles
  // ==========================================================================
  document.querySelectorAll('.tf-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tf = btn.dataset.tf;
      dashboardChart.loadHistory(tf);
      addAlert(`Timeframe switched to ${tf}`, 'general');
    });
  });

  const btnEma50 = document.getElementById('toggle-ema50');
  if (btnEma50) {
    btnEma50.addEventListener('click', () => {
      btnEma50.classList.toggle('active');
      dashboardChart.toggleEma50(btnEma50.classList.contains('active'));
    });
  }

  const btnEma200 = document.getElementById('toggle-ema200');
  if (btnEma200) {
    btnEma200.addEventListener('click', () => {
      btnEma200.classList.toggle('active');
      dashboardChart.toggleEma200(btnEma200.classList.contains('active'));
    });
  }

  // ==========================================================================
  // CSV Trade Journal Export Handlers
  // ==========================================================================
  function exportTradeJournal() {
    addAlert("Exporting XAUUSD Trade Journal (CSV)...", "general");
    const downloadUrl = "/api/journal/export";
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `xauusd_trade_journal_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  const btnExportTop = document.getElementById("btn-export-journal-top");
  if (btnExportTop) {
    btnExportTop.addEventListener("click", exportTradeJournal);
  }

  const btnExportCard = document.getElementById("btn-export-journal");
  if (btnExportCard) {
    btnExportCard.addEventListener("click", exportTradeJournal);
  }

  // ==========================================================================
  // AutoTrader Status & Toggle Controller
  // ==========================================================================
  const elAutoTraderChip = document.getElementById('autotrader-chip');
  const elAutoTraderLabel = document.getElementById('autotrader-label');

  async function initAutoTrader() {
    try {
      const res = await fetch('/api/autotrader/status');
      if (res.ok) {
        const data = await res.json();
        updateAutoTraderUI(data.enabled);
      }
    } catch (e) {
      console.debug("Could not fetch autotrader status:", e);
    }
  }

  function updateAutoTraderUI(enabled) {
    if (!elAutoTraderChip) return;
    if (enabled) {
      elAutoTraderChip.className = 'autotrader-chip active';
      if (elAutoTraderLabel) elAutoTraderLabel.textContent = 'AUTO-TRADER: ON';
    } else {
      elAutoTraderChip.className = 'autotrader-chip paused';
      if (elAutoTraderLabel) elAutoTraderLabel.textContent = 'AUTO-TRADER: OFF';
    }
  }

  if (elAutoTraderChip) {
    elAutoTraderChip.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/autotrader/toggle', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          updateAutoTraderUI(data.enabled);
          addAlert(`Auto-Trader ${data.enabled ? 'ENABLED' : 'PAUSED'} on OANDA Practice Account.`, 'general');
        }
      } catch (e) {
        console.error("Error toggling autotrader:", e);
      }
    });
  }

  // Initialize
  initAutoTrader();

  // Start WebSocket
  connectWebSocket();
});

function roundNum(val, dec = 2) {
  return parseFloat(Number(val).toFixed(dec));
}
