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
    """Parses the Excel file, maps raw codes to database symbols, clears old watchlist, and saves the new list with characteristics.

    Returns the list of mapped database symbols.
    """
    # Step 1: Parse Excel using Pandas
    try:
        if file_path.endswith(".xls"):
            df = pd.read_excel(file_path, engine="xlrd", engine_kwargs={"ignore_workbook_corruption": True})
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        logger.error(f"[SyncAce] Failed to parse Excel file: {e}")
        raise e

    # Determine ID column
    id_col = None
    if "股票代號" in df.columns:
        id_col = "股票代號"
    elif "股號" in df.columns:
        id_col = "股號"
    else:
        id_col = df.columns[0]

    # Clean and extract symbols along with characteristics from D, E, F, G, H columns (indices 3, 4, 5, 6, 7)
    # Check if df has at least 8 columns to parse characteristics
    has_extra_cols = df.shape[1] >= 8
    
    feature_map = {}
    for i in range(len(df)):
        raw_code = str(df.iloc[i, 0]).strip().split(".")[0]
        if not raw_code or raw_code.lower() == "nan":
            continue
        
        strength_dna = str(df.iloc[i, 3]).strip() if has_extra_cols and pd.notna(df.iloc[i, 3]) else None
        hint_double = str(df.iloc[i, 4]).strip() if has_extra_cols and pd.notna(df.iloc[i, 4]) else None
        magic_band = str(df.iloc[i, 5]).strip() if has_extra_cols and pd.notna(df.iloc[i, 5]) else None
        short_sniper = str(df.iloc[i, 6]).strip() if has_extra_cols and pd.notna(df.iloc[i, 6]) else None
        rebound_sprint = str(df.iloc[i, 7]).strip() if has_extra_cols and pd.notna(df.iloc[i, 7]) else None
        
        # Clean up empty strings or "nan"
        if strength_dna == "nan" or not strength_dna: strength_dna = None
        if hint_double == "nan" or not hint_double: hint_double = None
        if magic_band == "nan" or not magic_band: magic_band = None
        if short_sniper == "nan" or not short_sniper: short_sniper = None
        if rebound_sprint == "nan" or not rebound_sprint: rebound_sprint = None
        
        feature_map[raw_code] = (strength_dna, hint_double, magic_band, short_sniper, rebound_sprint)

    raw_symbols = list(feature_map.keys())

    if not raw_symbols:
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
    db_rows = []
    db_symbols = []
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    create_time = datetime.datetime.now()
    
    # Track symbols to avoid duplicate inserts
    seen_symbols = set()
    
    for r in rows:
        sym = r["symbol"]
        stock_id = r["stockId"]
        
        code = sym.split(".")[0]
        matched_code = None
        if code in feature_map:
            matched_code = code
        elif str(stock_id) in feature_map:
            matched_code = str(stock_id)
            
        if matched_code and sym not in seen_symbols:
            seen_symbols.add(sym)
            db_symbols.append(sym)
            feat = feature_map[matched_code]
            # row tuple: (symbol, update_date, strength_dna, hint_double, magic_band, short_sniper, rebound_sprint, create_date)
            db_rows.append((sym, today_str, feat[0], feat[1], feat[2], feat[3], feat[4], create_time))

    logger.info(f"[SyncAce] Mapped {len(db_symbols)} database symbols: {db_symbols}")

    if not db_symbols:
        logger.warning("[SyncAce] No matching symbols found in stock_metadata database.")
        conn.close()
        return []

    # Step 3: Update the Database
    try:
        # Clear the old watchlist and write the new mapped symbols with features
        AceWatchlistDao.clear_watchlist(conn=conn)
        AceWatchlistDao.add_symbols_to_watchlist(db_rows, conn=conn)
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
    
    file_path_xlsx = os.path.join(downloads_dir, f"ace_selection_{today_str}.xlsx")
    file_path_xls = os.path.join(downloads_dir, f"ace_selection_{today_str}.xls")
    
    file_path = None
    if os.path.exists(file_path_xlsx):
        file_path = file_path_xlsx
    elif os.path.exists(file_path_xls):
        file_path = file_path_xls

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
    if file_path:
        logger.info(f"[SyncAce] Today's Excel already downloaded at: {file_path}. Skipping download.")
    else:
        # Step 2: Download Excel (Mock or Live)
        if not wearn_excel_url or not wearn_cookies:
            logger.warning("[SyncAce] WEARN_EXCEL_URL or WEARN_COOKIES not configured. Running in MOCK MODE.")
            # Generate a mock Excel file for testing
            mock_data = {
                "股票代號": ["2330", "2317", "2454", "2603", "3231", "2609", "2002", "2881", "2882"],
                "股票名稱": ["台積電", "鴻海", "聯發科", "長榮", "緯創", "陽明", "中鋼", "富邦金", "國泰金"],
                "無用欄位1": ["", "", "", "", "", "", "", "", ""],
                "強勢股DNA": ["強勢_5,位階_1,籌碼_5,成交_5,吃貨_5", "強勢_4,位階_2,籌碼_4,成交_4", "", "強勢_5", "", "強勢_4", "", "強勢_5", "強勢_4"],
                "打暗號倍數股": ["", "", "強勢_3", "", "", "", "", "", ""],
                "法師型波段股": ["強勢_5,位階_1,籌碼_5,成交_5,吃貨_5", "", "", "", "強勢_2", "", "強勢_3", "", ""],
                "空方股狙擊手": ["", "", "", "強勢_5", "", "強勢_4", "", "強勢_5", ""],
                "搶反彈短跑股": ["", "", "", "", "", "", "", "", ""]
            }
            df_mock = pd.DataFrame(mock_data)
            df_mock.to_excel(file_path_xlsx, index=False)
            file_path = file_path_xlsx
            logger.info(f"[SyncAce] Generated Mock Excel file at: {file_path}")
        else:
            # Determine download file extension (.xlsx or .xls)
            ext = ".xls"
            if ".xlsx" in wearn_excel_url.lower():
                ext = ".xlsx"
            file_path = os.path.join(downloads_dir, f"ace_selection_{today_str}{ext}")
            
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
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[SyncAce] Cleaned up invalid/corrupted file: {file_path}")
            except Exception as clean_err:
                logger.warning(f"[SyncAce] Failed to clean up file: {clean_err}")

    logger.info("==================================================")
    logger.info(" 艾斯選股 (ACE) SYNCHRONIZATION JOB COMPLETED")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
