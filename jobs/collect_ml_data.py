import sys
import os
import sqlite3
import requests
import datetime
import time
import pandas as pd
import numpy as np
import yfinance as yf

# Adjust path to import backend models and tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import DB_FILE
from common.logger import logger
from common.base_dao import BaseDAO

# FinMind API Configuration
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2Vy_idIjoidXNucDIwMDEiLCJlbWFpbCI6InVzbnAyMDAxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.Vc5ppWVBZqusn0DXwjM0Ut4ZLnCBFWGusRnBJ9zI00A"

# Track API failures globally for fallback triggering
consecutive_errors = 0

def fetch_finmind_stock_history(dataset: str, stock_id: str, start_date: str, end_date: str) -> list:
    """Fetches a full year dataset from FinMind for a specific stock ID."""
    global consecutive_errors
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
        "token": TOKEN
    }
    try:
        resp = requests.get(FINMIND_URL, params=params, timeout=15)
        if resp.status_code == 200:
            consecutive_errors = 0 # reset on success
            return resp.json().get("data", [])
        elif resp.status_code in [400, 402]:
            consecutive_errors += 1
            logger.error(f"[Collector] FinMind {dataset} for {stock_id} returned {resp.status_code} (Limit/Level error).")
        else:
            logger.error(f"[Collector] FinMind {dataset} for {stock_id} returned status {resp.status_code}")
    except Exception as e:
        consecutive_errors += 1
        logger.error(f"[Collector] Error fetching FinMind {dataset} for {stock_id}: {e}")
    return []

