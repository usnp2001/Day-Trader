// app.js - Home stock screener form and paginated list controller

const state = {
    currentPage: 1,
    totalPages: 1,
    pageSize: 15,
    currentMode: "filter", // "filter" or "ace"
    sortBy: null,
    sortOrder: null, // "asc", "desc" or null
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
    // Initialize user session header
    initializeHeader();

    // 1. Initial default query to present list of stocks on load
    fetchStocks();

    // 2. Bind Form and Pagination UI Events
    bindEvents();
});

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
        const syncBtn = document.getElementById('btn-sync-finmind');
        if (syncBtn) {
            syncBtn.style.display = 'inline-block';
            syncBtn.addEventListener('click', handleSyncFinMind);
        }
        const syncYfBtn = document.getElementById('btn-sync-yfinance');
        if (syncYfBtn) {
            syncYfBtn.style.display = 'inline-block';
            syncYfBtn.addEventListener('click', handleSyncYFinance);
        }
        const syncOfficialBtn = document.getElementById('btn-sync-official');
        if (syncOfficialBtn) {
            syncOfficialBtn.style.display = 'inline-block';
            syncOfficialBtn.addEventListener('click', handleSyncOfficial);
        }
    }

    // Fetch user cash to show in header
    fetchUserCash();

    // Fetch user profile and avatar
    fetchUserProfileAndSetAvatar();

    // Bind cash adjustment pencil trigger
    const btnEditCash = document.getElementById('btn-edit-cash');
    if (btnEditCash) {
        btnEditCash.addEventListener('click', handleAdjustCash);
    }

    // Bind profile edit modal trigger
    const btnUserProfile = document.getElementById('btn-user-profile');
    if (btnUserProfile) {
        btnUserProfile.addEventListener('click', openProfileModal);
    }
}

