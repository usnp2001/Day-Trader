# 當沖選股與看盤交易平台 - Antigravity Day-Trader (Phase 4)

本專案是一個專為電腦版（PC）設計的**高頻當沖選股與看盤交易平台**。本專案將選股功能獨立於首頁，支援另開視窗連結到個股當沖看板，並結合 FinMind 大戶籌碼與 yfinance 混合同步評價技術。

---

## 頁面功能架構

### 1. 選股首頁 (`index.html`)
- **篩選股票條件選擇（上半部）**：
  - **量價篩選**：支援現價範圍（TWD）與成交量下限（股數）篩選。
  - **基本面篩選**：支援本益比 (PE) 上限篩選。
  - **技術面篩選**：支援黃金交叉/均線多頭排列（5日均線 MA5 > 20日均線 MA20）篩選。
  - 按下「開始查詢」後由後端 API `/api/screener/filter` 即時返回篩選結果。
- **股票列表呈現與分頁（下半部）**：
  - 以高密度表格呈現符合條件的個股代碼、名稱、現價、今日漲跌幅、成交量、本益比。
  - 支援**分頁功能**（上一頁、下一頁、當前頁碼顯示），每頁預設呈現 10 筆資料。
  - **雙擊行**或**點擊「開啟看板」按鈕**，會自動**另開新瀏覽器視窗/分頁**連結到個股當沖看板。
  - **同步 Finmind**：提供管理者「同步 Finmind」按鈕，發送異步請求，於背景自動抓取 FinMind 與 yfinance 混合評價指標。

### 2. 個股當沖看板頁 (`dashboard.html`)
- **即時圖表與技術指標**：
  - 整合 TradingView 官方圖表，支援 `1m`, `5m`, `15m`, `日K`, `周K`, `月K` 週期。
  - 繪製 K 線圖、量能柱、分時**均價線**，以及副圖技術指標 **KD (9,3,3)**、**MACD (12,26,9)**、**OBV**。
- **快速搜尋框與自動補完**：
  - 頁面頂部新增搜尋框，支援輸入**股票代號（如 2330）**或**中文名稱（如 鴻海）**。
  - 提供**下拉選單建議自動補完 (Autocomplete Suggestions)**，模糊比對資料庫資料，點擊即可無感切換個股資訊（不重整頁面，利用 `history.pushState` 靜默修改網址 URL 參數）。
- **當沖交易面板與五檔**：
  - 滑鼠移入圖表時十字準心同步，左鍵點擊圖表任意位置或點擊右側五檔，自動預填該價格並彈出買賣小視窗。
  - 提供下單（買進/賣出、限價/市價、張數調整）與庫存「平倉」一鍵交易功能。

---

## 目錄結構說明

本專案採用 **MVC (Model-View-Controller) / 三層架構** 進行模組化重構，結構如下：

- `/frontend`：前端靜態網站資源。
  - `index.html`：選股首頁（附帶安全認證哨兵防護）。
  - `dashboard.html`：個股當沖看板與下單頁。
  - `admin.html`：管理者後台，可進行帳戶開立與可用資金調整。
  - `login.html`：彭博風格深色 JWT 登入認證頁。
  - `app.js`：選股首頁與 API 互動、分頁及認證狀態維護。
- `/backend`：後端 FastAPI 與核心模組。
  - `/common`：全網共通模組（含 `logger.py` 雙向日誌、`config.py` 環境變數配置、`auth_utils.py` 自研無依賴 JWT 系統）。
  - `/controller`：路由控制器層（將登入、資金、訂單與選股 API 解耦路由）。
  - `/dal`：資料存取層 (Data Access Object)（`stock_metadata_dao.py`, `user_dao.py`, `database_init.py` 負責 SQLite 升級遷移與交易隔離讀寫）。
  - `/service`：業務邏輯層（`stock_service.py` 負責串接選股篩選、K線運算與排程調用）。
  - `/jobs`：獨立排程任務層（**`sync_finmind.py`** 實作大數據批量抓取、美股補全與 ROE/營收成長率 enrichment）。
  - `main.py`：FastAPI 進程啟動入口與靜態文件映射。
  - `crawler.py`：日常背景爬蟲，提供台灣上市/上櫃個股 MA 均線快取。
  - `broker.py`：MockBroker 券商抽象層。
  - `/logs`：全網日誌輸出目標夾（`trading_platform.log`）。
