// chart.js - Stock Charting Engine using TradingView Lightweight Charts

class TradingChartManager {
    constructor(chartContainerId, indicatorContainerId) {
        this.chartContainer = document.getElementById(chartContainerId);
        this.indicatorContainer = document.getElementById(indicatorContainerId);
        
        this.mainChart = null;
        this.candlestickSeries = null;
        this.avgPriceSeries = null;
        this.volumeSeries = null;
        
        this.indicatorChart = null;
        this.indicatorSeries = {}; // Stores lines for KD, MACD, OBV
        
        this.currentIndicator = 'KD'; // Default indicator
        this.rawKlineData = [];
        this.clickCallback = null;
        
        this._initCharts();
    }

    _initCharts() {
        const chartOptions = {
            layout: {
                background: { color: '#161b25' },
                textColor: '#b2b5be',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
            },
            grid: {
                vertLines: { color: '#2a2e39', style: 1 },
                horzLines: { color: '#2a2e39', style: 1 },
            },
            crosshair: {
                mode: 1, // Magnet crosshair (focuses on closest price bar)
                vertLine: {
                    color: '#708090',
                    width: 1,
                    style: 3,
                    labelBackgroundColor: '#1e222d',
                },
                horzLine: {
                    color: '#708090',
                    width: 1,
                    style: 3,
                    labelBackgroundColor: '#1e222d',
                },
            },
            timeScale: {
                borderColor: '#2a2e39',
                timeVisible: true,
                secondsVisible: false,
            },
        };

        // Create Main K-Line Chart
        this.mainChart = LightweightCharts.createChart(this.chartContainer, {
            ...chartOptions,
            rightPriceScale: {
                borderColor: '#2a2e39',
                autoScale: true,
            }
        });

        // Add Candlestick series (Red rise, Green fall matching Taiwan style)
        this.candlestickSeries = this.mainChart.addCandlestickSeries({
            upColor: '#ff4d4d',
            downColor: '#2ebd85',
            borderUpColor: '#ff4d4d',
            borderDownColor: '#2ebd85',
            wickUpColor: '#ff4d4d',
            wickDownColor: '#2ebd85',
        });

        // Add Average Price Line (均價線) - colored light blue
        this.avgPriceSeries = this.mainChart.addLineSeries({
            color: '#00b0ff',
            lineWidth: 1.5,
            title: '均價線',
            priceScaleId: 'right',
            crosshairMarkerVisible: false, // Prevents crosshair snapping to average price line
        });

        // Add Volume series overlaid on bottom
        this.volumeSeries = this.mainChart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume', // Render on a hidden scale
            crosshairMarkerVisible: false, // Prevents crosshair snapping to volume histogram bars
        });
        
        this.mainChart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.8, bottom: 0 },
        });

        // Create Lower Technical Indicator Chart
        this.indicatorChart = LightweightCharts.createChart(this.indicatorContainer, {
            ...chartOptions,
            height: 120, // fixed height for indicator pane
            rightPriceScale: {
                borderColor: '#2a2e39',
                autoScale: true,
            }
        });

        // Link timescales for synchronous scrolling/zooming
        let isSyncing = false;
        this.mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (isSyncing || !range) return;
            isSyncing = true;
            try {
                this.indicatorChart.timeScale().setVisibleRange(range);
            } catch (e) {
                // Ignore range sync errors before both charts have loaded data
            }
            isSyncing = false;
        });

        this.indicatorChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (isSyncing || !range) return;
            isSyncing = true;
            try {
                this.mainChart.timeScale().setVisibleRange(range);
            } catch (e) {
                // Ignore range sync errors before both charts have loaded data
            }
            isSyncing = false;
        });

        // Click Subscription to capture crosshair price for day trading orders
        this.mainChart.subscribeClick((param) => {
            if (!param.point || !param.time || !this.clickCallback) return;
            
            // Try to get the close price of the clicked candlestick first
            const candleData = param.seriesData.get(this.candlestickSeries);
            if (candleData && candleData.close !== undefined) {
                this.clickCallback(candleData.close);
            } else {
                // Fallback to vertical coordinate price
                const price = this.candlestickSeries.coordinateToPrice(param.point.y);
                if (price) {
                    this.clickCallback(roundToTick(price));
                }
            }
        });

        // Listen for window resize
        window.addEventListener('resize', () => {
            this.mainChart.resize(this.chartContainer.clientWidth, this.chartContainer.clientHeight);
            this.indicatorChart.resize(this.indicatorContainer.clientWidth, 120);
        });
    }

    onChartClick(callback) {
        this.clickCallback = callback;
    }

    setIndicator(indicatorName) {
        this.currentIndicator = indicatorName;
        this.renderIndicators();
    }

    loadData(klineData) {
        this.rawKlineData = klineData;
        if (!klineData || klineData.length === 0) return;

        // Dynamically adjust price format options based on active stock's price range
        const basePrice = klineData[0].close;
        const tickSize = getTickSizeForPrice(basePrice);
        
        this.candlestickSeries.applyOptions({
            priceFormat: {
                type: 'price',
                precision: 2,
                minMove: tickSize
            }
        });

        this.avgPriceSeries.applyOptions({
            priceFormat: {
                type: 'price',
                precision: 2,
                minMove: tickSize
            }
        });

        // Set candlesticks
        this.candlestickSeries.setData(klineData);

        // Render volumes
        const volumeData = klineData.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(255,77,77,0.3)' : 'rgba(46,189,133,0.3)'
        }));
        this.volumeSeries.setData(volumeData);

        // Render average price line (均價線)
        const avgPriceData = this._calculateAveragePriceLine(klineData);
        this.avgPriceSeries.setData(avgPriceData);

        // Render bottom technical indicator panel
        this.renderIndicators();
        
        // Auto-fit contents
        this.mainChart.timeScale().fitContent();
    }

    updateTick(tick) {
        if (this.rawKlineData.length === 0) return;

        // Obtain latest K-line bar
        const lastCandle = { ...this.rawKlineData[this.rawKlineData.length - 1] };
        const tickTime = tick.time;
        const tickPrice = tick.price;
        const tickVol = tick.volume;

        // If it's a new timestamp (based on interval), push a new bar. Otherwise, update the current bar.
        // For simplicity in simulation, we update the last K-line bar's close and volume
        lastCandle.close = tickPrice;
        lastCandle.high = Math.max(lastCandle.high, tickPrice);
        lastCandle.low = Math.min(lastCandle.low, tickPrice);
        lastCandle.volume += tickVol;

        // Replace last element in memory
        this.rawKlineData[this.rawKlineData.length - 1] = lastCandle;

        // Push update to Lightweight charts
        this.candlestickSeries.update(lastCandle);
        this.volumeSeries.update({
            time: lastCandle.time,
            value: lastCandle.volume,
            color: lastCandle.close >= lastCandle.open ? 'rgba(255,77,77,0.3)' : 'rgba(46,189,133,0.3)'
        });

        // Re-calculate average price and indicators for updated dataset
        const avgPriceData = this._calculateAveragePriceLine(this.rawKlineData);
        this.avgPriceSeries.setData(avgPriceData);
        this.renderIndicators();
    }

    renderIndicators() {
        // Clear all previous indicator lines
        for (const key in this.indicatorSeries) {
            this.indicatorChart.removeSeries(this.indicatorSeries[key]);
        }
        this.indicatorSeries = {};

        if (this.currentIndicator === 'KD') {
            const { kData, dData } = this._calculateKD(this.rawKlineData);
            
            this.indicatorSeries.k = this.indicatorChart.addLineSeries({
                color: '#ffaa00',
                lineWidth: 1,
                title: 'K'
            });
            this.indicatorSeries.d = this.indicatorChart.addLineSeries({
                color: '#00b0ff',
                lineWidth: 1,
                title: 'D'
            });
            
            this.indicatorSeries.k.setData(kData);
            this.indicatorSeries.d.setData(dData);

        } else if (this.currentIndicator === 'MACD') {
            const { difData, demData, macdBarData } = this._calculateMACD(this.rawKlineData);
            
            this.indicatorSeries.dif = this.indicatorChart.addLineSeries({
                color: '#ff4d4d',
                lineWidth: 1.2,
                title: 'DIF'
            });
            this.indicatorSeries.dem = this.indicatorChart.addLineSeries({
                color: '#00b0ff',
                lineWidth: 1.2,
                title: 'DEM'
            });
            this.indicatorSeries.bar = this.indicatorChart.addHistogramSeries({
                title: 'MACD',
                priceFormat: { type: 'volume' }
            });

            this.indicatorSeries.dif.setData(difData);
            this.indicatorSeries.dem.setData(demData);
            this.indicatorSeries.bar.setData(macdBarData);

        } else if (this.currentIndicator === 'OBV') {
            const obvData = this._calculateOBV(this.rawKlineData);
            
            this.indicatorSeries.obv = this.indicatorChart.addLineSeries({
                color: '#2ebd85',
                lineWidth: 1.5,
                title: 'OBV'
            });
            this.indicatorSeries.obv.setData(obvData);
        }
    }

    // ==========================================
    // MATHEMATICAL TECHNICAL INDICATOR CALCULATORS
    // ==========================================

    _calculateAveragePriceLine(candles) {
        // Average Price Line (均價線) = Cumulative (Price * Volume) / Cumulative Volume
        let cumulativeVal = 0;
        let cumulativeVol = 0;
        
        return candles.map(c => {
            cumulativeVal += (c.close * c.volume);
            cumulativeVol += c.volume;
            const avgPrice = cumulativeVol > 0 ? (cumulativeVal / cumulativeVol) : c.close;
            return {
                time: c.time,
                value: roundToTick(avgPrice)
            };
        });
    }

    _calculateKD(candles, period = 9, kFactor = 3, dFactor = 3) {
        const kData = [];
        const dData = [];
        
        if (candles.length < period) return { kData, dData };

        let kVal = 50.0;
        let dVal = 50.0;

        for (let i = 0; i < candles.length; i++) {
            if (i < period - 1) {
                // Initialize default values for early bars
                kData.push({ time: candles[i].time, value: 50.0 });
                dData.push({ time: candles[i].time, value: 50.0 });
                continue;
            }

            // Get high/low over lookback period
            let lowestLow = Infinity;
            let highestHigh = -Infinity;
            for (let j = i - period + 1; j <= i; j++) {
                if (candles[j].low < lowestLow) lowestLow = candles[j].low;
                if (candles[j].high > highestHigh) highestHigh = candles[j].high;
            }

            const currentClose = candles[i].close;
            let rsv = 50.0;
            if (highestHigh - lowestLow > 0) {
                rsv = ((currentClose - lowestLow) / (highestHigh - lowestLow)) * 100;
            }

            // KD Recursion: K = (2/3)*K_prev + (1/3)*RSV, D = (2/3)*D_prev + (1/3)*K
            kVal = (2 / 3) * kVal + (1 / 3) * rsv;
            dVal = (2 / 3) * dVal + (1 / 3) * kVal;

            kData.push({ time: candles[i].time, value: parseFloat(kVal.toFixed(2)) });
            dData.push({ time: candles[i].time, value: parseFloat(dVal.toFixed(2)) });
        }

        return { kData, dData };
    }

    _calculateMACD(candles, fast = 12, slow = 26, signal = 9) {
        const difData = [];
        const demData = [];
        const macdBarData = [];

        if (candles.length < slow) return { difData, demData, macdBarData };

        // Helper to calculate EMAs
        const emaFast = this._calculateEMA(candles, fast);
        const emaSlow = this._calculateEMA(candles, slow);

        // DIF = EMA(12) - EMA(26)
        const difValues = [];
        for (let i = 0; i < candles.length; i++) {
            const dif = emaFast[i] - emaSlow[i];
            difValues.push({ time: candles[i].time, value: dif });
            difData.push({ time: candles[i].time, value: parseFloat(dif.toFixed(2)) });
        }

        // DEM = EMA(9) of DIF
        const demValues = this._calculateEMA(difValues, signal);
        for (let i = 0; i < candles.length; i++) {
            const dem = demValues[i];
            demData.push({ time: candles[i].time, value: parseFloat(dem.toFixed(2)) });
            
            // MACD Bar (Oscillator) = DIF - DEM
            const barVal = difValues[i].value - dem;
            macdBarData.push({
                time: candles[i].time,
                value: parseFloat(barVal.toFixed(2)),
                color: barVal >= 0 ? 'rgba(255, 77, 77, 0.4)' : 'rgba(46, 189, 133, 0.4)' // Red up, green down
            });
        }

        return { difData, demData, macdBarData };
    }

    _calculateEMA(candles, period) {
        const ema = [];
        const k = 2 / (period + 1);
        let emaPrev = candles[0].close || candles[0].value || 0; // handle raw K-line or custom objects
        ema.push(emaPrev);

        for (let i = 1; i < candles.length; i++) {
            const price = candles[i].close !== undefined ? candles[i].close : candles[i].value;
            const emaCurrent = price * k + emaPrev * (1 - k);
            ema.push(emaCurrent);
            emaPrev = emaCurrent;
        }
        return ema;
    }

    _calculateOBV(candles) {
        const obvData = [];
        if (candles.length === 0) return obvData;

        let currentObv = 0;
        obvData.push({ time: candles[0].time, value: 0 });

        for (let i = 1; i < candles.length; i++) {
            const prevClose = candles[i-1].close;
            const currClose = candles[i].close;
            const volume = candles[i].volume;

            if (currClose > prevClose) {
                currentObv += volume;
            } else if (currClose < prevClose) {
                currentObv -= volume;
            }
            
            obvData.push({ time: candles[i].time, value: currentObv });
        }
        return obvData;
    }
}

