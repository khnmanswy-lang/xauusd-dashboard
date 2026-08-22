/**
 * Clean TradingView Lightweight Charts Manager for XAUUSD Terminal.
 * Displays clean Candlesticks, Volume Sub-pane, EMA 50, EMA 200, and dynamic OHLC legend.
 * All complex quantitative indicators (VWAP, RSI, Structure, ADR) are cleanly organized in the side matrix.
 */

class DashboardChart {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.currentTimeframe = 'M5';
    this.chart = null;
    this.candleSeries = null;
    this.volumeSeries = null;
    this.ema50Series = null;
    this.ema200Series = null;

    // Visibility toggles (clean: only EMA50 and EMA200 on chart)
    this.showEma50 = true;
    this.showEma200 = true;

    // Cache of current data
    this.candleData = [];
    this.volumeData = [];
    this.ema50Data = [];
    this.ema200Data = [];

    // Legend element
    this.legendEl = null;

    this.init();
  }

  init() {
    if (!this.container) return;

    this.createLegendElement();

    if (typeof LightweightCharts !== 'undefined') {
      this.initLightweightChart();
    } else {
      console.warn("LightweightCharts library not loaded; falling back to canvas.");
      this.initFallbackCanvas();
    }

    window.addEventListener('resize', () => {
      if (this.chart) {
        this.chart.applyOptions({
          width: this.container.clientWidth,
          height: this.container.clientHeight
        });
      }
    });
  }

  createLegendElement() {
    this.legendEl = document.createElement('div');
    this.legendEl.className = 'chart-ohlc-legend num';
    this.legendEl.innerHTML = `
      <span class="legend-symbol" style="color: var(--gold-accent); font-weight: 700; margin-right: 6px;">XAUUSD</span>
      <span class="legend-tf" style="color: var(--text-secondary); margin-right: 6px;">M5</span>
      <span id="legend-time" style="color: var(--text-muted); margin-right: 10px;">--:--</span>
      <span style="color: var(--text-secondary)">O:</span> <span id="legend-o" style="color: var(--text-primary)">--</span>
      <span style="color: var(--text-secondary)">H:</span> <span id="legend-h" style="color: var(--text-primary)">--</span>
      <span style="color: var(--text-secondary)">L:</span> <span id="legend-l" style="color: var(--text-primary)">--</span>
      <span style="color: var(--text-secondary)">C:</span> <span id="legend-c" style="color: var(--text-primary)">--</span>
      <span style="color: var(--text-muted); margin-left: 8px;">|</span>
      <span style="color: #f0b90b; margin-left: 8px;">EMA 50:</span> <span id="legend-ema50" style="color: #f0b90b; font-weight: 600;">--</span>
      <span style="color: #38bdf8; margin-left: 8px;">EMA 200:</span> <span id="legend-ema200" style="color: #38bdf8; font-weight: 600;">--</span>
    `;
    this.container.style.position = 'relative';
    this.container.appendChild(this.legendEl);
  }

  updateLegend(candle, e50Val, e200Val) {
    if (!candle) return;
    const elTime = document.getElementById('legend-time');
    const elO = document.getElementById('legend-o');
    const elH = document.getElementById('legend-h');
    const elL = document.getElementById('legend-l');
    const elC = document.getElementById('legend-c');
    const elE50 = document.getElementById('legend-ema50');
    const elE200 = document.getElementById('legend-ema200');

    if (elTime && candle.time) {
      const d = new Date(candle.time * 1000);
      elTime.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    }
    if (elO) elO.textContent = candle.open ? candle.open.toFixed(2) : '--';
    if (elH) elH.textContent = candle.high ? candle.high.toFixed(2) : '--';
    if (elL) elL.textContent = candle.low ? candle.low.toFixed(2) : '--';
    if (elC) {
      elC.textContent = candle.close ? candle.close.toFixed(2) : '--';
      elC.style.color = candle.close >= candle.open ? '#089981' : '#f23645';
    }
    if (elE50) elE50.textContent = e50Val ? e50Val.toFixed(2) : '--';
    if (elE200) elE200.textContent = e200Val ? e200Val.toFixed(2) : '--';
  }

  initLightweightChart() {
    this.chart = LightweightCharts.createChart(this.container, {
      width: this.container.clientWidth || 600,
      height: this.container.clientHeight || 450,
      layout: {
        background: { color: '#0a0e17' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: "'JetBrains Mono', 'Roboto Mono', monospace"
      },
      localization: {
        timeFormatter: (timestamp) => {
          const d = new Date(timestamp * 1000);
          return d.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
          });
        },
        dateFormatter: (timestamp) => {
          const d = new Date(timestamp * 1000);
          return d.toLocaleDateString();
        }
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.45)', style: 1 },
        horzLines: { color: 'rgba(30, 41, 59, 0.45)', style: 1 }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: '#f0b90b',
          width: 1,
          style: LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#161f2e'
        },
        horzLine: {
          color: '#f0b90b',
          width: 1,
          style: LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#161f2e'
        }
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 14,
        barSpacing: 4.5,
        minBarSpacing: 1.5,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          const hours = String(d.getHours()).padStart(2, '0');
          const mins = String(d.getMinutes()).padStart(2, '0');
          return `${hours}:${mins}`;
        }
      },
      rightPriceScale: {
        borderColor: '#1e293b',
        autoScale: true,
        scaleMargins: {
          top: 0.12,
          bottom: 0.20
        }
      }
    });

    // 1. Volume Sub-Pane (bottom)
    this.volumeSeries = this.chart.addHistogramSeries({
      color: 'rgba(0, 192, 118, 0.30)',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: {
        top: 0.84,
        bottom: 0
      }
    });

    // 2. Candlestick Series (TradingView Standard Colors)
    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: '#089981',
      downColor: '#f23645',
      borderUpColor: '#089981',
      borderDownColor: '#f23645',
      wickUpColor: '#089981',
      wickDownColor: '#f23645'
    });

    // 3. EMA 50 (Subtle Amber 1px Line)
    this.ema50Series = this.chart.addLineSeries({
      color: 'rgba(234, 179, 8, 0.65)',
      lineWidth: 1,
      title: 'EMA 50',
      priceLineVisible: false,
      crosshairMarkerVisible: false
    });

    // 4. EMA 200 (Subtle Cool Slate/Blue 1px Line)
    this.ema200Series = this.chart.addLineSeries({
      color: 'rgba(56, 189, 248, 0.55)',
      lineWidth: 1,
      title: 'EMA 200',
      priceLineVisible: false,
      crosshairMarkerVisible: false
    });

    // Crosshair inspection
    this.chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData) {
        if (this.candleData.length > 0) {
          const lastCandle = this.candleData[this.candleData.length - 1];
          const lastE50 = this.ema50Data.length > 0 ? this.ema50Data[this.ema50Data.length - 1].value : null;
          const lastE200 = this.ema200Data.length > 0 ? this.ema200Data[this.ema200Data.length - 1].value : null;
          this.updateLegend(lastCandle, lastE50, lastE200);
        }
        return;
      }

      const candle = param.seriesData.get(this.candleSeries);
      const e50 = param.seriesData.get(this.ema50Series);
      const e200 = param.seriesData.get(this.ema200Series);
      if (candle) {
        this.updateLegend(candle, e50 ? e50.value : null, e200 ? e200.value : null);
      }
    });

    // Load initial timeframe history
    this.loadHistory(this.currentTimeframe);
  }

  async loadHistory(timeframe) {
    this.currentTimeframe = timeframe;
    
    const tfEl = this.legendEl ? this.legendEl.querySelector('.legend-tf') : null;
    if (tfEl) tfEl.textContent = timeframe;

    try {
      const resp = await fetch(`/api/history/${timeframe}`);
      if (!resp.ok) throw new Error("History fetch error");
      const candles = await resp.json();
      
      if (candles && candles.length > 0) {
        this.candleData = candles.map(c => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close
        }));

        this.volumeData = candles.map(c => ({
          time: c.time,
          value: c.volume || 50,
          color: c.close >= c.open ? 'rgba(8, 153, 129, 0.30)' : 'rgba(242, 54, 69, 0.30)'
        }));

        // Calculate continuous EMAs for the series
        this.calculateEmASeries();

        if (this.candleSeries && this.volumeSeries) {
          this.candleSeries.setData(this.candleData);
          this.volumeSeries.setData(this.volumeData);
          this.renderEmaSeries();
          
          // Apply 2x zoom out and align to live edge
          this.chart.timeScale().applyOptions({
            barSpacing: 4.5,
            rightOffset: 14
          });
          this.chart.timeScale().scrollToRealTime();

          const lastCandle = this.candleData[this.candleData.length - 1];
          const lastE50 = this.ema50Data.length > 0 ? this.ema50Data[this.ema50Data.length - 1].value : null;
          const lastE200 = this.ema200Data.length > 0 ? this.ema200Data[this.ema200Data.length - 1].value : null;
          this.updateLegend(lastCandle, lastE50, lastE200);
        }
      }
    } catch (e) {
      console.warn("Could not load candle history:", e);
    }
  }

  calculateEmASeries() {
    this.ema50Data = [];
    this.ema200Data = [];
    if (this.candleData.length === 0) return;

    const closes = this.candleData.map(c => c.close);
    const k50 = 2.0 / (50 + 1);
    const k200 = 2.0 / (200 + 1);

    let prevE50 = closes[0];
    let prevE200 = closes[0];

    for (let i = 0; i < this.candleData.length; i++) {
      const c = this.candleData[i];
      const close = c.close;

      prevE50 = (close * k50) + (prevE50 * (1.0 - k50));
      prevE200 = (close * k200) + (prevE200 * (1.0 - k200));

      this.ema50Data.push({ time: c.time, value: roundNum(prevE50) });
      this.ema200Data.push({ time: c.time, value: roundNum(prevE200) });
    }
  }

  renderEmaSeries() {
    if (this.ema50Series) {
      this.ema50Series.setData(this.showEma50 ? this.ema50Data : []);
    }
    if (this.ema200Series) {
      this.ema200Series.setData(this.showEma200 ? this.ema200Data : []);
    }
  }

  updateCandle(liveTick) {
    if (!liveTick || !this.candleSeries || this.candleData.length === 0) return;

    const price = liveTick.price;
    const nowTs = liveTick.timestamp || Math.floor(Date.now() / 1000);
    const last = this.candleData[this.candleData.length - 1];

    const intervalSecs = this.currentTimeframe === 'H1' ? 3600 : (this.currentTimeframe === 'M15' ? 900 : (this.currentTimeframe === 'M1' ? 60 : 300));
    const bucketTs = nowTs - (nowTs % intervalSecs);

    if (last.time < bucketTs) {
      // New bar
      const newCandle = {
        time: bucketTs,
        open: price,
        high: price,
        low: price,
        close: price
      };
      this.candleData.push(newCandle);
      this.candleSeries.update(newCandle);

      const newVol = {
        time: bucketTs,
        value: 1.0,
        color: 'rgba(8, 153, 129, 0.30)'
      };
      this.volumeData.push(newVol);
      this.volumeSeries.update(newVol);

      // Incremental EMA calculation
      const k50 = 2.0 / (50 + 1);
      const k200 = 2.0 / (200 + 1);
      const lastE50 = this.ema50Data.length > 0 ? this.ema50Data[this.ema50Data.length - 1].value : price;
      const lastE200 = this.ema200Data.length > 0 ? this.ema200Data[this.ema200Data.length - 1].value : price;

      const newE50 = roundNum((price * k50) + (lastE50 * (1.0 - k50)));
      const newE200 = roundNum((price * k200) + (lastE200 * (1.0 - k200)));

      this.ema50Data.push({ time: bucketTs, value: newE50 });
      this.ema200Data.push({ time: bucketTs, value: newE200 });

      if (this.showEma50 && this.ema50Series) this.ema50Series.update({ time: bucketTs, value: newE50 });
      if (this.showEma200 && this.ema200Series) this.ema200Series.update({ time: bucketTs, value: newE200 });

      this.updateLegend(newCandle, newE50, newE200);
    } else {
      // Update active bar
      last.high = Math.max(last.high, price);
      last.low = Math.min(last.low, price);
      last.close = price;
      this.candleSeries.update(last);

      const lastVol = this.volumeData[this.volumeData.length - 1];
      if (lastVol) {
        lastVol.value = (lastVol.value || 1.0) + 0.5;
        lastVol.color = last.close >= last.open ? 'rgba(8, 153, 129, 0.30)' : 'rgba(242, 54, 69, 0.30)';
        this.volumeSeries.update(lastVol);
      }

      // Update current bar's EMA
      const k50 = 2.0 / (50 + 1);
      const k200 = 2.0 / (200 + 1);
      const prevE50 = this.ema50Data.length > 1 ? this.ema50Data[this.ema50Data.length - 2].value : price;
      const prevE200 = this.ema200Data.length > 1 ? this.ema200Data[this.ema200Data.length - 2].value : price;

      const currE50 = roundNum((price * k50) + (prevE50 * (1.0 - k50)));
      const currE200 = roundNum((price * k200) + (prevE200 * (1.0 - k200)));

      if (this.ema50Data.length > 0) this.ema50Data[this.ema50Data.length - 1].value = currE50;
      if (this.ema200Data.length > 0) this.ema200Data[this.ema200Data.length - 1].value = currE200;

      if (this.showEma50 && this.ema50Series) this.ema50Series.update({ time: last.time, value: currE50 });
      if (this.showEma200 && this.ema200Series) this.ema200Series.update({ time: last.time, value: currE200 });

      this.updateLegend(last, currE50, currE200);
    }
  }

  toggleEma50(enabled) {
    this.showEma50 = enabled;
    this.renderEmaSeries();
  }

  toggleEma200(enabled) {
    this.showEma200 = enabled;
    this.renderEmaSeries();
  }

  initFallbackCanvas() {
    const canvas = document.createElement('canvas');
    canvas.width = this.container.clientWidth || 600;
    canvas.height = this.container.clientHeight || 450;
    this.container.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#0a0e17';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#f0b90b';
    ctx.font = '14px monospace';
    ctx.fillText('⚡ XAUUSD Interactive Terminal Stream Online', 20, 40);
  }
}

function roundNum(val, dec = 2) {
  return parseFloat(Number(val).toFixed(dec));
}
