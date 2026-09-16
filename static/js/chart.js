/**
 * GitHub Primer Dark 4-Timeframe Simultaneous Multi-Chart Grid (M1, M15, H1, H4).
 * Pure JavaScript, zero external dependencies, ultra-low latency Lightweight Charts.
 */

function roundNum(val) {
  return typeof val === 'number' && !isNaN(val) ? Math.round(val * 100) / 100 : null;
}

/**
 * Manages an individual Lightweight Chart for a specific timeframe.
 */
class SingleTimeframeChart {
  constructor(timeframe, containerId, legendId) {
    this.timeframe = timeframe;
    this.container = document.getElementById(containerId);
    this.legendEl = document.getElementById(legendId);

    this.chart = null;
    this.candleSeries = null;
    this.volumeSeries = null;

    // Overlay series
    this.ema9Series = null;
    this.ema20Series = null;
    this.ema50Series = null;
    this.ema200Series = null;
    this.vwmaSeries = null;

    this.vwapSeries = null;
    this.vwapUpper1Series = null;
    this.vwapUpper2Series = null;
    this.vwapLower1Series = null;
    this.vwapLower2Series = null;

    this.bbUpperSeries = null;
    this.bbMiddleSeries = null;
    this.bbLowerSeries = null;

    // Overlay visibility state
    this.showEmaRibbon = true;
    this.showVwap = true;
    this.showBollinger = false;
    this.showVwma = false;
    this.showSmc = true;

    // Cache
    this.candleData = [];
    this.priceLines = [];

    this.init();
  }