function getTickSizeForPrice(price) {
    if (price < 10) return 0.01;
    if (price < 50) return 0.05;
    if (price < 100) return 0.1;
    if (price < 500) return 0.5;
    if (price < 1000) return 1.0;
    return 5.0;
}

// Tick-size rounding helper
function roundToTick(price) {
    const tickSize = getTickSizeForPrice(price);
    return Math.round(price / tickSize) * tickSize;
}

function getUPlotSplits(scaleMin, scaleMax, tickSize) {
    if (scaleMin === undefined || scaleMin === null || isNaN(scaleMin) ||
        scaleMax === undefined || scaleMax === null || isNaN(scaleMax)) {
        return [];
    }

    const range = scaleMax - scaleMin;
    if (range <= 0) return [scaleMin];
    
    let step = tickSize || 0.01;
    const targetTicks = 6;
    let rawStep = range / targetTicks;
    
    if (rawStep < step) {
        step = step;
    } else {
        let multiplier = Math.ceil(rawStep / step);
        step = multiplier * step;
    }
    
    const splits = [];
    let firstTick = Math.ceil(scaleMin / step) * step;
    for (let val = firstTick; val <= scaleMax; val += step) {
        splits.push(parseFloat(val.toFixed(4)));
    }
    
    if (splits.length < 2) {
        return [scaleMin, scaleMax];
    }
    return splits;
}

class UPlotChartManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.uplot = null;
        this.data = [[], []]; // [timestamps, prices]
        this.clickCallback = null;
        
        // Listen to resize events and adjust uPlot size dynamically
        window.addEventListener('resize', () => {
            if (this.uplot && this.container.style.display !== "none") {
                const w = this.container.clientWidth;
                const h = this.container.clientHeight;
                if (w > 0 && h > 0) {
                    this.uplot.setSize({ width: w, height: h });
                }
            }
        });
    }

    onChartClick(callback) {
        this.clickCallback = callback;
    }

    _parseTimeString(timeStr) {
        if (!timeStr) return Math.floor(Date.now() / 1000);
        const parts = timeStr.split(':');
        if (parts.length < 3) return Math.floor(Date.now() / 1000);
        
        const now = new Date();
        now.setHours(parseInt(parts[0], 10));
        now.setMinutes(parseInt(parts[1], 10));
        now.setSeconds(parseInt(parts[2], 10));
        now.setMilliseconds(0);
        return Math.floor(now.getTime() / 1000);
    }

    initChart(initialTicks) {
        // Destroy existing uPlot instance to avoid duplicate canvas overlays
        if (this.uplot) {
            this.uplot.destroy();
            this.uplot = null;
        }

        this.container.innerHTML = "";

        // Format data: uPlot expects [[timestamps], [prices], [volumes]]
        if (initialTicks && initialTicks.length > 0) {
            this.data = [
                initialTicks.map(t => typeof t.time === 'number' ? t.time : this._parseTimeString(t.time)),
                initialTicks.map(t => t.price),
                initialTicks.map(t => t.volume || 0)
            ];
        } else {
            const nowSec = Math.floor(Date.now() / 1000);
            this.data = [[nowSec], [0.0], [0]];
        }

        const parentWidth = this.container.parentElement ? this.container.parentElement.clientWidth : 0;
        const width = parentWidth || this.container.clientWidth || 800;
        const height = this.container.clientHeight || 350;

        let basePrice = 100.0;
        if (initialTicks && initialTicks.length > 0) {
            basePrice = initialTicks[0].price || basePrice;
        }
        const tickSize = getTickSizeForPrice(basePrice);
        this.tickSize = tickSize;

        console.log(`[uPlot Debug] initChart: ticksCount=${initialTicks ? initialTicks.length : 0}, parentWidth=${parentWidth}, containerWidth=${this.container.clientWidth}, finalWidth=${width}, height=${height}, tickSize=${tickSize}`);

        // Custom paths builder for drawing volume bar charts
        function drawUPlotVolumeBars(self, seriesIdx, idx0, idx1) {
            const fillPath = new Path2D();
            
            const xData = self.data[0];
            const yData = self.data[seriesIdx];
            const series = self.series[seriesIdx];
            
            // Volume starts at the absolute bottom of the plotting grid area
            const zeroPos = self.bbox.top + self.bbox.height;
            
            // Dynamically calculate bar width
            const pointsCount = xData.length;
            const chartWidth = self.bbox.width;
            const barWidth = Math.max(1, Math.floor(chartWidth / (pointsCount || 1)) - 1);
            
            for (let i = idx0; i <= idx1; i++) {
                const val = yData[i];
                if (val === null || val === undefined) continue;
                
                const xPos = self.valToPos(xData[i], "x");
                const yPos = self.valToPos(val, series.scale);
                
                const x = Math.round(xPos - barWidth / 2);
                const y = Math.round(yPos);
                const w = Math.round(barWidth);
                const h = Math.round(zeroPos - yPos);
                
                fillPath.rect(x, y, w, h);
            }
            
            return {
                stroke: null,
                fill: fillPath
            };
        }

        const opts = {
            width: width,
            height: height,
            title: "",
            id: "uplot-canvas-core",
            class: "uplot-chart-custom",
            padding: [12, 60, 12, 12],
            scales: {
                x: {
                    time: true,
                },
                y: {
                    auto: true,
                },
                vol: {
                    auto: true,
                    range: (self, min, max) => [0, max * 3] // scale volume to occupy the bottom 33% of the canvas
                }
            },
            series: [
                {
                    // X-axis Time formatting
                    value: (self, rawValue) => {
                        if (!rawValue) return "";
                        const d = new Date(rawValue * 1000);
                        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
                    }
                },
                {
                    // Y-axis Price formatting (light-blue stroke area chart)
                    scale: 'y',
                    stroke: "#00b0ff",
                    width: 2,
                    fill: "rgba(0, 176, 255, 0.05)",
                    label: "價格",
                    value: (self, rawValue) => "NT$ " + (rawValue ? rawValue.toFixed(2) : "0.00"),
                },
                {
                    // Y2-axis Volume formatting (bottom bar chart)
                    scale: 'vol',
                    fill: "rgba(255, 255, 255, 0.35)", // more obvious translucent volume bars
                    label: "成交量",
                    paths: drawUPlotVolumeBars,
                    value: (self, rawValue) => rawValue ? rawValue.toLocaleString() + " 股" : "0 股",
                }
            ],
            axes: [
                {
                    stroke: "#b2b5be",
                    grid: {
                        stroke: "#2a2e39",
                        width: 1,
                    },
                    size: 40,
                },
                {
                    show: true,
                    side: 1,
                    scale: 'y',
                    stroke: "#b2b5be",
                    grid: {
                        show: true,
                        stroke: "#2a2e39",
                        width: 1,
                    },
                    size: 60,
                    splits: (self, axisIdx, scaleMin, scaleMax) => {
                        return getUPlotSplits(scaleMin, scaleMax, tickSize);
                    },
                    values: (self, ticks) => ticks.map(v => (v !== undefined && v !== null && !isNaN(v)) ? Number(v).toFixed(2) : "")
                }
            ],
            cursor: {
                show: true,
                points: {
                    show: true,
                    size: 6,
                    stroke: "#fff",
                    fill: "#00b0ff"
                },
                drag: {
                    setScale: false
                },
                move: (self, mouseLeft, mouseTop) => {
                    const idx = self.posToIdx(mouseLeft);
                    if (idx !== undefined && idx !== null && idx >= 0) {
                        const price = self.data[1][idx];
                        if (price !== undefined && price !== null) {
                            const snappedTop = self.valToPos(price, "y");
                            return [mouseLeft, snappedTop];
                        }
                    }
                    return [mouseLeft, mouseTop];
                }
            }
        };

        this.uplot = new uPlot(opts, this.data, this.container);

        // Setup mouse click coordinate handler on uPlot interaction area
        const over = this.uplot.root.querySelector(".u-over");
        if (over) {
            let dragStart = null;
            over.addEventListener("mousedown", (e) => {
                dragStart = { x: e.clientX, y: e.clientY };
            });

            over.addEventListener("mouseup", (e) => {
                if (!dragStart) return;
                const dist = Math.hypot(e.clientX - dragStart.x, e.clientY - dragStart.y);
                dragStart = null;
                if (dist > 5) return; // Ignore drag operations

                if (this.uplot && this.clickCallback) {
                    const rect = over.getBoundingClientRect();
                    const left = e.clientX - rect.left;
                    const idx = this.uplot.posToIdx(left);
                    if (idx !== undefined && idx !== null && idx >= 0 && idx < this.data[1].length) {
                        const price = this.data[1][idx];
                        if (price && price > 0) {
                            this.clickCallback(price);
                        }
                    }
                }
            });
        }
    }

    addTick(tickTime, tickPrice, tickVolume = 0) {
        if (!this.uplot) return;

        let timestamp = (typeof tickTime === 'number') ? tickTime : this._parseTimeString(tickTime);
        const xData = this.data[0];
        const yData = this.data[1];
        const volData = this.data[2] || [];

        // uPlot requires strictly increasing x values
        if (xData.length > 0 && timestamp <= xData[xData.length - 1]) {
            timestamp = xData[xData.length - 1] + 1;
        }

        xData.push(timestamp);
        yData.push(tickPrice);
        volData.push(tickVolume);

        // Limit tick history size to prevent canvas latency
        if (xData.length > 300) {
            xData.shift();
            yData.shift();
            volData.shift();
        }

        this.data = [xData, yData, volData];
        this.uplot.setData(this.data);
    }
}