- `database_schema.txt`：資料庫用途與欄位結構說明文件（已升級為 Phase 4 規格）。
- `skill.md`：本專案功能與技術規格清單。
- `README.md`：本專案手冊。

---

## 本地執行指南

### 方法一：使用 Docker Compose（推薦）
```bash
docker-compose up -d --build
```
啟動後訪問 `http://localhost:8000/` 即可進入登入頁面。

### 方法二：使用 Python 本地環境
1. 進入 `backend` 資料夾安裝依賴套件：
   ```bash
   pip install -r requirements.txt
   ```
2. 啟動伺服器：
   ```bash
   python main.py
   ```
3. 訪問 `http://localhost:8000/` 進入登入頁面（預設管理者：`admin` / `admin123`）。

---

## 隨時單獨執行背景排程任務 (Background Jobs)

本專案提供三個獨立的背景排程腳本，用於更新股價、法人籌碼與艾斯選股等數據。您可以在手動調用或配置定時任務（如 Crontab / Windows 工作排程器）時使用。

> [!TIP]
> 推薦在 **Docker 容器內** 執行這些腳本，以確保 Python 依賴套件環境一致且完整。

### 1. 艾斯選股 Excel 同步任務 (`sync_ace_selection.py`)
負責從聚財網下載並解析選股 Excel，清洗股號並將最新指標特徵存入 `ace_watchlist`，並記錄實際執行的 TIMESTAMP 時間戳記。
* **在 Docker 容器內執行（推薦）：**
  ```bash
  docker-compose exec backend python jobs/sync_ace_selection.py
  ```
* **在本機 Windows 環境下執行：**
  *(需先在本機執行 `pip install -r backend/requirements.txt`)*
  ```bash
  python jobs/sync_ace_selection.py
  ```

### 2. FinMind 大戶籌碼與美股資料同步任務 (`sync_finmind.py`)
下載全台股 PER、三大法人與融資券大數據，並透過 yfinance 獲取美股 PE/PB、ROE 等指標。
* **在 Docker 容器內執行（推薦）：**
  ```bash
  docker-compose exec backend python jobs/sync_finmind.py
  ```
* **在本機 Windows 環境下執行：**
  ```bash
  python jobs/sync_finmind.py
  ```

### 3. 個股即時評價與爬蟲快取更新任務 (`sync_yfinance.py`)
日常更新台灣上市/上櫃個股與熱門股的即時股價、漲跌幅、成交量及 MA5/MA20 快取。
* **在 Docker 容器內執行（推薦）：**
  ```bash
  docker-compose exec backend python jobs/sync_yfinance.py
  ```
* **在本機 Windows 環境下執行：**
  ```bash
  python jobs/sync_yfinance.py
  ```

---

## GCP 雲端最省成本部署指南
詳情請參考 [skill.md](file:///d:/python/stock/skill.md) 中的 DevOps 部署流程。
1. 在 GCP Compute Engine 建立一個 `Ubuntu 22.04 LTS` VM (選取 `e2-micro` 可享有免費額度)。
2. 安裝 Docker 並上傳程式碼，執行 `docker compose up -d --build` 啟動容器。
3. 使用 **Nginx** 反向代理接收 Port 80 流量並配置 WebSocket 連線轉發頭。
4. 安裝 **Certbot** 獲取免費的 Let's Encrypt SSL 憑證，強制跳轉 `https` 與 `wss`。
