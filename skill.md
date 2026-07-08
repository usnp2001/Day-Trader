# 當沖看盤與選股交易平台 - 系統功能與技術技能清單 (Phase 3)

本文件詳述本交易平台（Antigravity Day-Trader）所具備的各項前/後端功能、API 規格、運算邏輯與部署技能，供日後維護與擴充快查使用。

---

## 🖥 前端技術與互動功能 (Frontend Capabilities)

### 1. 多維度專業圖表 (Charting Engine)
- **核心技術**：整合 TradingView 官方 [Lightweight Charts v4.2.3](file:///d:/python/stock/frontend/index.html)。
- **技術指標運算 (Client-Side Calculations)**：
  - **分時均價線 (Average Price Line)**：$\text{均價} = \frac{\sum_{i=1}^t (\text{成交價}_i \times \text{成交量}_i)}{\sum_{i=1}^t \text{成交量}_i}$。
  - **KD (9,3,3)**：基於滑動視窗計算 RSV 值，並依遞迴公式 $K_t = \frac{2}{3}K_{t-1} + \frac{1}{3}\text{RSV}_t$ 及 $D_t = \frac{2}{3}D_{t-1} + \frac{1}{3}K_t$ 繪製。
  - **MACD (12,26,9)**：計算 EMA(12) 與 EMA(26) 的差值（DIF），以及 DIF 的 9日 EMA 信號線（DEM），並以直方圖顯示柱狀體震盪值。
  - **OBV (能量潮指標)**：根據每日收盤價相較於前一日之漲跌，累加或累減當日成交量以反映成交力道。
- **圖表互動**：
  - 滑鼠移入圖表時，主圖與副指標圖的時間軸與十字線進行**雙向滾動同步**，並支援 `try...catch` 異常保護機制避免初載崩潰。
  - 監聽圖表左鍵點擊事件，自動擷取點擊點對應的股票價格，並預填至下單小視窗。

### 2. 智慧搜尋與自動補完 (Autocomplete Suggestions)
- 於個股看板頂部設計模糊搜尋框，監聽輸入事件，即時對後端 `/api/stocks/search` 發送請求。
- 下拉選單提供 `股票名稱 (代號)` 自動補完。
- 點擊建議項後，利用 `history.pushState` **無感變更網址參數，不刷新頁面**即可無縫切換 WebSocket 與 K 線圖。

### 3. 多維選股篩選器與分頁 (Screener Form & Pagination)
- 提供量價（價格下限/上限、成交量下限）、基本面（本益比上限）及技術面（5日均線大於20日均線之多頭排列）表單。
- 支援伺服器端分頁，並透過按鈕狀態變更與不透明度控制防範重複或無效請求。
- 表格雙擊或點擊「開啟看板」按鈕，可使用 `_blank` 另開瀏覽器頁籤進入個股看板。

### 4. 身份認證與帳戶管理前端互動
- **哨兵權限防護 (Sync Auth Guard)**：首頁與看板頁在網頁載入的最前端進行同步 `localStorage` Token 判定，若無 Token 則強行退回登入頁。
- **管理者控制面板 (Admin Portal)**：為擁有 `admin` 角色之帳戶顯示「管理者後台」連結，進入 `admin.html` 後可檢視全站註冊帳戶列表與即時開立/刪除帳戶。
- **資金餘額自由修改 (Cash Editor)**：在首頁與看盤頁右上角設計「✏️」修改可用餘額，透過 Prompt 接收調整，即時與後端同步並更新 UI 資產負債指標。

---

## ⚙ 後端 API 與服務 (Backend APIs)

### 1. 安全認證與管理 APIs (Authentication & Admin REST APIs)
- `POST /api/auth/register`：使用者自助註冊。
- `POST /api/auth/login`：使用者登入。驗證成功回傳 JWT Token、使用者帳號與角色。
- `POST /api/account/adjust_cash`：調整個人可用資金餘額（受 JWT 防護）。
- `GET /api/admin/users`：列出全站註冊帳戶、角色與現金（僅限 admin 角色存取）。
- `POST /api/admin/create_user`：管理者開立特定角色（admin/user）帳戶。
- `DELETE /api/admin/delete_user/{target_username}`：管理者刪除特定帳戶。

### 2. 交易與選股 APIs (Protected REST APIs)
*以下端點均掛載 `get_current_user` 路由守衛，要求傳遞 `Authorization: Bearer <token>`：*
- `GET /api/screener/filter`：多條件模糊選股過濾。
- `GET /api/stocks/search`：模糊搜尋個股資訊。
- `GET /api/kline/{symbol}`：拉取 K 線歷史數據。
- `GET /api/inventory`：查詢目前已登入用戶之個人庫存與資產餘額（已隔離）。
- `POST /api/order`：送出個人交易委託。
- `GET /api/orders` : 查詢個人歷史交易明細（已隔離）。

### 3. WebSocket 伺服器
- `WS /ws/market/{symbol}?token=<token>`：高頻實時行情推播通道。
  - 在連線階段進行 JWT 查核，驗證通過後才 accept 連線。
  - 以 500ms 頻率推送即時成交價（Tick）與五檔（depth）委託資料包。

---

## 🗄 資料庫與快取機制 (Database & Caching)

- **持久化層 (SQLite)**：
  - `users`：儲存使用者帳密雜湊與角色分配。
  - `account`：紀錄各用戶可用現金餘額（預設一千萬 NTD，支援動態編輯）。
  - `positions`：持久化庫存部位（以 username + symbol 複合主鍵隔離），買進/賣出/平倉時自動重算，qty=0 時自動清除。
  - `orders`：紀錄成交回報詳情（依 username 進行多用戶資料隔離）。
  - `stock_metadata`：常用篩選快取表，儲存股票基本面與均線資料。
- **資料庫欄位結構文件**：
  - [database_schema.txt](file:///d:/python/stock/database_schema.txt) 說明資料庫各資料表與欄位型態、條件限制的技術文檔。
- **自研 JWT 與密碼加鹽雜湊 (auth_utils.py)**：
  - 整合 Python 標準庫 `hmac` 和 `hashlib`。使用 SHA-256 對結合 UUID salt 的密碼進行加鹽雜湊，JWT 使用 HS256 (HMAC-SHA256) 進行簽章防偽。
- **快取同步與爬蟲**：
  - [crawler.py](file:///d:/python/stock/backend/crawler.py) 整合 `yfinance`，在伺服器 boot 啟動 3 秒後開啟背景排程，爬取台灣上市（TWSE, `.TW`）與上櫃（TPEx, `.TWO`）所有股票代碼，滾動計算當前 MA5、MA20 均線值，回寫至 SQLite 快取，克服線上即時爬蟲過慢的問題。

---

## 🐳 運維與部署技能 (DevOps & GCP)

- **Docker 虛擬化**：封裝 [Dockerfile](file:///d:/python/stock/backend/Dockerfile) 輕量運行環境，透過 [docker-compose.yml](file:///d:/python/stock/docker-compose.yml) 綁定靜態網站映射（`/frontend`）與 SQLite 實體資料卷持久化。
- **GCP 最省部署 ( GCE Single-VM Scheme)**：
  - 於 Compute Engine 開設免費額度 `e2-micro` 或 `e2-small` 主機。
  - 架設 **Nginx** 反向代理與防護，處理 Port 80 轉向 HTTPS，並配置 WebSocket `Upgrade` 轉發頭。
  - 使用 **Certbot (Let's Encrypt)** 支援安全的 `wss://` 連線。
- **微服務模式演進（預留架構）**：
  - 前端與後端靜態文件解耦，可單獨上傳 GCP Cloud Storage 靜態託管 + Cloud CDN。
  - API Gateway 集中管理入口，下單服務與行情服務可拆分為獨立的 Cloud Run 容器。