async function fetchUserCash() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/inventory`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        const json = await res.json();
        if (json.status === 200) {
            updateCashDisplay(json.result.summary.cash);
        }
    } catch (err) {
        console.error("Failed to fetch account cash:", err);
    }
}

function updateCashDisplay(cash) {
    const formatted = new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(cash);
    document.getElementById('header-user-cash').textContent = formatted;
}

async function handleAdjustCash() {
    const currentCashVal = parseFloat(document.getElementById('header-user-cash').textContent.replace(/[^0-9.-]+/g,""));
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
        if (res.ok && data.status === 200) {
            updateCashDisplay(newCash);
        } else {
            alert(data.detail || '金額修改失敗');
        }
    } catch (err) {
        alert('連線伺服器失敗，請確認網路狀態。');
    }
}

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
        
        state.currentMode = "filter";
        // Reset to page 1
        state.currentPage = 1;
        fetchStocks();
    });

    // Ace stock selection button listener
    const btnAce = document.getElementById("btn-ace-screener");
    if (btnAce) {
        btnAce.addEventListener("click", () => {
            state.currentMode = "ace";
            state.currentPage = 1;
            fetchStocks();
        });
    }

    // AI stock selection button listener
    const btnAi = document.getElementById("btn-ai-screener");
    if (btnAi) {
        btnAi.addEventListener("click", () => {
            state.currentMode = "ai";
            state.currentPage = 1;
            fetchStocks();
        });
    }

    // Pagination Button Listeners
    document.getElementById("btn-prev-page").addEventListener("click", () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchStocks();
        }
    });

    document.getElementById("btn-next-page").addEventListener("click", () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchStocks();
        }
    });

    // Page Size Select Change Listener
    const selectPageSize = document.getElementById("select-page-size");
    if (selectPageSize) {
        selectPageSize.value = state.pageSize;
        selectPageSize.addEventListener("change", function() {
            state.pageSize = parseInt(this.value);
            state.currentPage = 1;
            fetchStocks();
        });
    }

    // Column Headers Clicking Listeners
    document.querySelectorAll(".screener-list th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const field = th.getAttribute("data-sort");
            if (state.sortBy !== field) {
                state.sortBy = field;
                state.sortOrder = "desc";
            } else {
                if (state.sortOrder === "desc") {
                    state.sortOrder = "asc";
                } else {
                    state.sortBy = null;
                    state.sortOrder = null;
                }
            }
            updateSortHeadersUI();
            fetchStocks();
        });
    });
}

async function fetchStocks() {
    const tbody = document.getElementById("screener-results-tbody");
    tbody.innerHTML = `<tr><td colspan="17" style="text-align: center; color: var(--text-muted); padding: 40px;">查詢中，請稍後...</td></tr>`;

    let url;
    if (state.currentMode === "ace") {
        const params = new URLSearchParams({
            page: state.currentPage,
            page_size: state.pageSize
        });
        if (state.sortBy) {
            params.append("sort_by", state.sortBy);
            params.append("sort_order", state.sortOrder);
        }
        url = `${API_BASE_URL}/api/screener/ace?${params.toString()}`;
    } else if (state.currentMode === "ai") {
        const params = new URLSearchParams();
        if (state.sortBy) {
            params.append("sort_by", state.sortBy);
            params.append("sort_order", state.sortOrder);
        }
        url = `${API_BASE_URL}/api/screener/ai?${params.toString()}`;
    } else {
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
        if (state.sortBy) {
            params.append("sort_by", state.sortBy);
            params.append("sort_order", state.sortOrder);
        }
        url = `${API_BASE_URL}/api/screener/filter?${params.toString()}`;
    }

    // Update panel title header dynamically based on current mode
    const panelTitle = document.getElementById("panel-title-text");
    if (panelTitle) {
        if (state.currentMode === "ace") {
            panelTitle.innerText = "符合條件股票清單 (艾斯選股)";
        } else if (state.currentMode === "ai") {
            panelTitle.innerText = "符合條件股票清單 (AI預測選股)";
        } else {
            panelTitle.innerText = "符合條件股票清單 (自訂篩選)";
        }
    }

    try {
        const res = await fetch(url, {
            headers: getAuthHeaders()
        });
        
        if (res.status === 401) {
            handleLogout();
            return;
        }

        const json = await res.json();
        
        if (json.status === 200) {
            if (state.currentMode === "ai") {
                state.totalPages = 1;
                state.currentPage = 1;
                document.getElementById("results-count").innerText = `共 ${json.result.stocks.length} 筆資料 (AI預測排序)`;
                updatePaginationInfo(json.result.stocks.length, json.result.stocks.length);
            } else {
                state.totalPages = json.result.total_pages;
                state.currentPage = json.result.current_page;
                document.getElementById("results-count").innerText = `共 ${json.result.total_count} 筆資料`;
                updatePaginationInfo(json.result.total_count, json.result.stocks.length);
            }
            renderStockList(json.result.stocks);
            updatePaginationUI();
        } else {
            tbody.innerHTML = `<tr><td colspan="18" style="text-align: center; color: var(--color-up); padding: 40px;">查詢錯誤: ${json.message || json.detail}</td></tr>`;
        }
    } catch (err) {
        console.error("Fetch request failed:", err);
        tbody.innerHTML = `<tr><td colspan="18" style="text-align: center; color: var(--color-up); padding: 40px;">選股伺服器連線失敗！</td></tr>`;
    }
}

function renderStockList(stocks) {
    const tbody = document.getElementById("screener-results-tbody");
    tbody.innerHTML = "";
    
    const chkAll = document.getElementById('check-all-screener');
    if (chkAll) chkAll.checked = false;

    if (stocks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="18" style="text-align: center; color: var(--text-muted); padding: 40px;">無符合篩選條件的股票</td></tr>`;
        return;
    }

    stocks.forEach(stock => {
        const tr = document.createElement("tr");
        
        const sign = stock.change > 0 ? "+" : "";
        const colorClass = stock.change > 0 ? "up" : (stock.change < 0 ? "down" : "");
        const peValue = stock.pe_ratio ? stock.pe_ratio.toFixed(1) : "-";
        
        // FinMind expanded columns formatting
        const pbValue = stock.pb_ratio ? stock.pb_ratio.toFixed(2) : "-";
        const divValue = stock.dividend_yield ? stock.dividend_yield.toFixed(2) + "%" : "-";
        const foreignNet = stock.foreign_net_buy !== null && stock.foreign_net_buy !== undefined ? stock.foreign_net_buy.toLocaleString() : "-";
        const trustNet = stock.trust_net_buy !== null && stock.trust_net_buy !== undefined ? stock.trust_net_buy.toLocaleString() : "-";
        const dealerNet = stock.dealer_net_buy !== null && stock.dealer_net_buy !== undefined ? stock.dealer_net_buy.toLocaleString() : "-";
        const marginBal = stock.margin_balance !== null && stock.margin_balance !== undefined ? stock.margin_balance.toLocaleString() : "-";
        const shortBal = stock.short_balance !== null && stock.short_balance !== undefined ? stock.short_balance.toLocaleString() : "-";
        const revYoY = stock.revenue_yoy ? stock.revenue_yoy.toFixed(2) + "%" : "-";
        const aiProbVal = (stock.ai_prob !== undefined && stock.ai_prob !== null) ? `${stock.ai_prob}%` : "-";
        const aiProbStyle = stock.ai_prob !== undefined ? "color: #b388ff; font-weight: bold;" : "color: var(--text-secondary);";

        tr.innerHTML = `
            <td style="text-align: center; padding: 12px 10px;" onclick="event.stopPropagation()">
                <input type="checkbox" class="screener-row-checkbox" value="${stock.symbol}" onclick="onScreenerRowCheckboxClick(event)">
            </td>
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
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${pbValue}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${divValue}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${foreignNet}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${trustNet}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${dealerNet}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${marginBal}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${shortBal}</td>
            <td class="mono" style="text-align: right; color: var(--text-secondary);">${revYoY}</td>
            <td class="mono" style="text-align: right; ${aiProbStyle}">${aiProbVal}</td>
            <td class="mono" style="text-align: right; color: var(--text-muted); font-size: 11px; white-space: nowrap;">${stock.updateDate || "-"}</td>
            <td style="text-align: center;">
                <button class="btn-tab-icon" title="開啟個股看板" onclick="openDashboard('${stock.symbol}')">
                    📊
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

function updateSortHeadersUI() {
    document.querySelectorAll(".screener-list th.sortable").forEach(th => {
        const field = th.getAttribute("data-sort");
        th.classList.remove("asc", "desc");
        if (state.sortBy === field) {
            th.classList.add(state.sortOrder);
        }
    });
}

function updatePaginationInfo(totalCount, currentCount) {
    const infoDiv = document.getElementById("pagination-info");
    if (!infoDiv) return;
    if (totalCount === 0) {
        infoDiv.innerText = "";
        return;
    }
    const start = (state.currentPage - 1) * state.pageSize + 1;
    const end = start + currentCount - 1;
    infoDiv.innerText = `顯示第 ${start} - ${end} 筆，共 ${totalCount} 筆`;
}

// Global window link function
window.openDashboard = function(symbol) {
    window.open(`dashboard.html?symbol=${symbol}`, "_blank");
};

// ==========================================
// USER PROFILE SETTINGS CONTROLLERS
// ==========================================

async function fetchUserProfileAndSetAvatar() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/user/profile`, {
            headers: getAuthHeaders()
        });
        if (res.ok) {
            const json = await res.json();
            if (json.status === 200 && json.result) {
                const profile = json.result;
                const avatarImg = document.getElementById('header-user-avatar');
                if (avatarImg) {
                    if (profile.profile_pic) {
                        avatarImg.src = profile.profile_pic;
                        avatarImg.style.display = 'inline-block';
                    } else {
                        avatarImg.src = '/uploads/default-avatar.png';
                        avatarImg.style.display = 'inline-block';
                    }
                }
            }
        }
    } catch (err) {
        console.error("Failed to fetch user profile:", err);
    }
}

