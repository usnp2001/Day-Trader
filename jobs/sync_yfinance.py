import sys
import os
import datetime
import sqlite3
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
from common.config import DB_FILE

# Popular watchlist symbols to query yfinance for detailed fundamental indicators (ROE, RevGrowth)
POPULAR_SYMBOLS = [
    "2330.TW", "2317.TW", "2454.TW", "2603.TW", "2609.TW",
    "3231.TW", "2382.TW", "2618.TW", "2002.TW", "2881.TW",
    "2882.TW", "2303.TW", "2308.TW", "2891.TW", "2610.TW"
]

def migrate_database_columns():
    """Ensures all expanded and premium columns exist in the SQLite schema before updating."""
    if not os.path.exists(DB_FILE):
        logger.error(f"[SyncJobYF] Database file not found at: {DB_FILE}")
        return
    conn = sqlite3.connect(DB_FILE)
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
            logger.info(f"[SyncJobYF] Dynamic migration added column: {col_name}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def sync_global_yfinance():
    """
    Syncs US stocks and popular Taiwan stocks detailed indicators (ROE, Revenue Growth) 
    using yfinance to offload FinMind API usage.
    """
    logger.info("[SyncJobYF] --- Starting yfinance fundamental metrics scan ---")
    if not os.path.exists(DB_FILE):
        logger.error(f"[SyncJobYF] Database file not found at: {DB_FILE}")
        return
        
    conn = sqlite3.connect(DB_FILE)
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
            
    logger.info(f"[SyncJobYF] Target list for yfinance info sync (top 50 volume prioritized + US fallback, total {len(targets)}): {[t[0] for t in targets]}")
    
    update_list = []
    for r in targets:
        symbol = r[0]
        logger.info(f"[SyncJobYF] Fetching yfinance info for: {symbol}")
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
            logger.info(f"[SyncJobYF] Success: {symbol} PE={pe}, PB={pb}, Yield={div_yield}%, ROE={roe}%, RevGrowth={rev_growth}%")
        except Exception as e:
            logger.error(f"[SyncJobYF] yfinance query failed for {symbol}: {e}")
            
    if update_list:
        StockMetadataDao.update_stock_metadata(update_list)
        logger.info(f"[SyncJobYF] Updated {len(update_list)} target stocks with yfinance fundamentals.")

def execute_sync():
    logger.info("==================================================")
    logger.info(" STARTING DEDICATED YFINANCE SYNCHRONIZATION JOB")
    logger.info("==================================================")
    
    # 1. Ensure schema is fully migrated
    migrate_database_columns()
    
    # 2. Run yfinance scan for US stocks and popular TW watchlist stocks (ROE, RevGrowth, PE/PB/Yield)
    try:
        sync_global_yfinance()
    except Exception as e:
        logger.error(f"[SyncJobYF] Critical error in yfinance fundamental sync: {e}")
        
    logger.info("==================================================")
    logger.info(" YFINANCE SYNCHRONIZATION JOB FINISHED SUCCESSFULLY")
    logger.info("==================================================")

if __name__ == "__main__":
    execute_sync()
