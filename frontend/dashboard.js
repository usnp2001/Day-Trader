// dashboard.js - Charting dashboard state and interaction controller

const state = {
    selectedSymbol: "2330.TW",  // Default to TSMC
    selectedName: "台積電",
    selectedInterval: "1d",     // Default interval
    selectedPrice: 0.0,
    screenerStocks: [],         // Cached stock metadata for name matching
    positions: [],
    orders: [],
    accountSummary: {
        cash: 10000000.0,
        market_value: 0.0,
        total_assets: 10000000.0,
        total_pnl: 0.0
    },
    ws: null,
    chartManager: null
};

const API_BASE_URL = `${window.location.protocol}//${window.location.host}`;
const WS_BASE_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Parse URL Parameter (e.g. ?symbol=2317.TW)
    const urlParams = new URLSearchParams(window.location.search);
    const sym = urlParams.get('symbol');
    if (sym) {
        state.selectedSymbol = sym.toUpperCase();
    }

    // 2. Initialize Charting Engine
    state.chartManager = new TradingChartManager("tradingview-chart", "indicator-chart");
    
    // Bind click coordinate handler from chart to open order modal
    state.chartManager.onChartClick((price) => {
        openTradingModal("BUY", price);
    });

    // 3. Load Data
    initApp();

    // 4. Bind UI Interactivity
    bindUIEvents();
});

// ==========================================
// AUTHENTICATION HEADERS & UTILITIES
// ==========================================

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
    };
}

window.handleLogout = function() {
    localStorage.clear();
    window.location.href = '/login.html';
};

function initializeHeader() {
    const token = localStorage.getItem('token');
    const username = localStorage.getItem('username');
    const role = localStorage.getItem('role');

    if (!token) {
        handleLogout();
        return;
    }

    // Populate user profile info in header
    document.getElementById('header-username').textContent = username;
    
    if (role === 'admin') {
        const roleBadge = document.getElementById('header-user-role');
        if (roleBadge) {
            roleBadge.textContent = 'admin';
            roleBadge.style.display = 'inline-block';
        }
        const adminLink = document.getElementById('link-admin-panel');
        if (adminLink) {
            adminLink.style.display = 'inline-block';
        }
    }

    // Bind cash adjustment pencil trigger
    const btnEditCash = document.getElementById('btn-edit-cash');
    if (btnEditCash) {
        btnEditCash.addEventListener('click', handleAdjustCash);
    }
}

async function handleAdjustCash() {
    const currentCashVal = state.accountSummary.cash;
    const newCashStr = prompt('請輸入新的可用現金金額 (TWD):', currentCashVal);
    if (newCashStr === null) return;
    const newCash = parseFloat(newCashStr);
    if (isNaN(newCash) || newCash < 0) {
        alert('請輸入有效的正數金額！');
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/account/adjust_cash`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ cash: newCash })
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            state.accountSummary.cash = newCash;
            renderAccountSummary();
            recalculateHeaderAssets();
        } else {
            alert(data.detail || '金額修改失敗');
        }
    } catch (err) {
        alert('連線伺服器失敗，請確認網路狀態。');
    }
}

// ==========================================
// INITIAL SETUP
// ==========================================

async function initApp() {
    initializeHeader();
    await fetchScreenerList(); // Load all stocks cache first for name mapping
    await fetchInventory();
    
    // Lookup selected stock name
    const matched = state.screenerStocks.find(s => s.symbol === state.selectedSymbol);
    if (matched) {
        state.selectedName = matched.name;
    } else {
        state.selectedName = state.selectedSymbol;
    }
    
    updateActiveStockUI();
    await fetchKlineHistory();
    connectWebSocket();
    initSearchAutocomplete();
}

async function fetchScreenerList() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/screener`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const json = await res.json();
        if (json.status === "success") {
            state.screenerStocks = json.data;
        }
    } catch (e) {
        console.error("Error fetching stocks list:", e);
    }
}

