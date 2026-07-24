import sys
import os
import datetime
import requests
import time
import yfinance as yf

# Disable urllib3 warnings about insecure requests (for verify=False)
requests.packages.urllib3.disable_warnings()

# Add parent directory to sys.path to resolve backend package imports
if os.path.exists("/app/dal"):
    backend_dir = "/app"
else:
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dal.stock_metadata_dao import StockMetadataDao
from common.logger import logger
from common.config import DB_TYPE, DB_FILE
from common.base_dao import BaseDAO, OperationalError

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
    "Connection": "keep-alive"
}

def try_float(val):
    if val is None:
        return None
    val_str = str(val).strip().replace(",", "")
    if val_str in ["-", "", "N/A", "null"]:
        return None
    try:
        return float(val_str)
    except ValueError:
        return None

def try_int(val):
    if val is None:
        return 0
    val_str = str(val).strip().replace(",", "")
    if val_str in ["-", "", "N/A", "null"]:
        return 0
    try:
        return int(float(val_str))
    except ValueError:
        return 0

def parse_roc_date_to_gregorian(roc_date_str):
    """Converts a ROC date string (e.g. '1150709' or '115/07/09') to 'YYYYMMDD'."""
    cleaned = roc_date_str.replace("/", "").strip()
    if not cleaned.isdigit():
        return datetime.date.today().strftime("%Y%m%d")
    if len(cleaned) == 7:
        year = int(cleaned[:3]) + 1911
        month = cleaned[3:5]
        day = cleaned[5:]
        return f"{year}{month}{day}"
    elif len(cleaned) == 6:
        year = int(cleaned[:2]) + 1911
        month = cleaned[2:4]
        day = cleaned[4:]
        return f"{year}{month}{day}"
    return datetime.date.today().strftime("%Y%m%d")

def sync_yfinance_top_50():
    """Syncs US stocks and top 50 volume stocks using yfinance."""
    logger.info("[SyncOfficial] --- Starting yfinance fundamental metrics scan (Top 50 Volume + US) ---")
    if DB_TYPE == "sqlite" and not os.path.exists(DB_FILE):
        logger.error(f"[SyncOfficial] Database file not found at: {DB_FILE}")
        return
        
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId FROM stock_metadata")
    rows = cursor.fetchall()
    conn.close()
    
    # Sort all stocks by volume descending to find top 50 volume stocks
    sorted_by_volume = sorted(rows, key=lambda x: x[5] or 0, reverse=True)
    top_50_volume = sorted_by_volume[:50]
    
    # Gather all US stocks
    us_stocks = [r for r in rows if not (r[0].endswith(".TW") or r[0].endswith(".TWO"))]
    
    # Combine top 50 volume stocks and US stocks, prioritizing top 50 volume stocks first
    seen = set()
    targets = []
    
    # Add top 50 volume stocks first
    for r in top_50_volume:
        if r[0] not in seen:
            seen.add(r[0])
            targets.append(r)
            
    # Add any remaining US stocks
    for r in us_stocks:
        if r[0] not in seen:
            seen.add(r[0])
            targets.append(r)
            
    logger.info(f"[SyncOfficial] Target list for yfinance info sync (total {len(targets)}): {[t[0] for t in targets]}")
    
    update_list = []
    for r in targets:
        symbol = r[0]
        logger.info(f"[SyncOfficial] Fetching yfinance info for: {symbol}")
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            pe = info.get("trailingPE") or info.get("forwardPE")
            pb = info.get("priceToBook")
            
            div_yield = info.get("dividendYield")
            if div_yield is not None:
                div_yield = round(float(div_yield) * 100, 2)
                
            roe = info.get("returnOnEquity")
            if roe is not None:
                roe = round(float(roe) * 100, 2)
                
            rev_growth = info.get("revenueGrowth")
            if rev_growth is not None:
                rev_growth = round(float(rev_growth) * 100, 2)
                
            update_body = {
                "symbol": symbol,
                "name": info.get("shortName") or info.get("longName") or r[1],
                "price": info.get("currentPrice") or info.get("previousClose") or r[2],
                "change": info.get("regularMarketChange") or r[3],
                "change_percent": info.get("regularMarketChangePercent") or r[4],
                "volume": info.get("volume") or r[5],
                "pe_ratio": pe or r[6],
                "ma5": r[7],
                "ma20": r[8],
                "stockId": r[9],
                "pb_ratio": pb,
                "dividend_yield": div_yield,
                "roe": roe,
                "revenue_growth": rev_growth
            }
            update_list.append(update_body)
            logger.info(f"[SyncOfficial] Success: {symbol} PE={pe}, PB={pb}, Yield={div_yield}%, ROE={roe}%, RevGrowth={rev_growth}%")
        except Exception as e:
            logger.error(f"[SyncOfficial] yfinance query failed for {symbol}: {e}")
            
    if update_list:
        StockMetadataDao.update_stock_metadata(update_list)
        logger.info(f"[SyncOfficial] Updated {len(update_list)} target stocks with yfinance fundamentals.")

