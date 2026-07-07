# 當沖看盤與選股交易平台 - 系統功能與技術技能清單 (skill.md)

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

---

## ⚙ 後端 API 與服務 (Backend APIs)

### 1. RESTful APIs
- `GET /api/screener/filter`：多條件模糊選股過濾。
  - 參數：`price_min` (float), `price_max` (float), `min_volume` (int), `pe_max` (float), `ma_bullish` (bool), `page` (int), `page_size` (int)
  - 回傳：符合條件的個股 JSON 清單、總筆數、總頁數。
- `GET /api/stocks/search`：模糊搜尋個股資訊。
  - 參數：`query` (string)
  - 回傳：名稱與代碼清單，上限 10 筆。
- `GET /api/kline/{symbol}`：拉取 K 線歷史數據。
  - 參數：`interval` (1m, 5m, 15m, 1d, 1wk, 1mo)
- `GET /api/inventory`：查詢持股與餘額。
- `POST /api/order`：送出下單交易。
  - Payload: `{ symbol: string, action: 'BUY'|'SELL', price: float, qty: int, order_type: 'LIMIT'|'MARKET' }`
- `GET /api/orders`：查詢成交歷史紀錄。

### 2. WebSocket 伺服器
- `WS /ws/market/{symbol}`：高頻實時行情推播通道。
  - 以 500ms 頻率推送即時成交價（Tick）與五檔（depth）委託資料包。

---

## 🗄 資料庫與快取機制 (Database & Caching)

- **持久化層 (SQLite)**：
  - `account`：紀錄目前可用現金餘額（預設一千萬 NTD）。
  - `positions`：持久化庫存部位，買進/賣出/平倉時自動做加權平均成本重算，並在 qty=0 時自動清除。
  - `orders`：紀錄成交回報詳情。
  - `stock_metadata`：常用篩選快取表，儲存股票基本面與均線資料（已修正美股 Intel 交易代號為 `INTC` 並引入美股中英文名稱映射關係，並於欄位新增 `stockId`，台股為 4 位數代號數值，美股則給 0）。
- **資料庫欄位結構文件**：
  - [database_schema.txt](file:///d:/python/stock/database_schema.txt) 說明資料庫各資料表與欄位型態、條件限制的獨立技術文檔。
- **快取同步與爬蟲**：
  - [crawler.py](file:///d:/python/stock/backend/crawler.py) 整合 `yfinance`，在伺服器 boot 啟動 3 秒後開啟背景排程，爬取台灣上市（TWSE, `.TW`）與上櫃（TPEx, `.TWO`）所有股票代碼，向外部抓取各股 PE 與 Close 歷史數據，滾動計算當前 MA5、MA20 均線值，回寫至 SQLite 快取，藉此讓首頁選股擁有毫秒級的查詢效率，克服線上即時爬蟲過慢的問題。

---

## 🐳 運維與部署技能 (DevOps & GCP)

- **Docker 虛擬化**：封裝 [Dockerfile](file:///d:/python/stock/backend/Dockerfile) 輕量運行環境，透過 [docker-compose.yml](file:///d:/python/stock/docker-compose.yml) 綁定靜態網站映射（`/frontend`）與 SQLite 實體資料卷持久化。
- **GCP 最省部署 ( GCE Single-VM Scheme)**：
  - 於 Compute Engine 開設免費額度 `e2-micro` 或 `e2-small` 主機。
  - 架設 **Nginx** 反向代理與防護，處理 Port 80 轉向 HTTPS，並配置 WebSocket `Upgrade` 轉發頭。
  - 使用 **Certbot (Let's Encrypt)** 取得免費且會自動续期的 SSL 憑證，支援安全的 `wss://` 連線。
- **微服務模式演進（預留架構）**：
  - 前端與後端靜態文件解耦，可單獨上傳 GCP Cloud Storage 靜態託管 + Cloud CDN。
  - API Gateway 集中管理入口，下單服務與行情服務可拆分為獨立的 Cloud Run 容器。