async function fetchInventory() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/inventory`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const json = await res.json();
        if (json.status === "success") {
            state.positions = json.positions;
            state.accountSummary = json.summary;
            renderAccountSummary();
            renderPortfolio();
            await fetchOrders();
        }
    } catch (e) {
        console.error("Error fetching inventory:", e);
    }
}

async function fetchOrders() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/orders`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const json = await res.json();
        if (json.status === "success") {
            state.orders = json.orders;
            renderOrderHistory();
        }
    } catch (e) {
        console.error("Error fetching orders:", e);
    }
}

async function fetchKlineHistory() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/kline/${state.selectedSymbol}?interval=${state.selectedInterval}`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const json = await res.json();
        if (json.status === "success") {
            state.chartManager.loadData(json.data);
            const lastCandle = json.data[json.data.length - 1];
            if (lastCandle) {
                updateChartOverlay(lastCandle.close, 0.0);
            }
        }
    } catch (e) {
        console.error("Error fetching K-line history:", e);
    }
}

// ==========================================
// WEBSOCKET FEED
// ==========================================

function connectWebSocket() {
    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }

    const dot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");
    dot.className = "status-dot";
    statusText.innerText = "連接中...";

    const token = localStorage.getItem('token');
    const wsUrl = `${WS_BASE_URL}/ws/market/${state.selectedSymbol}?token=${encodeURIComponent(token)}`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        dot.className = "status-dot connected";
        statusText.innerText = "已連線";
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleLiveMarketPacket(data);
    };

    state.ws.onclose = (event) => {
        dot.className = "status-dot";
        statusText.innerText = "連線已中斷";
        // If closed because of authorization failure, redirect
        if (event.code === 1008) {
            console.error("WebSocket auth rejected.");
            handleLogout();
            return;
        }
        setTimeout(() => {
            if (state.ws === null) connectWebSocket();
        }, 3000);
    };

    state.ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
        dot.className = "status-dot";
        statusText.innerText = "連線錯誤";
    };
}

function handleLiveMarketPacket(data) {
    state.chartManager.updateTick(data.tick);

    const stock = state.screenerStocks.find(s => s.symbol === data.symbol);
    const prevClose = stock ? (data.price - stock.change) : data.price;
    const diff = data.price - prevClose;
    const pct = prevClose > 0 ? (diff / prevClose) * 100 : 0.0;

    updateChartOverlay(data.price, pct);
    renderOrderBookDepth(data.depth);
    appendTickLog(data.tick);

    const matchedPosition = state.positions.find(p => p.symbol === data.symbol);
    if (matchedPosition) {
        matchedPosition.current_price = data.price;
        const mv = matchedPosition.qty * data.price;
        const pnl = mv - (matchedPosition.qty * matchedPosition.buy_price);
        const pnlPct = (pnl / (matchedPosition.qty * matchedPosition.buy_price)) * 100;
        
        matchedPosition.market_value = mv;
        matchedPosition.unrealized_pnl = pnl;
        matchedPosition.pnl_percent = pnlPct;
        
        renderPortfolio();
        recalculateHeaderAssets();
    }
}

function recalculateHeaderAssets() {
    const marketVal = state.positions.reduce((sum, p) => sum + (p.qty * p.current_price), 0);
    const totalPnl = state.positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
    const totalAssets = state.accountSummary.cash + marketVal;

    document.getElementById("account-mv").innerText = formatCurrency(marketVal);
    document.getElementById("account-pnl").innerText = formatPNL(totalPnl);
    document.getElementById("account-assets").innerText = formatCurrency(totalAssets);
}

// ==========================================
// SEARCH AUTOCOMPLETE LOGIC
// ==========================================

function initSearchAutocomplete() {
    const searchInput = document.getElementById("symbol-search-input");
    const suggestions = document.getElementById("search-suggestions");

    searchInput.addEventListener("input", async (e) => {
        const query = e.target.value.trim();
        if (query.length === 0) {
            suggestions.style.display = "none";
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/api/stocks/search?query=${encodeURIComponent(query)}`, {
                headers: getAuthHeaders()
            });
            if (res.status === 401) {
                handleLogout();
                return;
            }
            const json = await res.json();
            if (json.status === "success" && json.results.length > 0) {
                renderSuggestions(json.results);
            } else {
                suggestions.innerHTML = `<div style="padding: 8px 12px; color: var(--text-muted); font-size:12px;">查無相符股票</div>`;
                suggestions.style.display = "block";
            }
        } catch (err) {
            console.error("Fuzzy search error:", err);
        }
    });

    // Close suggestions dropdown when clicking outside
    document.addEventListener("click", (e) => {
        if (!searchInput.contains(e.target) && !suggestions.contains(e.target)) {
            suggestions.style.display = "none";
        }
    });
}