def parse_t86_data(raw_data, is_csv, twse_map):
    try:
        if is_csv:
            import csv
            reader = csv.reader(raw_data.splitlines())
            header = None
            data_rows = []
            for r in reader:
                if not r:
                    continue
                if "證券代號" in r:
                    header = [col.strip() for col in r]
                    continue
                if header:
                    if len(r) < len(header):
                        break
                    data_rows.append([col.strip() for col in r])
        else:
            json_data = raw_data
            if json_data.get("stat") != "OK" or "data" not in json_data:
                return False
            header = json_data.get("fields", [])
            data_rows = json_data["data"]
            
        if not header:
            return False
            
        idx_sym = header.index("證券代號") if "證券代號" in header else 0
        idx_foreign_1 = -1
        idx_foreign_2 = -1
        idx_trust = -1
        idx_dealer = -1
        for idx, f in enumerate(header):
            if "外陸資買賣超股數" in f and "不含外資自營商" in f:
                idx_foreign_1 = idx
            elif "外資自營商買賣超股數" in f:
                idx_foreign_2 = idx
            elif "投信買賣超股數" in f:
                idx_trust = idx
            elif "自營商買賣超股數" in f and "自行買賣" not in f and "避險" not in f:
                idx_dealer = idx
                
        for row in data_rows:
            sym = row[idx_sym].strip().replace("=", "").replace('"', '') + ".TW"
            if sym not in twse_map:
                continue
            foreign_超1 = try_int(row[idx_foreign_1]) if idx_foreign_1 != -1 else 0
            foreign_超2 = try_int(row[idx_foreign_2]) if idx_foreign_2 != -1 else 0
            trust_超 = try_int(row[idx_trust]) if idx_trust != -1 else 0
            dealer_超 = try_int(row[idx_dealer]) if idx_dealer != -1 else 0
            
            twse_map[sym]["foreign_net_buy"] = foreign_超1 + foreign_超2
            twse_map[sym]["trust_net_buy"] = trust_超
            twse_map[sym]["dealer_net_buy"] = dealer_超
        return True
    except Exception as e:
        logger.error(f"[SyncOfficial] Parse error inside T86: {e}")
        return False

