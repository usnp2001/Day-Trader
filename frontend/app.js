// app.js - Home stock screener form and paginated list controller

const state = {
    currentPage: 1,
    totalPages: 1,
    pageSize: 10,
    filters: {
        price_min: 0,
        price_max: 999999,
        min_volume: 0,
        pe_max: 999999,
        ma_bullish: false,
        exclude_us: false
    }
};

const API_BASE_URL = `${window.location.protocol}//${window.location.host}`;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial default query to present list of stocks on load
    fetchFilteredStocks();

    // 2. Bind Form and Pagination UI Events
    bindEvents();
});

function bindEvents() {
    // Form submit query listener
    const form = document.getElementById("filter-form");
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        
        // Read form inputs
        const priceMin = parseFloat(document.getElementById("filter-price-min").value) || 0;
        const priceMax = parseFloat(document.getElementById("filter-price-max").value) || 999999;
        const minVol = parseInt(document.getElementById("filter-volume-min").value) || 0;
        const peMax = parseFloat(document.getElementById("filter-pe-max").value) || 999999;
        const maBullish = document.getElementById("filter-ma-bullish").checked;
        const excludeUs = document.getElementById("filter-exclude-us").checked;

        // Save filters to state
        state.filters = {
            price_min: priceMin,
            price_max: priceMax,
            min_volume: minVol,
            pe_max: peMax,
            ma_bullish: maBullish,
            exclude_us: excludeUs
        };
        
        // Reset to page 1
        state.currentPage = 1;
        fetchFilteredStocks();
    });

    // Pagination Button Listeners
    document.getElementById("btn-prev-page").addEventListener("click", () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchFilteredStocks();
        }
    });

    document.getElementById("btn-next-page").addEventListener("click", () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchFilteredStocks();
        }
    });
}

async function fetchFilteredStocks() {
    const tbody = document.getElementById("screener-results-tbody");
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px;">查詢中，請稍後...</td></tr>`;

    // Construct URL query parameters
    const params = new URLSearchParams({
        price_min: state.filters.price_min,
        price_max: state.filters.price_max,
        min_volume: state.filters.min_volume,
        pe_max: state.filters.pe_max,
        ma_bullish: state.filters.ma_bullish,
        exclude_us: state.filters.exclude_us,
        page: state.currentPage,
        page_size: state.pageSize
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/screener/filter?${params.toString()}`);
        const json = await res.json();
        
        if (json.status === "success") {
            state.totalPages = json.total_pages;
            state.currentPage = json.current_page;
            
            document.getElementById("results-count").innerText = `共 ${json.total_count} 筆資料`;
            renderStockList(json.stocks);
            updatePaginationUI();
        } else {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--color-up); padding: 40px;">查詢錯誤: ${json.detail}</td></tr>`;
        }
    } catch (err) {
        console.error("Filter request failed:", err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--color-up); padding: 40px;">選股伺服器連線失敗！</td></tr>`;
    }
}

function renderStockList(stocks) {
    const tbody = document.getElementById("screener-results-tbody");
    tbody.innerHTML = "";

    if (stocks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px;">無符合篩選條件的股票</td></tr>`;
        return;
    }

    stocks.forEach(stock => {
        const tr = document.createElement("tr");
        
        const sign = stock.change > 0 ? "+" : "";
        const colorClass = stock.change > 0 ? "up" : (stock.change < 0 ? "down" : "");
        const peValue = stock.pe_ratio ? stock.pe_ratio.toFixed(1) : "-";

        tr.innerHTML = `
            <td style="padding: 12px 8px; font-weight:600; font-family: monospace;">${stock.symbol}</td>
            <td style="font-weight:600; color: #fff;">${stock.name}</td>
            <td class="mono ${colorClass}" style="text-align: right; font-weight:500;">
                ${stock.price.toFixed(2)}
            </td>
            <td class="mono ${colorClass}" style="text-align: right;">
                ${sign}${stock.change_percent.toFixed(2)}%
            </td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">
                ${stock.volume.toLocaleString()}
            </td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">
                ${peValue}
            </td>
            <td style="text-align: center;">
                <button class="btn-tab" style="background-color: var(--color-accent); color: #fff; border:none; padding: 4px 12px; font-size:11px; border-radius:3px; cursor:pointer;" onclick="openDashboard('${stock.symbol}')">
                    開啟看板
                </button>
            </td>
        `;
        
        // Double-click row to open dashboard
        tr.style.cursor = "pointer";
        tr.addEventListener("dblclick", () => {
            openDashboard(stock.symbol);
        });

        tbody.appendChild(tr);
    });
}

function updatePaginationUI() {
    const prevBtn = document.getElementById("btn-prev-page");
    const nextBtn = document.getElementById("btn-next-page");
    const pageIndicator = document.getElementById("page-indicator");

    pageIndicator.innerText = `第 ${state.currentPage} / ${state.totalPages} 頁`;

    prevBtn.disabled = state.currentPage <= 1;
    nextBtn.disabled = state.currentPage >= state.totalPages;
    
    // Style disabled buttons
    prevBtn.style.opacity = prevBtn.disabled ? "0.3" : "1";
    prevBtn.style.cursor = prevBtn.disabled ? "not-allowed" : "pointer";
    nextBtn.style.opacity = nextBtn.disabled ? "0.3" : "1";
    nextBtn.style.cursor = nextBtn.disabled ? "not-allowed" : "pointer";
}

// Global window link function
window.openDashboard = function(symbol) {
    window.open(`dashboard.html?symbol=${symbol}`, "_blank");
};