function renderSuggestions(results) {
    const suggestions = document.getElementById("search-suggestions");
    suggestions.innerHTML = "";
    
    results.forEach(item => {
        const div = document.createElement("div");
        div.className = "suggestion-item";
        div.style.padding = "8px 12px";
        div.style.cursor = "pointer";
        div.style.fontSize = "12px";
        div.style.borderBottom = "1px solid rgba(255,255,255,0.02)";
        div.innerHTML = `<span style="font-weight:600; color:#fff;">${item.name}</span> <span style="color:var(--text-muted); font-family:monospace; margin-left:8px;">${item.symbol}</span>`;
        
        div.addEventListener("click", () => {
            switchStock(item.symbol, item.name);
        });
        
        suggestions.appendChild(div);
    });
    suggestions.style.display = "block";
}

function switchStock(symbol, name) {
    state.selectedSymbol = symbol;
    state.selectedName = name;

    // Update URL bar silently without reloading the page
    const newUrl = `${window.location.pathname}?symbol=${symbol}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    updateActiveStockUI();
    fetchKlineHistory();
    connectWebSocket();

    // Clear search input and suggestion dropdown
    const searchInput = document.getElementById("symbol-search-input");
    searchInput.value = "";
    document.getElementById("search-suggestions").style.display = "none";
}

// ==========================================
// UI & EVENT BINDINGS
// ==========================================

function bindUIEvents() {
    // K-Line timeframe selector
    document.querySelectorAll("#timeframe-controls .btn-tab").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll("#timeframe-controls .btn-tab").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            state.selectedInterval = e.target.dataset.val;
            fetchKlineHistory();
        });
    });

    // Technical indicator selector
    document.querySelectorAll("#indicator-controls .btn-tab").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll("#indicator-controls .btn-tab").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            state.chartManager.setIndicator(e.target.dataset.val);
        });
    });

    // Bottom tab toggles
    document.getElementById("tab-portfolio-btn").addEventListener("click", () => {
        showBottomTab("portfolio");
    });
    document.getElementById("tab-orders-btn").addEventListener("click", () => {
        showBottomTab("orders");
    });

    // Modal forms toggles
    document.getElementById("modal-action-buy").addEventListener("click", () => {
        setModalAction("BUY");
    });
    document.getElementById("modal-action-sell").addEventListener("click", () => {
        setModalAction("SELL");
    });

    document.getElementById("btn-qty-minus").addEventListener("click", () => {
        const input = document.getElementById("input-qty");
        input.value = Math.max(1, parseInt(input.value) - 1);
        updateModalEstimatedCost();
    });
    document.getElementById("btn-qty-plus").addEventListener("click", () => {
        const input = document.getElementById("input-qty");
        input.value = parseInt(input.value) + 1;
        updateModalEstimatedCost();
    });

    document.getElementById("input-qty").addEventListener("input", updateModalEstimatedCost);
    document.getElementById("input-price").addEventListener("input", updateModalEstimatedCost);

    // Limit/Market order toggles
    document.querySelectorAll("input[name='order_type']").forEach(radio => {
        radio.addEventListener("change", (e) => {
            const priceInput = document.getElementById("input-price");
            const pickerGrid = document.getElementById("picker-grid");
            if (e.target.value === "MARKET") {
                priceInput.disabled = true;
                priceInput.value = "市價";
                pickerGrid.style.opacity = "0.4";
                pickerGrid.style.pointerEvents = "none";
            } else {
                priceInput.disabled = false;
                priceInput.value = state.selectedPrice;
                pickerGrid.style.opacity = "1";
                pickerGrid.style.pointerEvents = "all";
            }
            updateModalEstimatedCost();
        });
    });

    document.getElementById("btn-close-modal").addEventListener("click", closeTradingModal);
    document.getElementById("btn-order-submit").addEventListener("click", submitOrder);
}

function showBottomTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    
    if (tabName === "portfolio") {
        document.getElementById("tab-portfolio-btn").classList.add("active");
        document.getElementById("tab-portfolio-content").classList.add("active");
    } else {
        document.getElementById("tab-orders-btn").classList.add("active");
        document.getElementById("tab-orders-content").classList.add("active");
    }
}

function updateActiveStockUI() {
    document.getElementById("active-stock-title").innerText = `${state.selectedName} (${state.selectedSymbol})`;
}

function updateChartOverlay(price, changePercent) {
    const overlay = document.getElementById("chart-overlay-info");
    const sign = changePercent > 0 ? "+" : "";
    const colorClass = changePercent > 0 ? "up" : (changePercent < 0 ? "down" : "");
    
    overlay.innerHTML = `
        <span style="font-weight: 700;">${state.selectedName} (${state.selectedSymbol})</span>
        <span class="mono ${colorClass}" style="font-weight: 700; font-size: 14px;">${price.toFixed(2)}</span>
        <span class="mono ${colorClass}">${sign}${changePercent.toFixed(2)}%</span>
    `;
}

function renderAccountSummary() {
    document.getElementById("account-cash").innerText = formatCurrency(state.accountSummary.cash);
    document.getElementById("account-mv").innerText = formatCurrency(state.accountSummary.market_value);
    document.getElementById("account-assets").innerText = formatCurrency(state.accountSummary.total_assets);
    document.getElementById("account-pnl").innerText = formatPNL(state.accountSummary.total_pnl);
}

function renderPortfolio() {
    const tbody = document.getElementById("portfolio-tbody");
    tbody.innerHTML = "";
    
    if (state.positions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">無庫存部位</td></tr>`;
        return;
    }
    
    state.positions.forEach(pos => {
        const tr = document.createElement("tr");
        const sign = pos.unrealized_pnl > 0 ? "+" : "";
        const colorClass = pos.unrealized_pnl > 0 ? "up" : (pos.unrealized_pnl < 0 ? "down" : "");
        
        tr.innerHTML = `
            <td style="font-weight: 600; cursor: pointer; color: var(--color-accent);">${pos.name} (${pos.symbol})</td>
            <td class="mono">${pos.qty}</td>
            <td class="mono">${pos.buy_price.toFixed(2)}</td>
            <td class="mono">${pos.current_price.toFixed(2)}</td>
            <td class="mono">${formatCurrency(pos.market_value)}</td>
            <td class="mono ${colorClass}" style="font-weight: 500;">
                ${sign}${formatCurrency(pos.unrealized_pnl)} (${sign}${pos.pnl_percent.toFixed(2)}%)
            </td>
            <td>
                <button class="btn-close-position" onclick="liquidatePosition('${pos.symbol}', '${pos.name}', ${pos.qty})">
                    平倉
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

function renderOrderHistory() {
    const tbody = document.getElementById("orders-tbody");
    tbody.innerHTML = "";
    
    if (state.orders.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">無交易紀錄</td></tr>`;
        return;
    }
    
    state.orders.forEach(order => {
        const tr = document.createElement("tr");
        const actionClass = order.action === "BUY" ? "up" : "down";
        const actionText = order.action === "BUY" ? "買進" : "賣出";
        
        tr.innerHTML = `
            <td>${order.timestamp}</td>
            <td>${order.symbol}</td>
            <td class="${actionClass}" style="font-weight:600;">${actionText}</td>
            <td class="mono">${order.order_type === "MARKET" ? "市價" : order.price.toFixed(2)}</td>
            <td class="mono">${order.qty}</td>
            <td class="mono">${order.exec_price > 0 ? order.exec_price.toFixed(2) : "-"}</td>
            <td style="font-weight:500; color: #0ecb81;">${order.status}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderOrderBookDepth(depth) {
    const tbody = document.getElementById("depth-tbody");
    tbody.innerHTML = "";
    
    const asks = [...depth.asks].reverse();
    const bids = [...depth.bids];
    
    const maxVol = Math.max(
        ...asks.map(a => a.volume),
        ...bids.map(b => b.volume)
    );

    asks.forEach(ask => {
        const pct = maxVol > 0 ? (ask.volume / maxVol) * 100 : 0.0;
        const tr = document.createElement("tr");
        tr.className = "ask-row";
        tr.innerHTML = `
            <td class="down" style="font-weight: 500;">${ask.price.toFixed(2)}</td>
            <td class="mono">${ask.volume}</td>
            <td class="depth-bar-container">
                <div class="depth-bar ask" style="width: ${pct}px;"></div>
            </td>
        `;
        tr.addEventListener("click", () => {
            openTradingModal("BUY", ask.price);
        });
        tbody.appendChild(tr);
    });

    const activeStock = state.screenerStocks.find(s => s.symbol === state.selectedSymbol);
    const lastPrice = activeStock ? activeStock.price : (bids[0].price + asks[0].price)/2;
    const sepTr = document.createElement("tr");
    sepTr.innerHTML = `
        <td colspan="3" style="background-color: var(--bg-main); font-weight: 700; text-align: center; padding: 4px; font-size: 13px;">
            ${lastPrice.toFixed(2)}
        </td>
    `;
    tbody.appendChild(sepTr);

    bids.forEach(bid => {
        const pct = maxVol > 0 ? (bid.volume / maxVol) * 100 : 0.0;
        const tr = document.createElement("tr");
        tr.className = "bid-row";
        tr.innerHTML = `
            <td class="up" style="font-weight: 500;">${bid.price.toFixed(2)}</td>
            <td class="mono">${bid.volume}</td>
            <td class="depth-bar-container">
                <div class="depth-bar bid" style="width: ${pct}px;"></div>
            </td>
        `;
        tr.addEventListener("click", () => {
            openTradingModal("SELL", bid.price);
        });
        tbody.appendChild(tr);
    });
}

function appendTickLog(tick) {
    const tbody = document.getElementById("ticks-tbody");
    if (!tbody) return;
    const tr = document.createElement("tr");
    
    const directionClass = tick.direction === "BUY" ? "up" : (tick.direction === "SELL" ? "down" : "");
    const flashClass = tick.direction === "BUY" ? "flash-up" : (tick.direction === "SELL" ? "flash-down" : "");
    tr.className = flashClass;

    tr.innerHTML = `
        <td>${tick.time}</td>
        <td class="mono ${directionClass}" style="font-weight:500;">${tick.price.toFixed(2)}</td>
        <td class="mono" style="text-align: right; color: var(--text-secondary);">${tick.volume}</td>
    `;
    
    tbody.insertBefore(tr, tbody.firstChild);
    if (tbody.children.length > 50) {
        tbody.removeChild(tbody.lastChild);
    }
}

// ==========================================
// TRADING ACTION MODALS
// ==========================================

function openTradingModal(action, prefilledPrice) {
    document.getElementById("modal-title").innerText = `${state.selectedName} (${state.selectedSymbol}) - 送出委託`;
    
    state.selectedPrice = prefilledPrice;
    document.getElementById("input-price").value = prefilledPrice;
    
    document.getElementById("order-type-limit").checked = true;
    document.getElementById("input-price").disabled = false;
    document.getElementById("picker-grid").style.opacity = "1";
    document.getElementById("picker-grid").style.pointerEvents = "all";

    setModalAction(action);
    renderQuickPricePicker(prefilledPrice);
    updateModalEstimatedCost();
    
    document.getElementById("modal-overlay").style.display = "flex";
}

function setModalAction(action) {
    const buyBtn = document.getElementById("modal-action-buy");
    const sellBtn = document.getElementById("modal-action-sell");
    const submitBtn = document.getElementById("btn-order-submit");
    
    if (action === "BUY") {
        buyBtn.classList.add("active");
        sellBtn.classList.remove("active");
        submitBtn.className = "btn-submit-order buy";
        submitBtn.innerText = "確認買進 (送出委託)";
    } else {
        sellBtn.classList.add("active");
        buyBtn.classList.remove("active");
        submitBtn.className = "btn-submit-order sell";
        submitBtn.innerText = "確認賣出 (送出委託)";
    }
    updateModalEstimatedCost();
}

function renderQuickPricePicker(basePrice) {
    const grid = document.getElementById("picker-grid");
    grid.innerHTML = "";
    
    let tickSize = 0.01;
    if (basePrice < 10) tickSize = 0.01;
    else if (basePrice < 50) tickSize = 0.05;
    else if (basePrice < 100) tickSize = 0.1;
    else if (basePrice < 500) tickSize = 0.5;
    else if (basePrice < 1000) tickSize = 1.0;
    else tickSize = 5.0;

    const offsets = [-2 * tickSize, -1 * tickSize, 0, 1 * tickSize, 2 * tickSize];
    
    offsets.forEach(offset => {
        const btn = document.createElement("button");
        btn.className = "picker-btn";
        const p = Math.max(0.1, basePrice + offset);
        btn.innerText = p.toFixed(2);
        btn.addEventListener("click", () => {
            document.getElementById("input-price").value = p.toFixed(2);
            state.selectedPrice = p;
            updateModalEstimatedCost();
        });
        grid.appendChild(btn);
    });
}

function updateModalEstimatedCost() {
    const qty = parseInt(document.getElementById("input-qty").value) || 0;
    const isMarket = document.getElementById("order-type-market").checked;
    
    let price = parseFloat(document.getElementById("input-price").value) || 0.0;
    if (isMarket) {
        const stock = state.screenerStocks.find(s => s.symbol === state.selectedSymbol);
        price = stock ? stock.price : 100.0;
    }

    const estCost = qty * price;
    const isBuy = document.getElementById("modal-action-buy").classList.contains("active");
    
    document.getElementById("modal-est-total").innerText = 
        `${isBuy ? '預估支出' : '預估收入'}: ${formatCurrency(estCost)}`;
}

function closeTradingModal() {
    document.getElementById("modal-overlay").style.display = "none";
}

async function submitOrder() {
    const symbol = state.selectedSymbol;
    const isBuy = document.getElementById("modal-action-buy").classList.contains("active");
    const action = isBuy ? "BUY" : "SELL";
    const qty = parseInt(document.getElementById("input-qty").value) || 0;
    const isMarket = document.getElementById("order-type-market").checked;
    
    if (qty <= 0) {
        alert("請輸入委託數量！");
        return;
    }

    let price = 0.0;
    if (!isMarket) {
        price = parseFloat(document.getElementById("input-price").value);
        if (isNaN(price) || price <= 0) {
            alert("請輸入委託價格！");
            return;
        }
    }

    const orderType = isMarket ? "MARKET" : "LIMIT";
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/order`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                symbol: symbol,
                action: action,
                price: price,
                qty: qty,
                order_type: orderType
            })
        });

        if (res.status === 401) {
            handleLogout();
            return;
        }

        const json = await res.json();
        if (json.status === "success") {
            closeTradingModal();
            await fetchInventory();
        } else {
            alert("下單失敗: " + json.detail);
        }
    } catch (e) {
        console.error("Order submission error:", e);
        alert("下單連線失敗！");
    }
}

window.liquidatePosition = function(symbol, name, qty) {
    switchStock(symbol, name);
    const stock = state.screenerStocks.find(s => s.symbol === symbol);
    const basePrice = stock ? stock.price : 100.0;

    const coverAction = qty > 0 ? "SELL" : "BUY";
    const coverQty = Math.abs(qty);

    openTradingModal(coverAction, basePrice);
    document.getElementById("input-qty").value = coverQty;
    updateModalEstimatedCost();
};

// ==========================================
// STRING / CURRENCY FORMATTERS
// ==========================================

function formatCurrency(val) {
    return `NT$ ${Math.round(val).toLocaleString()}`;
}

function formatPNL(val) {
    const sign = val > 0 ? "+" : "";
    const colorClass = val > 0 ? "up" : (val < 0 ? "down" : "");
    return `<span class="${colorClass}">${sign}NT$ ${Math.round(val).toLocaleString()}</span>`;
}