def execute_sync():
    logger.info("==================================================")
    logger.info(" STARTING OFFICIAL DATA SYNCHRONIZATION JOB")
    logger.info("==================================================")
    
    twse_map = {}
    gregorian_date = None
    
    # 1. Fetch TWSE PE/PB/Yield from OpenAPI
    logger.info("[SyncOfficial] Fetching TWSE PE/PB/Yield from OpenAPI...")
    try:
        resp = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("Code", "").strip()
                if not code:
                    continue
                sym = code + ".TW"
                
                # Get Date from the first row to determine the trading date for T86 query
                if not gregorian_date and row.get("Date"):
                    gregorian_date = parse_roc_date_to_gregorian(row.get("Date"))
                    logger.info(f"[SyncOfficial] TWSE OpenAPI returned data date: {row.get('Date')} (Gregorian: {gregorian_date})")
                
                twse_map[sym] = {
                    "pe_ratio": try_float(row.get("PEratio")),
                    "pb_ratio": try_float(row.get("PBratio")),
                    "dividend_yield": try_float(row.get("DividendYield")),
                    "foreign_net_buy": 0, "trust_net_buy": 0, "dealer_net_buy": 0,
                    "margin_balance": 0, "short_balance": 0
                }
            logger.info(f"[SyncOfficial] Successfully loaded {len(twse_map)} TWSE stocks PE/PB info from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TWSE PE/PB OpenAPI: {e}")

    # 2. Fetch TWSE T86 Institutional Trades for that specific date
    if gregorian_date:
        logger.info(f"[SyncOfficial] Fetching TWSE T86 Institutional Trades for {gregorian_date}...")
        
        success = False
        last_error = None
        
        for attempt in range(1, 4):
            is_csv = (attempt < 3)
            fmt = "csv" if is_csv else "json"
            url = f"https://www.twse.com.tw/fund/T86?response={fmt}&date={gregorian_date}&selectType=ALLBUT0999"
            
            try:
                logger.info(f"[SyncOfficial] Fetching TWSE T86 via {fmt.upper()} (Attempt {attempt}/3)...")
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    raw_data = resp.text if is_csv else resp.json()
                    if parse_t86_data(raw_data, is_csv, twse_map):
                        logger.info(f"[SyncOfficial] Successfully merged TWSE Institutional Trades from {fmt.upper()} endpoint.")
                        success = True
                        break
                    else:
                        last_error = f"Failed to parse {fmt.upper()} T86 response content"
                else:
                    last_error = f"HTTP status code: {resp.status_code}"
            except Exception as e:
                last_error = str(e)
            
            if attempt < 3:
                logger.warning(f"[SyncOfficial] T86 attempt {attempt} failed: {last_error}. Retrying in 3 seconds...")
                time.sleep(3)
        
        if not success:
            logger.error(f"[SyncOfficial] Failed to fetch TWSE T86 web endpoint after 3 attempts. Last error: {last_error}")

    # 3. Fetch TWSE Margin Balances from OpenAPI
    logger.info("[SyncOfficial] Fetching TWSE Margin Balances from OpenAPI...")
    try:
        resp = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN", headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("股票代號", "").strip()
                if not code:
                    continue
                sym = code + ".TW"
                if sym not in twse_map:
                    continue
                twse_map[sym]["margin_balance"] = try_int(row.get("融資今日餘額"))
                twse_map[sym]["short_balance"] = try_int(row.get("融券今日餘額"))
            logger.info("[SyncOfficial] Successfully merged TWSE Margin Trading from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TWSE Margin Trading OpenAPI: {e}")

    # 4. Fetch TPEx PE/PB/Yield from OpenAPI
    logger.info("[SyncOfficial] Fetching TPEx PE/PB/Yield from OpenAPI...")
    tpex_map = {}
    try:
        resp = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis", headers=HEADERS, verify=False, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("SecuritiesCompanyCode", "").strip()
                if not code:
                    continue
                sym = code + ".TWO"
                tpex_map[sym] = {
                    "pe_ratio": try_float(row.get("PriceEarningRatio")),
                    "pb_ratio": try_float(row.get("PriceBookRatio")),
                    "dividend_yield": try_float(row.get("YieldRatio")),
                    "foreign_net_buy": 0, "trust_net_buy": 0, "dealer_net_buy": 0,
                    "margin_balance": 0, "short_balance": 0
                }
            logger.info(f"[SyncOfficial] Successfully loaded {len(tpex_map)} TPEx stocks PE/PB info from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TPEx PE/PB OpenAPI: {e}")

    # 5. Fetch TPEx Institutional Investors from OpenAPI
    logger.info("[SyncOfficial] Fetching TPEx Institutional Trades from OpenAPI...")
    try:
        resp = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading", headers=HEADERS, verify=False, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("SecuritiesCompanyCode", "").strip()
                if not code:
                    continue
                sym = code + ".TWO"
                if sym not in tpex_map:
                    continue
                foreign = try_int(row.get("Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference"))
                trust = try_int(row.get("SecuritiesInvestmentTrustCompanies-Difference"))
                dealer = try_int(row.get("Dealers-Difference"))
                tpex_map[sym]["foreign_net_buy"] = foreign
                tpex_map[sym]["trust_net_buy"] = trust
                tpex_map[sym]["dealer_net_buy"] = dealer
            logger.info("[SyncOfficial] Successfully merged TPEx Institutional Trades from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TPEx Institutional Trades OpenAPI: {e}")

    # 6. Fetch TPEx Margin Balances from OpenAPI
    logger.info("[SyncOfficial] Fetching TPEx Margin Balances from OpenAPI...")
    try:
        resp = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance", headers=HEADERS, verify=False, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("SecuritiesCompanyCode", "").strip()
                if not code:
                    continue
                sym = code + ".TWO"
                if sym not in tpex_map:
                    continue
                tpex_map[sym]["margin_balance"] = try_int(row.get("MarginPurchaseBalance"))
                tpex_map[sym]["short_balance"] = try_int(row.get("ShortSaleBalance"))
            logger.info("[SyncOfficial] Successfully merged TPEx Margin Trading from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TPEx Margin Trading OpenAPI: {e}")

    # 6.1 Fetch TWSE Price/Volume from OpenAPI
    price_volume_map = {}
    logger.info("[SyncOfficial] Fetching TWSE Price and Volume from OpenAPI...")
    try:
        resp = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("Code", "").strip()
                if not code:
                    continue
                sym = code + ".TW"
                price = try_float(row.get("ClosingPrice")) or 0.0
                change = try_float(row.get("Change")) or 0.0
                volume = try_int(row.get("TradeVolume"))
                prev_close = price - change
                change_percent = (change / prev_close) * 100 if prev_close != 0 else 0.0
                
                price_volume_map[sym] = {
                    "price": price,
                    "change": change,
                    "change_percent": change_percent,
                    "volume": volume
                }
            logger.info(f"[SyncOfficial] Loaded {len(data)} TWSE price/volume records from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TWSE Price/Volume OpenAPI: {e}")

    # 6.2 Fetch TPEx Price/Volume from OpenAPI
    logger.info("[SyncOfficial] Fetching TPEx Price and Volume from OpenAPI...")
    try:
        resp = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes", headers=HEADERS, verify=False, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for row in data:
                code = row.get("SecuritiesCompanyCode", "").strip()
                if not code:
                    continue
                sym = code + ".TWO"
                price = try_float(row.get("Close")) or 0.0
                change = try_float(row.get("Change")) or 0.0
                volume = try_int(row.get("TradingShares"))
                prev_close = price - change
                change_percent = (change / prev_close) * 100 if prev_close != 0 else 0.0
                
                price_volume_map[sym] = {
                    "price": price,
                    "change": change,
                    "change_percent": change_percent,
                    "volume": volume
                }
            logger.info(f"[SyncOfficial] Loaded {len(data)} TPEx price/volume records from OpenAPI.")
    except Exception as e:
        logger.error(f"[SyncOfficial] Failed to fetch TPEx Price/Volume OpenAPI: {e}")

    # Merge TWSE and TPEx data maps
    merged_taiwan_map = {**twse_map, **tpex_map}
    logger.info(f"[SyncOfficial] Completed official OpenAPI downloads. Merged {len(merged_taiwan_map)} Taiwan stock metrics in memory.")

    # 7. Connect to database and update Taiwan stock metrics
    if merged_taiwan_map:
        if DB_TYPE == "sqlite" and not os.path.exists(DB_FILE):
            logger.error(f"[SyncOfficial] Database file not found at: {DB_FILE}")
            return
            
        conn = BaseDAO.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId FROM stock_metadata")
        rows = cursor.fetchall()
        conn.close()
        
        update_list = []
        for r in rows:
            sym = r[0]
            if sym not in merged_taiwan_map:
                continue
            metrics = merged_taiwan_map[sym]
            pv = price_volume_map.get(sym, {})
            
            update_list.append({
                "symbol": sym,
                "name": r[1],
                "price": pv.get("price") if pv.get("price") is not None and pv.get("price") != 0.0 else r[2],
                "change": pv.get("change") if pv.get("change") is not None else r[3],
                "change_percent": pv.get("change_percent") if pv.get("change_percent") is not None else r[4],
                "volume": pv.get("volume") if pv.get("volume") is not None and pv.get("volume") != 0 else r[5],
                "pe_ratio": metrics.get("pe_ratio") or r[6],
                "ma5": r[7],
                "ma20": r[8],
                "stockId": r[9],
                "pb_ratio": metrics.get("pb_ratio"),
                "dividend_yield": metrics.get("dividend_yield"),
                "foreign_net_buy": metrics.get("foreign_net_buy", 0),
                "trust_net_buy": metrics.get("trust_net_buy", 0),
                "dealer_net_buy": metrics.get("dealer_net_buy", 0),
                "margin_balance": metrics.get("margin_balance", 0),
                "short_balance": metrics.get("short_balance", 0)
            })
            
        if update_list:
            StockMetadataDao.update_stock_metadata(update_list)
            logger.info(f"[SyncOfficial] Successfully synchronized {len(update_list)} Taiwan stocks with official TWSE/TPEx Open Data.")

    # 8. Enrich with yfinance top 50 volume and US stocks
    try:
        sync_yfinance_top_50()
    except Exception as e:
        logger.error(f"[SyncOfficial] yfinance top 50 enrichment failed: {e}")

    logger.info("==================================================")
    logger.info(" OFFICIAL DATA SYNCHRONIZATION JOB COMPLETED")
    logger.info("==================================================")

if __name__ == "__main__":
    execute_sync()