  init() {
    if (!this.container || typeof LightweightCharts === 'undefined') return;

    const isDark = true;
    const bg = '#0d1117';
    const grid = '#21262d';
    const text = '#8b949e';

    this.chart = LightweightCharts.createChart(this.container, {
      width: this.container.clientWidth || 300,
      height: this.container.clientHeight || 250,
      layout: {
        background: { type: 'solid', color: bg },
        textColor: text,
        fontSize: 10,
        fontFamily: "'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace"
      },
      grid: {
        vertLines: { color: grid, style: LightweightCharts.LineStyle.Dotted },
        horzLines: { color: grid, style: LightweightCharts.LineStyle.Dotted }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: '#58a6ff', width: 1, style: LightweightCharts.LineStyle.Dashed },
        horzLine: { color: '#58a6ff', width: 1, style: LightweightCharts.LineStyle.Dashed }
      },
      rightPriceScale: {
        borderColor: '#30363d',
        autoScale: true,
        scaleMargins: { top: 0.08, bottom: 0.20 },
        alignLabels: true
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 12,
        barSpacing: 6,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          const day = String(d.getUTCDate()).padStart(2, '0');
          const mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
          const hrs = String(d.getUTCHours()).padStart(2, '0');
          const min = String(d.getUTCMinutes()).padStart(2, '0');
          if (hrs === '00' && min === '00') return `${day} ${mon}`;
          return `${hrs}:${min}`;
        }
      }
    });

    // 1. Candlestick Series (The ONLY series with right-axis price tag)
    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      lastValueVisible: true,
      priceLineVisible: true
    });

    // 2. Volume Series (De-saturated, 18% opacity, completely recedes to background)
    this.volumeSeries = this.chart.addHistogramSeries({
      color: 'rgba(110, 118, 129, 0.18)',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      lastValueVisible: false,
      priceLineVisible: false,
      scaleMargins: { top: 0.88, bottom: 0 }
    });

    // Role-tailored default visibility per timeframe
    const isM1 = this.timeframe === 'M1';
    const isM15 = this.timeframe === 'M15';
    const isH1 = this.timeframe === 'H1';
    const isH4 = this.timeframe === 'H4';

    // 3. EMA Ribbon - ZERO price scale tags (lastValueVisible: false on all)
    // EMA 9: Active on M1 (scalp trigger) and M15 (momentum)
    this.ema9Series = this.chart.addLineSeries({
      color: 'rgba(88, 166, 255, 0.85)',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: isM1 || isM15
    });

    // EMA 21: Active on M15 (intraday trend)
    this.ema20Series = this.chart.addLineSeries({
      color: 'rgba(240, 136, 62, 0.85)',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: isM15
    });

    // EMA 50: Active on H1 and H4 (intermediate trend regime)
    this.ema50Series = this.chart.addLineSeries({
      color: 'rgba(188, 140, 255, 0.85)',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: isH1 || isH4
    });

    // EMA 200: Active on H1 and H4 (master institutional trend anchor)
    this.ema200Series = this.chart.addLineSeries({
      color: '#ffffff',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: isH1 || isH4
    });

    // 4. VWMA 20 (Off by default)
    this.vwmaSeries = this.chart.addLineSeries({
      color: 'rgba(57, 197, 187, 0.60)',
      lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: false
    });

    // 5. Session VWAP (Active on M1) & Bands (Active on M15)
    this.vwapSeries = this.chart.addLineSeries({
      color: '#e3b341',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: isM1
    });

    this.vwapUpper1Series = this.chart.addLineSeries({ color: 'rgba(227, 179, 65, 0.20)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false, visible: isM15 });
    this.vwapLower1Series = this.chart.addLineSeries({ color: 'rgba(227, 179, 65, 0.20)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false, visible: isM15 });
    this.vwapUpper2Series = this.chart.addLineSeries({ color: 'rgba(227, 179, 65, 0.35)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false, visible: isM15 });
    this.vwapLower2Series = this.chart.addLineSeries({ color: 'rgba(227, 179, 65, 0.35)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false, visible: isM15 });

    // 6. Bollinger Bands (Off by default)
    this.bbUpperSeries = this.chart.addLineSeries({ color: 'rgba(88, 166, 255, 0.25)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, visible: false, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
    this.bbMiddleSeries = this.chart.addLineSeries({ color: 'rgba(88, 166, 255, 0.40)', lineWidth: 1, visible: false, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
    this.bbLowerSeries = this.chart.addLineSeries({ color: 'rgba(88, 166, 255, 0.25)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, visible: false, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });

    // Crosshair move legend updater
    this.chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !this.legendEl) return;
      const bar = param.seriesData.get(this.candleSeries);
      if (bar) {
        this.updateLegend(bar.open, bar.high, bar.low, bar.close);
      }
    });

    // Resize observer for responsive layout
    const resizeObs = new ResizeObserver(() => {
      if (this.chart && this.container) {
        this.chart.applyOptions({
          width: this.container.clientWidth,
          height: this.container.clientHeight
        });
      }
    });
    resizeObs.observe(this.container);
  }

  updateLegend(o, h, l, c) {
    if (!this.legendEl) return;
    const oEl = this.legendEl.querySelector('.o-val');
    const hEl = this.legendEl.querySelector('.h-val');
    const lEl = this.legendEl.querySelector('.l-val');
    const cEl = this.legendEl.querySelector('.c-val');
    if (oEl) oEl.textContent = o ? o.toFixed(2) : '--';
    if (hEl) hEl.textContent = h ? h.toFixed(2) : '--';
    if (lEl) lEl.textContent = l ? l.toFixed(2) : '--';
    if (cEl) {
      cEl.textContent = c ? c.toFixed(2) : '--';
      cEl.style.color = (c >= o) ? 'var(--bullish-green)' : 'var(--bearish-red)';
    }
  }

  setData(candles) {
    if (!this.chart || !candles || candles.length === 0) return;

    this.candleData = [];
    const cData = [];
    const vData = [];
    const ema9 = [];
    const ema20 = [];
    const ema50 = [];
    const ema200 = [];
    const vwma = [];
    const vwap = [];
    const vwapU1 = [];
    const vwapU2 = [];
    const vwapL1 = [];
    const vwapL2 = [];
    const bbU = [];
    const bbM = [];
    const bbL = [];

    for (const c of candles) {
      const rawT = c.time !== undefined ? c.time : c.timestamp;
      if (rawT === undefined || rawT === null) continue;
      const t = typeof rawT === 'string' ? Math.floor(new Date(rawT).getTime() / 1000) : rawT;

      const bar = {
        time: t,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume || 1.0
      };
      this.candleData.push(bar);
      cData.push({ time: t, open: c.open, high: c.high, low: c.low, close: c.close });
      vData.push({
        time: t,
        value: c.volume || 1.0,
        color: c.close >= c.open ? 'rgba(63, 185, 80, 0.15)' : 'rgba(248, 81, 73, 0.15)'
      });

      if (c.ema9 !== undefined && c.ema9 !== null) ema9.push({ time: t, value: c.ema9 });
      if (c.ema20 !== undefined && c.ema20 !== null) ema20.push({ time: t, value: c.ema20 });
      if (c.ema50 !== undefined && c.ema50 !== null) ema50.push({ time: t, value: c.ema50 });
      if (c.ema200 !== undefined && c.ema200 !== null) ema200.push({ time: t, value: c.ema200 });
      if (c.vwma20 !== undefined && c.vwma20 !== null) vwma.push({ time: t, value: c.vwma20 });
      if (c.vwap !== undefined && c.vwap !== null) vwap.push({ time: t, value: c.vwap });
      if (c.vwap_upper_1 !== undefined && c.vwap_upper_1 !== null) vwapU1.push({ time: t, value: c.vwap_upper_1 });
      if (c.vwap_upper_2 !== undefined && c.vwap_upper_2 !== null) vwapU2.push({ time: t, value: c.vwap_upper_2 });
      if (c.vwap_lower_1 !== undefined && c.vwap_lower_1 !== null) vwapL1.push({ time: t, value: c.vwap_lower_1 });
      if (c.vwap_lower_2 !== undefined && c.vwap_lower_2 !== null) vwapL2.push({ time: t, value: c.vwap_lower_2 });
      if (c.bb_upper !== undefined && c.bb_upper !== null) bbU.push({ time: t, value: c.bb_upper });
      if (c.bb_middle !== undefined && c.bb_middle !== null) bbM.push({ time: t, value: c.bb_middle });
      if (c.bb_lower !== undefined && c.bb_lower !== null) bbL.push({ time: t, value: c.bb_lower });
    }

    if (this.candleSeries && cData.length > 0) {
      this.candleSeries.setData(cData);
      if (this.volumeSeries) this.volumeSeries.setData(vData);
      if (this.ema9Series) this.ema9Series.setData(ema9);
      if (this.ema20Series) this.ema20Series.setData(ema20);
      if (this.ema50Series) this.ema50Series.setData(ema50);
      if (this.ema200Series) this.ema200Series.setData(ema200);
      if (this.vwmaSeries) this.vwmaSeries.setData(vwma);
      if (this.vwapSeries) this.vwapSeries.setData(vwap);
      if (this.vwapUpper1Series) this.vwapUpper1Series.setData(vwapU1);
      if (this.vwapUpper2Series) this.vwapUpper2Series.setData(vwapU2);
      if (this.vwapLower1Series) this.vwapLower1Series.setData(vwapL1);
      if (this.vwapLower2Series) this.vwapLower2Series.setData(vwapL2);
      if (this.bbUpperSeries) this.bbUpperSeries.setData(bbU);
      if (this.bbMiddleSeries) this.bbMiddleSeries.setData(bbM);
      if (this.bbLowerSeries) this.bbLowerSeries.setData(bbL);

      const last = this.candleData[this.candleData.length - 1];
      this.updateLegend(last.open, last.high, last.low, last.close);
      this.chart.timeScale().fitContent();
    }
  }

  updateCandle(tickPrice, tickVol, timestamp) {
    if (!this.candleSeries) return;

    const tfSeconds = { 'M1': 60, 'M15': 900, 'H1': 3600, 'H4': 14400 }[this.timeframe] || 60;
    const nowTs = timestamp || Math.floor(Date.now() / 1000);
    const barStart = Math.floor(nowTs / tfSeconds) * tfSeconds;

    if (this.candleData.length === 0) {
      const initialBar = {
        time: barStart,
        open: tickPrice,
        high: tickPrice,
        low: tickPrice,
        close: tickPrice,
        volume: tickVol || 1.0
      };
      this.candleData.push(initialBar);
      this.candleSeries.setData([{ time: barStart, open: tickPrice, high: tickPrice, low: tickPrice, close: tickPrice }]);
      this.updateLegend(tickPrice, tickPrice, tickPrice, tickPrice);
      return;
    }

    const lastBar = this.candleData[this.candleData.length - 1];
    const lastBarTime = lastBar.time !== undefined ? lastBar.time : lastBar.timestamp;

    if (lastBarTime === barStart) {
      lastBar.high = Math.max(lastBar.high, tickPrice);
      lastBar.low = Math.min(lastBar.low, tickPrice);
      lastBar.close = tickPrice;
      lastBar.volume = (lastBar.volume || 0) + (tickVol || 1.0);
    } else if (barStart > lastBarTime) {
      const newBar = {
        time: barStart,
        open: tickPrice,
        high: tickPrice,
        low: tickPrice,
        close: tickPrice,
        volume: tickVol || 1.0
      };
      this.candleData.push(newBar);
      if (this.candleData.length > 1000) this.candleData.shift();
    }

    const currentBar = this.candleData[this.candleData.length - 1];
    const curTime = currentBar.time !== undefined ? currentBar.time : currentBar.timestamp;
    this.candleSeries.update({
      time: curTime,
      open: currentBar.open,
      high: currentBar.high,
      low: currentBar.low,
      close: currentBar.close
    });
    if (this.volumeSeries) {
      this.volumeSeries.update({
        time: curTime,
        value: currentBar.volume,
        color: currentBar.close >= currentBar.open ? 'rgba(63, 185, 80, 0.15)' : 'rgba(248, 81, 73, 0.15)'
      });
    }
    this.updateLegend(currentBar.open, currentBar.high, currentBar.low, currentBar.close);
  }

  setOverlayVisibility(name, isVisible) {
    if (name === 'ema') {
      this.showEmaRibbon = isVisible;
      if (this.ema9Series) this.ema9Series.applyOptions({ visible: isVisible });
      if (this.ema20Series) this.ema20Series.applyOptions({ visible: isVisible });
      if (this.ema50Series) this.ema50Series.applyOptions({ visible: isVisible });
      if (this.ema200Series) this.ema200Series.applyOptions({ visible: isVisible });
    } else if (name === 'vwap') {
      this.showVwap = isVisible;
      if (this.vwapSeries) this.vwapSeries.applyOptions({ visible: isVisible });
      if (this.vwapUpper1Series) this.vwapUpper1Series.applyOptions({ visible: isVisible });
      if (this.vwapUpper2Series) this.vwapUpper2Series.applyOptions({ visible: isVisible });
      if (this.vwapLower1Series) this.vwapLower1Series.applyOptions({ visible: isVisible });
      if (this.vwapLower2Series) this.vwapLower2Series.applyOptions({ visible: isVisible });
    } else if (name === 'bb') {
      this.showBollinger = isVisible;
      if (this.bbUpperSeries) this.bbUpperSeries.applyOptions({ visible: isVisible });
      if (this.bbMiddleSeries) this.bbMiddleSeries.applyOptions({ visible: isVisible });
      if (this.bbLowerSeries) this.bbLowerSeries.applyOptions({ visible: isVisible });
    } else if (name === 'vwma') {
      this.showVwma = isVisible;
      if (this.vwmaSeries) this.vwmaSeries.applyOptions({ visible: isVisible });
    } else if (name === 'smc') {
      this.showSmc = isVisible;
    }
  }
}

/**
 * Coordinates all 4 simultaneous timeframe charts (M1, M15, H1, H4).
 */
class MultiTimeframeChartGrid {
  constructor() {
    this.charts = {
      'M1': new SingleTimeframeChart('M1', 'chart-m1', 'legend-m1'),
      'M15': new SingleTimeframeChart('M15', 'chart-m15', 'legend-m15'),
      'H1': new SingleTimeframeChart('H1', 'chart-h1', 'legend-h1'),
      'H4': new SingleTimeframeChart('H4', 'chart-h4', 'legend-h4')
    };

    this.overlays = {
      ema: true,
      vwap: true,
      bb: false,
      vwma: false,
      smc: true
    };

    this.bindGlobalOverlayToggles();
  }

  bindGlobalOverlayToggles() {
    const bindBtn = (id, key) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      btn.addEventListener('click', () => {
        this.overlays[key] = !this.overlays[key];
        btn.classList.toggle('active', this.overlays[key]);
        for (const chart of Object.values(this.charts)) {
          chart.setOverlayVisibility(key, this.overlays[key]);
        }
      });
    };

    bindBtn('toggle-ema', 'ema');
    bindBtn('toggle-vwap', 'vwap');
    bindBtn('toggle-bb', 'bb');
    bindBtn('toggle-vwma', 'vwma');
    bindBtn('toggle-smc', 'smc');
  }

  async loadAllHistory() {
    const tfs = ['M1', 'M15', 'H1', 'H4'];
    await Promise.all(tfs.map(async (tf) => {
      try {
        const res = await fetch(`/api/history/${tf}`);
        if (res.ok) {
          const candles = await res.json();
          if (this.charts[tf]) {
            this.charts[tf].setData(candles);
          }
        }
      } catch (e) {
        console.error(`Failed loading history for ${tf}:`, e);
      }
    }));
  }

  updateCandle(tickPrice, tickVol, timestamp) {
    for (const chart of Object.values(this.charts)) {
      chart.updateCandle(tickPrice, tickVol, timestamp);
    }
  }

  renderSetup(setup) {
    // Optional visual markers on charts
  }
}

// Global instance
window.multiChartGrid = null;
window.initDashboardCharts = function() {
  window.multiChartGrid = new MultiTimeframeChartGrid();
  window.multiChartGrid.loadAllHistory();
  return window.multiChartGrid;
};
