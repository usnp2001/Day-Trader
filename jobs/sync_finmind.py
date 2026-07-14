import sys
import os
import datetime
import requests
import yfinance as yf

# Add parent directory to sys.path to resolve backend package imports
if os.path.exists("/app/dal"):
    backend_dir = "/app"
else:
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dal.stock_metadata_dao import StockMetadataDao
from common.logger import logger
from common.config import FINMIND_TOKEN, DB_TYPE, DB_FILE
from common.base_dao import BaseDAO, OperationalError, DatabaseError

def fetch_finmind_daily_bulk(dataset: str, token: str, days_back: int = 10) -> list:
    """Fetches bulk daily market records from FinMind by scanning dates backwards from today."""
    url = "https://api.finmindtrade.com/api/v4/data"
    today = datetime.date.today()
    
    for i in range(days_back):
        check_date = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        logger.info(f"[SyncJob] Scanning date '{check_date}' for Taiwan dataset: {dataset}")
        
        params = {
            "dataset": dataset,
            "start_date": check_date,
            "end_date": check_date,
            "token": token
        }
        
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    logger.info(f"[SyncJob] Success: Loaded {len(data)} records for {dataset} on {check_date}")
                    return data
            else:
                logger.warning(f"[SyncJob] Scan for {check_date} failed (Status {resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"[SyncJob] Request error for {check_date} (dataset {dataset}): {e}")
            
    logger.error(f"[SyncJob] Could not find any daily records for {dataset} in the past {days_back} days.")
    return []

def fetch_finmind_monthly_revenue(token: str) -> list:
    """Fetches bulk monthly revenue records for the past 45 days."""
    url = "https://api.finmindtrade.com/api/v4/data"
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=45)).strftime("%Y-%m-%d")
    
    logger.info(f"[SyncJob] Loading monthly revenue reports starting from: {start_date}")
    params = {
        "dataset": "TaiwanStockMonthRevenue",
        "start_date": start_date,
        "token": token
    }
    
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            logger.info(f"[SyncJob] Success: Loaded {len(data)} monthly revenue records.")
            return data
        else:
            logger.warning(f"[SyncJob] Month revenue fetch failed (Status {resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"[SyncJob] Month revenue request error: {e}")
    return []

def sync_finmind_taiwan_bulk():
    """Bulk syncs Taiwan stocks metadata using FinMind to minimize HTTP request counts."""
    logger.info("[SyncJob] --- Starting Bulk FinMind Scan for Taiwan Market ---")
    
    # 1. Fetch PER/PBR/Yield daily data
    logger.info("[SyncJob] Step 1: Downloading PE/PB/Yield indicators...")
    per_data = fetch_finmind_daily_bulk("TaiwanStockPER", FINMIND_TOKEN)
    per_map = {}
    for row in per_data:
        stock_id = row.get("stock_id")
        if stock_id:
            per_map[stock_id] = {
                "pe_ratio": row.get("PER"),
                "pb_ratio": row.get("PBR"),
                "dividend_yield": row.get("dividend_yield")
            }

    # 2. Fetch Institutional trading daily data
    logger.info("[SyncJob] Step 2: Downloading institutional net trade buy/sell...")
    inst_data = fetch_finmind_daily_bulk("TaiwanStockInstitutionalInvestorsBuySell", FINMIND_TOKEN)
    inst_map = {}
    for row in inst_data:
        stock_id = row.get("stock_id")
        if not stock_id:
            continue
        if stock_id not in inst_map:
            inst_map[stock_id] = {"foreign_net_buy": 0, "trust_net_buy": 0, "dealer_net_buy": 0}
            
        name = row.get("name", "")
        diff = int(row.get("diff", 0))
        
        if "Foreign" in name or "外資" in name or "外陸資" in name:
            inst_map[stock_id]["foreign_net_buy"] += diff
        elif "Trust" in name or "投信" in name:
            inst_map[stock_id]["trust_net_buy"] += diff
        elif "Dealer" in name or "自營商" in name:
            inst_map[stock_id]["dealer_net_buy"] += diff

    # 3. Fetch Margin trading daily data
    logger.info("[SyncJob] Step 3: Downloading margin purchase and short sale balances...")
    margin_data = fetch_finmind_daily_bulk("TaiwanStockMarginPurchaseShortSale", FINMIND_TOKEN)
    margin_map = {}
    for row in margin_data:
        stock_id = row.get("stock_id")
        if stock_id:
            margin_map[stock_id] = {
                "margin_balance": int(row.get("MarginPurchaseTodayBalance", 0)),
                "short_balance": int(row.get("ShortSaleTodayBalance", 0))
            }

    # 4. Fetch Monthly revenue growth data
    logger.info("[SyncJob] Step 4: Downloading monthly revenue reports...")
    revenue_data = fetch_finmind_monthly_revenue(FINMIND_TOKEN)
    revenue_map = {}
    for row in revenue_data:
        stock_id = row.get("stock_id")
        if not stock_id:
            continue
        date_str = row.get("date", "")
        yoy = row.get("revenue_year_growth_rate")
        
        if stock_id not in revenue_map or date_str > revenue_map[stock_id]["date"]:
            revenue_map[stock_id] = {
                "date": date_str,
                "revenue_yoy": yoy
            }

    # 5. Connect and update SQLite cache
    logger.info("[SyncJob] Step 5: Connecting to database and saving Taiwan updates...")
    if DB_TYPE == "sqlite" and not os.path.exists(DB_FILE):
        logger.error(f"[SyncJob] Database file not found at: {DB_FILE}")
        return
        
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId FROM stock_metadata")
    rows = cursor.fetchall()
    conn.close()
    
    update_list = []
    for r in rows:
        sym = r[0]
        if not (sym.endswith(".TW") or sym.endswith(".TWO")):
            continue
        stock_id = sym.split(".")[0]
        
        pe_info = per_map.get(stock_id, {})
        inst_info = inst_map.get(stock_id, {})
        margin_info = margin_map.get(stock_id, {})
        rev_info = revenue_map.get(stock_id, {})
        
        # Skip if no updates found for this stock
        if not (pe_info or inst_info or margin_info or rev_info):
            continue
            
        update_list.append({
            "symbol": sym,
            "name": r[1],
            "price": r[2],
            "change": r[3],
            "change_percent": r[4],
            "volume": r[5],
            "pe_ratio": pe_info.get("pe_ratio") or r[6],
            "ma5": r[7],
            "ma20": r[8],
            "stockId": r[9],
            "pb_ratio": pe_info.get("pb_ratio"),
            "dividend_yield": pe_info.get("dividend_yield"),
            "foreign_net_buy": inst_info.get("foreign_net_buy", 0),
            "trust_net_buy": inst_info.get("trust_net_buy", 0),
            "dealer_net_buy": inst_info.get("dealer_net_buy", 0),
            "margin_balance": margin_info.get("margin_balance", 0),
            "short_balance": margin_info.get("short_balance", 0),
            "revenue_yoy": rev_info.get("revenue_yoy")
        })
        
    if update_list:
        StockMetadataDao.update_stock_metadata(update_list)
        logger.info(f"[SyncJob] Bulk updated {len(update_list)} Taiwan stocks in SQLite database.")


def sync_global_yfinance():
    """
    Syncs US stocks and prioritized top 50 volume stocks detailed indicators (ROE, Revenue Growth) 
    using yfinance to offload FinMind API usage.
    """
    logger.info("[SyncJob] --- Starting prioritized yfinance fundamental metrics scan ---")
    if DB_TYPE == "sqlite" and not os.path.exists(DB_FILE):
        logger.error(f"[SyncJob] Database file not found at: {DB_FILE}")
        return
        
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId FROM stock_metadata")
    rows = cursor.fetchall()
    conn.close()
    
    # Sort all stocks by volume descending to find top 50 volume stocks
    sorted_by_volume = sorted(rows, key=lambda x: x[5] or 0, reverse=True)
    top_50_volume = sorted_by_volume[:50]
    
    # Gather all US stocks (which must be updated since yfinance is their only source)
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
            
    logger.info(f"[SyncJob] Target list for yfinance info sync (top 50 volume prioritized + US fallback, total {len(targets)}): {[t[0] for t in targets]}")
    
    update_list = []
    for r in targets:
        symbol = r[0]
        logger.info(f"[SyncJob] Fetching yfinance info for: {symbol}")
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Fetch indicators
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
                
            # Construct update body (merging existing price/volume if yfinance has none)
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
            logger.info(f"[SyncJob] Success: {symbol} PE={pe}, PB={pb}, Yield={div_yield}%, ROE={roe}%, RevGrowth={rev_growth}%")
        except Exception as e:
            logger.error(f"[SyncJob] yfinance query failed for {symbol}: {e}")
            
    if update_list:
        StockMetadataDao.update_stock_metadata(update_list)
        logger.info(f"[SyncJob] Updated {len(update_list)} target stocks with yfinance fundamentals.")


def migrate_database_columns():
    """Ensures all expanded and premium columns exist in the schema before updating."""
    if DB_TYPE == "sqlite" and not os.path.exists(DB_FILE):
        logger.error(f"[SyncJob] Database file not found at: {DB_FILE}")
        return
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    new_columns = [
        ("pb_ratio", "REAL"),
        ("dividend_yield", "REAL"),
        ("foreign_net_buy", "INTEGER"),
        ("trust_net_buy", "INTEGER"),
        ("dealer_net_buy", "INTEGER"),
        ("margin_balance", "INTEGER"),
        ("short_balance", "INTEGER"),
        ("revenue_yoy", "REAL"),
        ("roe", "REAL"),
        ("revenue_growth", "REAL")
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE stock_metadata ADD COLUMN {col_name} {col_type}")
            conn.commit()
            logger.info(f"[SyncJob] Dynamic migration added column: {col_name}")
        except DatabaseError:
            try:
                conn.rollback()
            except Exception:
                pass
    conn.close()

def execute_sync():
    logger.info("==================================================")
    logger.info(" STARTING FINMIND METADATA SYNCHRONIZATION JOB")
    logger.info("==================================================")
    
    # 0. Ensure schema is fully migrated
    migrate_database_columns()
    
    # 1. Run FinMind bulk scan for Taiwan stocks (evaluates PER, PB, Yield, Margin, Corporations)
    try:
        sync_finmind_taiwan_bulk()
    except Exception as e:
        logger.error(f"[SyncJob] Critical error in Taiwan FinMind bulk sync: {e}")
        
    # 2. Run prioritized yfinance scan for top 50 volume stocks and US stocks
    try:
        sync_global_yfinance()
    except Exception as e:
        logger.error(f"[SyncJob] Critical error in yfinance fundamental sync: {e}")
        
    logger.info("==================================================")
    logger.info(" FINMIND SYNCHRONIZATION JOB FINISHED SUCCESSFULLY")
    logger.info("==================================================")

if __name__ == "__main__":
    execute_sync()
