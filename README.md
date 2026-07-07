# 當沖選股與看盤交易平台 - Antigravity Day-Trader

本專案是一個專為電腦版（PC）設計的**高頻當沖選股與看盤交易平台**。本專案將選股功能獨立於首頁，並支援另開視窗連結到個股當沖看板。

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

- `/frontend`：前端靜態網站資源。
  - `index.html`：選股首頁。
  - `dashboard.html`：個股當沖看板與下單頁。
  - `styles.css`：Bloomberg 暗色調配色樣式，融合首頁表單與看板網格。
  - `app.js`：選股首頁的查詢、篩選與分頁交互邏輯。
  - `dashboard.js`：個股看板的 WebSocket、交易委託與搜尋框切換邏輯。
  - `chart.js`：Lightweight Charts 圖表初始化與技術指標數學運算。
- `/backend`：FastAPI 後端與資料庫。
  - `main.py`：伺服器入口、WebSocket 行情推播與篩選/搜尋 APIs。
  - `crawler.py`：`yfinance` 數據拉取，並於開機 3 秒後進行背景同步，支援台灣上市 (TWSE) 與上櫃 (TPEx) 股票爬取與同步，計算各股 MA5、MA20 及本益比寫入資料庫快取。
  - `database.py`：SQLite 資料庫設定。新建 `stock_metadata` 快取表，預載 25 筆熱門台美當沖股（含修正後的美股 Intel 代號 `INTC` 與美股中英文名稱映射，並新增包含台股四位數代碼與美股預設為 0 的 `stockId` 欄位）作為搜尋快查及選股基礎。
  - `broker.py`：下單網關抽象層，模擬持久化 SQLite 交易。
- `database_schema.txt`：資料庫用途與欄位結構說明文件。
- `skill.md`：本專案功能與技術規格清單。
- `README.md`：本專案手冊。

---

## 本地執行指南

### 方法一：使用 Docker Compose（推薦）
```bash
docker-compose up -d --build
```
啟動後訪問 `http://localhost:8000/` 即可進入選股首頁。

### 方法二：使用 Python 環境
1. 進入 `backend` 資料夾安裝依賴套件：
   ```bash
   pip install -r requirements.txt
   ```
2. 啟動伺服器：
   ```bash
   python main.py
   ```
3. 訪問 `http://localhost:8000/` 進入選股首頁。

---

## GCP 雲端最省成本部署指南

請參考 [skill.md](file:///d:/python/stock/skill.md) 中關於運維部署的詳情。
1. **虛擬機建立**：在 GCP 建立一個 `e2-micro`（GCP 免費額度）或 `e2-small` VM，系統選擇 `Ubuntu 22.04 LTS`。
2. **安裝 Docker & Compose**：
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   sudo apt-get install docker-compose-plugin -y
   ```
3. **複製程式碼並啟動**：將本專案複製到 VM 中，執行 `docker compose up -d --build`。
4. **架設反向代理 Nginx 與 SSL**：
   - 安裝 Nginx：`sudo apt-get install nginx -y`。
   - 編輯 `/etc/nginx/sites-available/default`，將 Port 80 轉向 `http://localhost:8000`，並針對 `/ws/` 路徑配置 WebSocket `Upgrade` 協定轉發。
   - 執行 `sudo certbot --nginx -d yourdomain.com` 申請免費 Let's Encrypt HTTPS 憑證，系統會自動將連線升級至 `https://` 與 `wss://`。

---

## 串接玉山證券或華南證券 API 步驟

當您準備進行實盤交易時：
1. **申請憑證**：向玉山證券（富果 Fugle API）或華南證券申請自動交易權限，並下載個人憑證檔（如 `.p12` 檔）。
2. **後端設定**：在後端 `backend/broker.py` 中，將真實的券商 SDK 登入與委託程式解除註釋，並放入您的帳密與憑證密鑰。
3. **主程式切換**：在 `backend/main.py` 中，將原先的 `broker = MockBroker()` 修改為您開通的實盤 Broker Gateway（如 `EsunFugleBroker()`），重啟後即可無縫切換至真實下單系統。
