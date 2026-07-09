import sys
import os
import requests
import datetime
import time

# Add backend folder and parent folder to sys.path to enable imports on both host and docker container
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dal.stock_metadata_dao import StockMetadataDao
from common.base_dao import BaseDAO
from crawler import DEFAULT_SYMBOLS
from common.logger import logger

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidXNucDIwMDEiLCJlbWFpbCI6InVzbnAyMDAxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.Vc5ppWVBZqusn0DXwjM0Ut4ZLnCBFWGusRnBJ9zI00A"

def fetch_finmind_dataset(dataset_name: str, stock_id: str, start_date: str) -> list:
    """Helper to query a FinMind dataset for a given stock ID starting from a date."""
    # Add a polite delay of 0.5 seconds between API requests to control query frequency
    time.sleep(0.5)
    params = {
        "dataset": dataset_name,
        "data_id": stock_id,
        "start_date": start_date,
        "token": TOKEN
    }
    try:
        resp = requests.get(FINMIND_URL, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        elif resp.status_code in [400, 402]:
            raise PermissionError(f"API quota exceeded or permission level restricted (Status {resp.status_code})")
        else:
            logger.error(f"[FinMind Sync] Dataset {dataset_name} for stock {stock_id} returned status {resp.status_code}: {resp.text}")
    except PermissionError as pe:
        raise pe
    except Exception as e:
        logger.error(f"[FinMind Sync] Error fetching dataset {dataset_name} for stock {stock_id}: {e}")
    return []

def main():
    logger.info("[FinMind Sync] Starting background stock metadata synchronization...")
    
    # 1. Retrieve all stock symbols from local database
    conn = BaseDAO.get_connection()
    rows = conn.execute("SELECT symbol, name FROM stock_metadata").fetchall()
    conn.close()
    
    tw_stocks = []
    for row in rows:
        symbol = row["symbol"]
        # Sync all Taiwan stocks from database
        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            tw_stocks.append({
                "symbol": symbol,
                "name": row["name"],
                "stock_id": symbol.split(".")[0]
            })
            
    logger.info(f"[FinMind Sync] Found {len(tw_stocks)} Taiwan watchlist stocks to update.")
    
    today = datetime.date.today()
    # Query datasets for the last 15 days to guarantee we get the latest trading days' data
    recent_start_date = (today - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
    # Monthly revenue needs 14 months to calculate YoY
    revenue_start_date = (today - datetime.timedelta(days=450)).strftime("%Y-%m-%d")
    
    success_count = 0
    for stock in tw_stocks:
        symbol = stock["symbol"]
        stock_id = stock["stock_id"]
        name = stock["name"]
        
        logger.info(f"[FinMind Sync] Syncing data for {name} ({symbol})...")
        
        updates = {
            "symbol": symbol,
            "name": name
        }
        
        try:
            # A. Fetch PER/PBR & Dividend Yield
            per_data = fetch_finmind_dataset("TaiwanStockPER", stock_id, recent_start_date)
            if per_data:
                # Get latest record
                latest_per = per_data[-1]
                updates["pb_ratio"] = latest_per.get("PBR")
                updates["dividend_yield"] = latest_per.get("dividend_yield")
                
            # B. Fetch Institutional Investors Net Buy
            inst_data = fetch_finmind_dataset("TaiwanStockInstitutionalInvestorsBuySellWide", stock_id, recent_start_date)
            if inst_data:
                latest_inst = inst_data[-1]
                foreign_buy = latest_inst.get("Foreign_Investor_buy", 0)
                foreign_sell = latest_inst.get("Foreign_Investor_sell", 0)
                updates["foreign_net_buy"] = foreign_buy - foreign_sell
                
                trust_buy = latest_inst.get("Investment_Trust_buy", 0)
                trust_sell = latest_inst.get("Investment_Trust_sell", 0)
                updates["trust_net_buy"] = trust_buy - trust_sell
                
                # Dealer total is self + hedging + any general dealer transaction
                dealer_buy = latest_inst.get("Dealer_buy", 0) + latest_inst.get("Dealer_self_buy", 0) + latest_inst.get("Dealer_Hedging_buy", 0)
                dealer_sell = latest_inst.get("Dealer_sell", 0) + latest_inst.get("Dealer_self_sell", 0) + latest_inst.get("Dealer_Hedging_sell", 0)
                updates["dealer_net_buy"] = dealer_buy - dealer_sell
                
            # C. Fetch Margin & Short Balance
            margin_data = fetch_finmind_dataset("TaiwanStockMarginPurchaseShortSale", stock_id, recent_start_date)
            if margin_data:
                latest_margin = margin_data[-1]
                updates["margin_balance"] = latest_margin.get("MarginPurchaseTodayBalance")
                updates["short_balance"] = latest_margin.get("ShortSaleTodayBalance")
                
            # D. Fetch Monthly Revenue & Calculate YoY
            rev_data = fetch_finmind_dataset("TaiwanStockMonthRevenue", stock_id, revenue_start_date)
            if len(rev_data) >= 13:
                # Sort chronologically
                rev_sorted = sorted(rev_data, key=lambda x: x["date"])
                latest_rev_rec = rev_sorted[-1]
                latest_rev = latest_rev_rec["revenue"]
                latest_month = latest_rev_rec["revenue_month"]
                latest_year = latest_rev_rec["revenue_year"]
                
                target_year = latest_year - 1
                target_month = latest_month
                
                prev_rev = None
                for rec in rev_sorted:
                    if rec["revenue_year"] == target_year and rec["revenue_month"] == target_month:
                        prev_rev = rec["revenue"]
                        break
                        
                if prev_rev and prev_rev > 0:
                    updates["revenue_yoy"] = ((latest_rev - prev_rev) / prev_rev) * 100
                    
            # Write updates back to database
            StockMetadataDao.update_stock_metadata([updates])
            success_count += 1
            logger.info(f"[FinMind Sync] Successfully updated {symbol}: "
                        f"PBR={updates.get('pb_ratio')}, Yield={updates.get('dividend_yield')}%, "
                        f"ForeignNet={updates.get('foreign_net_buy')}, TrustNet={updates.get('trust_net_buy')}, "
                        f"MarginBal={updates.get('margin_balance')}, ShortBal={updates.get('short_balance')}, "
                        f"RevYoY={updates.get('revenue_yoy')}%")
        except PermissionError as pe:
            logger.warning(f"[FinMind Sync] Sync stopped due to API limitations: {pe}")
            logger.warning("[FinMind Sync] If using a free 'Register' level token, you can only sync up to 150 stocks per hour. Please upgrade your token or wait for the hourly reset.")
            break
        except Exception as db_err:
            logger.error(f"[FinMind Sync] Failed to write updates for {symbol} to database: {db_err}")
            
    logger.info(f"[FinMind Sync] Job completed. Successfully synchronized {success_count}/{len(tw_stocks)} Taiwan stocks.")

if __name__ == "__main__":
    main()