window.openProfileModal = async function() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/user/profile`, {
            headers: getAuthHeaders()
        });
        
        if (res.status === 401) {
            handleLogout();
            return;
        }
        
        const json = await res.json();
        if (res.ok && json.status === 200) {
            const profile = json.result;
            
            document.getElementById('profile-username').value = profile.username;
            document.getElementById('profile-name').value = profile.name || '';
            document.getElementById('profile-email').value = profile.email || '';
            document.getElementById('profile-phone').value = profile.phone || '';
            document.getElementById('profile-address').value = profile.address || '';
            document.getElementById('profile-avatar-url').value = profile.profile_pic || '';
            document.getElementById('profile-password').value = ''; // keep blank
            
            const previewImg = document.getElementById('profile-avatar-preview');
            if (profile.profile_pic) {
                previewImg.src = profile.profile_pic;
                previewImg.style.display = 'block';
            } else {
                previewImg.src = '/uploads/default-avatar.png';
                previewImg.style.display = 'block';
            }
            
            document.getElementById('profile-modal').style.display = 'flex';
        } else {
            alert('無法獲取個人資料：' + json.detail);
        }
    } catch (err) {
        alert('連線伺服器失敗，無法載入個人設定。');
    }
};

window.closeProfileModal = function() {
    document.getElementById('profile-modal').style.display = 'none';
};

window.uploadAvatarFile = async function(input, targetUrlInputId, previewImgId) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/upload_avatar`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (response.ok && data.status === 200) {
            document.getElementById(targetUrlInputId).value = data.result.avatar_url;
            const previewImg = document.getElementById(previewImgId);
            previewImg.src = data.result.avatar_url;
            previewImg.style.display = 'block';
            alert('大頭照上傳成功！');
        } else {
            alert(data.detail || '大頭照上傳失敗');
        }
    } catch (err) {
        alert('大頭照上傳失敗，伺服器連線異常。');
    }
};

