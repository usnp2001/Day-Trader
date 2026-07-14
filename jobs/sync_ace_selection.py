import sys
import os
import datetime
import requests
import pandas as pd

# Add parent directory to sys.path to resolve backend package imports
if os.path.exists("/app/dal"):
    backend_dir = "/app"
else:
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dal.ace_watchlist_dao import AceWatchlistDao
from dal.system_config_dao import SystemConfigDao
from common.logger import logger
from common.config import DB_TYPE, DB_FILE
from common.base_dao import BaseDAO, DatabaseError

def process_excel_file(file_path: str) -> list:
    """Parses the Excel file, maps raw codes to database symbols, clears old watchlist, and saves the new list.

    Returns the list of mapped database symbols.
    """
    # Step 1: Parse Excel using Pandas
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        logger.error(f"[SyncAce] Failed to parse Excel file: {e}")
        raise e

    # Validate Excel headers
    if "股票代號" not in df.columns:
        logger.error("[SyncAce] Invalid Excel format: '股票代號' column not found.")
        raise ValueError("Invalid Excel format: '股票代號' column not found.")

    # Clean and extract symbols
    raw_symbols = df["股票代號"].astype(str).tolist()
    symbols = []
    for sym in raw_symbols:
        sym = sym.strip().split(".")[0]  # Remove decimals or suffixes if any
        if sym:
            symbols.append(sym)

    if not symbols:
        logger.warning("[SyncAce] No valid stock symbols found in Excel.")
        return []

    # Step 2: Map raw codes to exact database symbols
    logger.info("[SyncAce] Mapping raw numeric codes to database symbols...")
    conn = BaseDAO.get_connection()
    
    try:
        rows = conn.execute("SELECT symbol, stockId FROM stock_metadata").fetchall()
    except Exception as e:
        logger.error(f"[SyncAce] Database query failed: {e}")
        conn.close()
        raise e

    # Map in Python (handles TW/TWO suffixes seamlessly)
    db_symbols = []
    symbol_set = set(symbols)
    symbol_int_set = {int(s) for s in symbols if s.isdigit()}
    
    for r in rows:
        sym = r["symbol"]
        stock_id = r["stockId"]
        
        # Check by symbol code (like "2330.TW" starts with "2330")
        code = sym.split(".")[0]
        if code in symbol_set or stock_id in symbol_int_set:
            db_symbols.append(sym)

    logger.info(f"[SyncAce] Mapped {len(db_symbols)} database symbols: {db_symbols}")

    if not db_symbols:
        logger.warning("[SyncAce] No matching symbols found in stock_metadata database.")
        conn.close()
        return []

    # Step 3: Update the Database
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    try:
        # Clear the old watchlist and write the new mapped symbols
        AceWatchlistDao.clear_watchlist(conn=conn)
        AceWatchlistDao.add_symbols_to_watchlist(db_symbols, today_str, conn=conn)
        logger.info(f"[SyncAce] Successfully updated database ace_watchlist with {len(db_symbols)} stocks.")
    except Exception as e:
        logger.error(f"[SyncAce] Database transaction failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        conn.close()

    return db_symbols

def main():
    logger.info("==================================================")
    logger.info(" STARTING 艾斯選股 (ACE) SYNCHRONIZATION JOB")
    logger.info("==================================================")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "downloads"))
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, f"ace_selection_{today_str}.xlsx")

    # Read config variables (Check database first, fallback to environment)
    wearn_excel_url = None
    wearn_cookies = None
    try:
        wearn_excel_url = SystemConfigDao.get_config("wearn_excel_url")
        wearn_cookies = SystemConfigDao.get_config("wearn_cookies")
    except Exception as e:
        logger.warning(f"[SyncAce] Failed to read config from database: {e}")

    if not wearn_excel_url:
        wearn_excel_url = os.getenv("WEARN_EXCEL_URL")
    if not wearn_cookies:
        wearn_cookies = os.getenv("WEARN_COOKIES")

    # Step 1: Check if today's file already exists
    if os.path.exists(file_path):
        logger.info(f"[SyncAce] Today's Excel already downloaded at: {file_path}. Skipping download.")
    else:
        # Step 2: Download Excel (Mock or Live)
        if not wearn_excel_url or not wearn_cookies:
            logger.warning("[SyncAce] WEARN_EXCEL_URL or WEARN_COOKIES not configured. Running in MOCK MODE.")
            # Generate a mock Excel file for testing
            mock_data = {
                "股票代號": ["2330", "2317", "2454", "2603", "3231", "2609", "2002", "2881", "2882"],
                "股票名稱": ["台積電", "鴻海", "聯發科", "長榮", "緯創", "陽明", "中鋼", "富邦金", "國泰金"]
            }
            df_mock = pd.DataFrame(mock_data)
            df_mock.to_excel(file_path, index=False)
            logger.info(f"[SyncAce] Generated Mock Excel file at: {file_path}")
        else:
            logger.info(f"[SyncAce] Downloading Excel from Wearn: {wearn_excel_url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Cookie": wearn_cookies
            }
            try:
                response = requests.get(wearn_excel_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    logger.info(f"[SyncAce] Successfully downloaded Excel to: {file_path}")
                else:
                    logger.error(f"[SyncAce] Failed to download Excel. Status Code: {response.status_code}")
                    return
            except Exception as e:
                logger.error(f"[SyncAce] HTTP Request failed: {e}")
                return

    # Step 3: Process Excel and update DB
    try:
        process_excel_file(file_path)
    except Exception as e:
        logger.error(f"[SyncAce] Job failed during Excel processing: {e}")

    logger.info("==================================================")
    logger.info(" 艾斯選股 (ACE) SYNCHRONIZATION JOB COMPLETED")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