def main():
    global consecutive_errors
    logger.info("[Collector] Starting ML dataset collection job...")
    
    # 1. Fetch top 150 most active Taiwan symbols sorted by volume descending to comply with FinMind API limits
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name FROM stock_metadata 
        WHERE symbol LIKE '%.TW' OR symbol LIKE '%.TWO' 
        ORDER BY volume DESC 
        LIMIT 150
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        logger.error("[Collector] No symbols found in database!")
        return
        
    symbol_map = {row[0]: row[1] for row in rows}
    symbols = list(symbol_map.keys())
    logger.info(f"[Collector] Selected top {len(symbols)} most liquid Taiwan stocks to download.")
    
    # 2. Download K-Line data using yfinance (auto_adjust=True for ex-dividend)
    logger.info("[Collector] Downloading 1 year adjusted K-Line data from yfinance...")
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=380) # Slightly more for MA calculation warmup
    
    try:
        raw_kf = yf.download(symbols, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by='ticker', auto_adjust=True)
    except Exception as e:
        logger.error(f"[Collector] yfinance bulk download failed: {e}")
        return

    kline_records = []
    logger.info("[Collector] Processing and unstacking yfinance data...")
    for sym in symbols:
        if sym not in raw_kf.columns.levels[0]:
            continue
        sym_df = raw_kf[sym].dropna(subset=['Close']).copy()
        sym_df = sym_df.reset_index()
        for _, r in sym_df.iterrows():
            kline_records.append({
                "symbol": sym,
                "date": r['Date'].strftime("%Y-%m-%d"),
                "open": float(r['Open']),
                "high": float(r['High']),
                "low": float(r['Low']),
                "close": float(r['Close']),
                "volume": int(r['Volume'])
            })
            
    df_kline = pd.DataFrame(kline_records)
    if df_kline.empty:
        logger.error("[Collector] No K-line records downloaded!")
        return
        
    logger.info(f"[Collector] Downloaded {len(df_kline)} K-line records.")
    
    # 3. Download Institutional Flows & Margin Stock-by-Stock from FinMind
    logger.info(f"[Collector] Querying FinMind for {len(symbols)} stocks over 1-year history...")
    
    inst_records = []
    margin_records = []
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    skip_finmind = False
    
    for idx, sym in enumerate(symbols):
        stock_id = sym.split(".")[0]
        name = symbol_map[sym]
        
        # Check if fallback mode is triggered (after 6 consecutive errors, which implies quota locked or restricted)
        if consecutive_errors >= 6 and not skip_finmind:
            skip_finmind = True
            logger.warning("="*80)
            logger.warning("[Collector] WARNING: Consecutive FinMind API errors detected!")
            logger.warning("[Collector] Enabling GRACEFUL FALLBACK MODE to skip API calls and prevent waiting.")
            logger.warning("[Collector] Generating dataset using K-Line prices & Technical Indicators (KD, MACD, RSI) only.")
            logger.warning("="*80)
            
        if skip_finmind:
            # Inject empty/zero placeholders for chip columns
            inst_records.append({
                "symbol": sym,
                "date": start_str, # placeholder key
                "foreign_net_buy": 0,
                "trust_net_buy": 0,
                "dealer_net_buy": 0
            })
            margin_records.append({
                "symbol": sym,
                "date": start_str,
                "margin_balance": 0,
                "short_balance": 0
            })
            continue
            
        logger.info(f"   [{idx+1}/{len(symbols)}] Fetching FinMind chips for {name} ({sym})...")
        
        # A. Fetch Institutional Flows for the entire year
        inst_data = fetch_finmind_stock_history("TaiwanStockInstitutionalInvestorsBuySellWide", stock_id, start_str, end_str)
        for row in inst_data:
            f_buy = row.get("Foreign_Investor_buy", 0) - row.get("Foreign_Investor_sell", 0)
            t_buy = row.get("Investment_Trust_buy", 0) - row.get("Investment_Trust_sell", 0)
            d_buy = (row.get("Dealer_buy", 0) + row.get("Dealer_self_buy", 0) + row.get("Dealer_Hedging_buy", 0)) - \
                    (row.get("Dealer_sell", 0) + row.get("Dealer_self_sell", 0) + row.get("Dealer_Hedging_sell", 0))
            inst_records.append({
                "symbol": sym,
                "date": row.get("date"),
                "foreign_net_buy": f_buy,
                "trust_net_buy": t_buy,
                "dealer_net_buy": d_buy
            })
            
        # B. Fetch Margin & Short Balances for the entire year
        margin_data = fetch_finmind_stock_history("TaiwanStockMarginPurchaseShortSale", stock_id, start_str, end_str)
        for row in margin_data:
            margin_records.append({
                "symbol": sym,
                "date": row.get("date"),
                "margin_balance": row.get("MarginPurchaseTodayBalance", 0),
                "short_balance": row.get("ShortSaleTodayBalance", 0)
            })
            
        # Sleep to comply politely with API limits
        time.sleep(0.4)
        
    df_inst = pd.DataFrame(inst_records)
    df_margin = pd.DataFrame(margin_records)
    
    logger.info(f"[Collector] Collected institutional records: {len(df_inst)} | Margin records: {len(df_margin)}")
    
    # 4. Merge Datasets
    logger.info("[Collector] Merging K-line, institutional and margin datasets...")
    df_merged = df_kline.copy()
    
    if not df_inst.empty and not skip_finmind:
        df_merged = pd.merge(df_merged, df_inst, on=["symbol", "date"], how="left")
    else:
        df_merged["foreign_net_buy"] = 0.0
        df_merged["trust_net_buy"] = 0.0
        df_merged["dealer_net_buy"] = 0.0
        
    if not df_margin.empty and not skip_finmind:
        df_merged = pd.merge(df_merged, df_margin, on=["symbol", "date"], how="left")
    else:
        df_merged["margin_balance"] = 0.0
        df_merged["short_balance"] = 0.0
        
    # Fill missing values for institutional/margin data with 0
    fill_cols = ["foreign_net_buy", "trust_net_buy", "dealer_net_buy", "margin_balance", "short_balance"]
    df_merged[fill_cols] = df_merged[fill_cols].fillna(0)
    
    # 5. Vectorized technical indicators calculation (per symbol)
    logger.info("[Collector] Calculating technical indicators (RSI, KD, MACD, Moving Averages)...")
    processed_dfs = []
    
    for sym, gp in df_merged.groupby("symbol"):
        gp = gp.sort_values("date").copy()
        
        # A. Moving Averages
        gp["ma5"] = gp["close"].rolling(5, min_periods=1).mean()
        gp["ma20"] = gp["close"].rolling(20, min_periods=1).mean()
        
        # B. RSI (14) using Exponential Moving Average
        delta = gp["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        gp["rsi_14"] = 100 - (100 / (1 + rs))
        
        # C. KD (9, 3, 3)
        low_9 = gp["low"].rolling(9, min_periods=1).min()
        high_9 = gp["high"].rolling(9, min_periods=1).max()
        rsv = (gp["close"] - low_9) / (high_9 - low_9 + 1e-9) * 100
        gp["kd_k"] = rsv.ewm(alpha=1/3, adjust=False).mean()
        gp["kd_d"] = gp["kd_k"].ewm(alpha=1/3, adjust=False).mean()
        
        # D. MACD (12, 26, 9)
        ema_12 = gp["close"].ewm(span=12, adjust=False).mean()
        ema_26 = gp["close"].ewm(span=26, adjust=False).mean()
        gp["macd_dif"] = ema_12 - ema_26
        gp["macd_dem"] = gp["macd_dif"].ewm(span=9, adjust=False).mean()
        gp["macd_osc"] = gp["macd_dif"] - gp["macd_dem"]
        
        processed_dfs.append(gp)
        
    df_final = pd.concat(processed_dfs, ignore_index=True)
    
    # Save to CSV
    output_path = os.path.join(os.path.dirname(__file__), "ml_stock_dataset.csv")
    df_final.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"[Collector] ML dataset collection finished successfully! Saved to: {output_path}")

if __name__ == "__main__":
    main()