window.handleSaveProfile = async function(e) {
    e.preventDefault();
    
    const email = document.getElementById('profile-email').value.trim();
    const name = document.getElementById('profile-name').value.trim();
    const phone = document.getElementById('profile-phone').value.trim();
    const address = document.getElementById('profile-address').value.trim();
    const profile_pic = document.getElementById('profile-avatar-url').value;
    const password = document.getElementById('profile-password').value;
    
    const submitBtn = document.getElementById('btn-save-profile');
    submitBtn.disabled = true;
    submitBtn.textContent = '儲存中...';
    
    const payload = { email, name, phone, address, profile_pic };
    if (password) {
        payload.password = password;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/user/profile`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        if (response.ok && data.status === 200) {
            alert('個人資料儲存成功！');
            closeProfileModal();
            fetchUserProfileAndSetAvatar(); // Refresh header avatar
        } else {
            alert(data.detail || '個人資料儲存失敗');
        }
    } catch (err) {
        alert('儲存失敗，請檢查網路狀態。');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '儲存個人資料';
    }
};

// Cookie Helpers
function setCookie(name, value, seconds) {
    const d = new Date();
    d.setTime(d.getTime() + (seconds * 1000));
    document.cookie = `${name}=${value};expires=${d.toUTCString()};path=/`;
}

function getCookie(name) {
    const ca = document.cookie.split(';');
    const nameEQ = `${name}=`;
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i].trim();
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

window.handleSyncFinMind = async function() {
    const btn = document.getElementById("btn-sync-finmind");
    
    // Check Cooldown Cookie
    const cooldownStart = getCookie("finmind_sync_cooldown");
    if (cooldownStart) {
        const elapsed = Math.floor((Date.now() - parseInt(cooldownStart)) / 1000);
        const remaining = 900 - elapsed; // 15 minutes = 900 seconds
        if (remaining > 0) {
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            alert(`同步間隔為 15 分鐘！請於 ${minutes} 分 ${seconds} 秒後再試。`);
            return;
        }
    }
    
    btn.disabled = true;
    btn.textContent = "同步中...";
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/sync_finmind`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            handleLogout();
            return;
        }
        
        const data = await response.json();
        if (response.ok) {
            // Set cooldown start timestamp in cookie (expires in 900 seconds)
            setCookie("finmind_sync_cooldown", Date.now().toString(), 900);
            alert("同步任務已啟動！系統已在背景開始自 FinMind 抓取數據。因爲要抓取全市場股票，若您使用的是免費 Token，當達到每小時 600 次上限時，背景任務將會自動儲存已拉取的股票資料並優雅中止。請稍候點擊「查詢」重新加載列表。");
        } else {
            alert(data.detail || "同步任務啟動失敗！");
        }
    } catch (err) {
        alert("連線伺服器失敗，無法啟動同步。");
    } finally {
        btn.disabled = false;
        btn.textContent = "同步 Finmind";
    }
};

window.handleSyncYFinance = async function() {
    const btn = document.getElementById("btn-sync-yfinance");
    
    // Check Cooldown Cookie
    const cooldownStart = getCookie("yfinance_sync_cooldown");
    if (cooldownStart) {
        const elapsed = Math.floor((Date.now() - parseInt(cooldownStart)) / 1000);
        const remaining = 900 - elapsed; // 15 minutes = 900 seconds
        if (remaining > 0) {
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            alert(`同步間隔為 15 分鐘！請於 ${minutes} 分 ${seconds} 秒後再試。`);
            return;
        }
    }
    
    btn.disabled = true;
    btn.textContent = "同步中...";
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/sync_yfinance`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            handleLogout();
            return;
        }
        
        const data = await response.json();
        if (response.ok) {
            // Set cooldown start timestamp in cookie (expires in 900 seconds)
            setCookie("yfinance_sync_cooldown", Date.now().toString(), 900);
            alert("yFinance 同步任務已啟動！系統已在背景開始抓取基本面數據（包含本益比、淨值比、殖利率、ROE 及營收成長率）。請稍候點擊「查詢」重新加載列表。");
        } else {
            alert(data.detail || "同步任務啟動失敗！");
        }
    } catch (err) {
        alert("連線伺服器失敗，無法啟動同步。");
    } finally {
        btn.disabled = false;
        btn.textContent = "同步 yFinance";
    }
};

window.handleSyncOfficial = async function() {
    const btn = document.getElementById("btn-sync-official");
    
    // Check Cooldown Cookie
    const cooldownStart = getCookie("official_sync_cooldown");
    if (cooldownStart) {
        const elapsed = Math.floor((Date.now() - parseInt(cooldownStart)) / 1000);
        const remaining = 900 - elapsed; // 15 minutes = 900 seconds
        if (remaining > 0) {
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            alert(`官方數據同步間隔為 15 分鐘！請於 ${minutes} 分 ${seconds} 秒後再試。`);
            return;
        }
    }
    
    btn.disabled = true;
    btn.textContent = "同步中...";
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/sync_official`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            handleLogout();
            return;
        }
        
        const data = await response.json();
        if (response.ok) {
            // Set cooldown start timestamp in cookie (expires in 900 seconds)
            setCookie("official_sync_cooldown", Date.now().toString(), 900);
            alert("官方數據同步任務已啟動！系統已在背景開始自 TWSE 與 TPEx 官方網站抓取最新的大數據，並整合 yFinance 熱門股基本面。這是一個 100% 免費且不受限制的同步通道。請稍候點擊「查詢」重新加載列表。");
        } else {
            alert(data.detail || "官方數據同步任務啟動失敗！");
        }
    } catch (err) {
        alert("連線伺服器失敗，無法啟動同步。");
    } finally {
        btn.disabled = false;
        btn.textContent = "同步官方數據";
    }
};

// ==========================================
// BULK WATCHLIST SELECTION LOGIC
// ==========================================

window.toggleScreenerCheckAll = function(master) {
    const checkboxes = document.querySelectorAll('.screener-row-checkbox');
    checkboxes.forEach(cb => cb.checked = master.checked);
};

window.onScreenerRowCheckboxClick = function(event) {
    event.stopPropagation();
    const total = document.querySelectorAll('.screener-row-checkbox').length;
    const checked = document.querySelectorAll('.screener-row-checkbox:checked').length;
    const chkAll = document.getElementById('check-all-screener');
    if (chkAll) {
        chkAll.checked = (total === checked && total > 0);
    }
};

window.handleAddSelectedToWatchlist = async function() {
    const checkedCbs = document.querySelectorAll('.screener-row-checkbox:checked');
    if (checkedCbs.length === 0) {
        alert("請先勾選要加入自選清單的股票！");
        return;
    }

    const symbols = Array.from(checkedCbs).map(cb => cb.value);
    const btn = document.getElementById("btn-add-to-watchlist");
    if (!btn) return;
    
    btn.disabled = true;
    const origText = btn.innerHTML;
    btn.textContent = "⌛ 新增中...";

    try {
        let addedCount = 0;
        let failedCount = 0;
        
        for (const symbol of symbols) {
            const response = await fetch('/api/watchlist', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ symbol: symbol })
            });
            if (response.ok) {
                addedCount++;
            } else {
                failedCount++;
            }
        }
        
        alert(`成功將 ${addedCount} 檔股票加入自選清單！` + (failedCount > 0 ? ` (有 ${failedCount} 檔加入失敗)` : ""));
        
        // Clear all checkboxes
        checkedCbs.forEach(cb => cb.checked = false);
        const chkAll = document.getElementById('check-all-screener');
        if (chkAll) chkAll.checked = false;
    } catch (err) {
        alert("加入自選清單時發生網路錯誤: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origText;
    }
};

