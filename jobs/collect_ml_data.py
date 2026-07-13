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

def main():
    logger.info("[Collector] Starting ML dataset collection job...")
    
    if not os.path.exists(DB_FILE):
        logger.error(f"[Collector] Database file not found at: {DB_FILE}")
        return

    # 1. Fetch all Taiwan symbols and their latest official chips snapshot from SQLite
    logger.info("[Collector] Querying SQLite for all Taiwan stock symbols & latest chips snapshot...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance
        FROM stock_metadata 
        WHERE symbol LIKE '%.TW' OR symbol LIKE '%.TWO'
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        logger.error("[Collector] No Taiwan symbols found in SQLite stock_metadata!")
        return
        
    symbol_map = {}
    stock_chips_map = {}
    for r in rows:
        sym = r[0]
        symbol_map[sym] = r[1]
        stock_chips_map[sym] = {
            "foreign_net_buy": float(r[2] or 0.0),
            "trust_net_buy": float(r[3] or 0.0),
            "dealer_net_buy": float(r[4] or 0.0),
            "margin_balance": float(r[5] or 0.0),
            "short_balance": float(r[6] or 0.0)
        }
        
    symbols = list(symbol_map.keys())
    logger.info(f"[Collector] Selected {len(symbols)} Taiwan stocks from database. (Excluded US stocks)")
    
    # 2. Download 1 year K-Line data using yfinance
    logger.info("[Collector] Downloading 1 year K-Line data from yfinance...")
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=380) #Warmup days for MA calculations
    
    try:
        raw_kf = yf.download(symbols, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by='ticker', auto_adjust=True)
    except Exception as e:
        logger.error(f"[Collector] yfinance bulk download failed: {e}")
        return

    kline_records = []
    logger.info("[Collector] Processing K-line data and injecting latest official chips snapshot...")
    
    for sym in symbols:
        # Check if yfinance returned data for this ticker
        if sym not in raw_kf.columns.levels[0]:
            continue
            
        sym_df = raw_kf[sym].dropna(subset=['Close']).copy()
        if sym_df.empty:
            continue
            
        sym_df = sym_df.reset_index()
        # Sort by Date ascending to find the latest row
        sym_df = sym_df.sort_values('Date').reset_index(drop=True)
        
        n_rows = len(sym_df)
        latest_idx = n_rows - 1
        chips = stock_chips_map[sym]
        
        for idx, r in sym_df.iterrows():
            # Inject latest official chips data only into the final row (today)
            if idx == latest_idx:
                f_buy = chips["foreign_net_buy"]
                t_buy = chips["trust_net_buy"]
                d_buy = chips["dealer_net_buy"]
                margin = chips["margin_balance"]
                short = chips["short_balance"]
            else:
                f_buy = 0.0
                t_buy = 0.0
                d_buy = 0.0
                margin = 0.0
                short = 0.0
                
            kline_records.append({
                "symbol": sym,
                "date": r['Date'].strftime("%Y-%m-%d"),
                "open": float(r['Open']),
                "high": float(r['High']),
                "low": float(r['Low']),
                "close": float(r['Close']),
                "volume": int(r['Volume']),
                "foreign_net_buy": f_buy,
                "trust_net_buy": t_buy,
                "dealer_net_buy": d_buy,
                "margin_balance": margin,
                "short_balance": short
            })
            
    df_merged = pd.DataFrame(kline_records)
    if df_merged.empty:
        logger.error("[Collector] No stock records compiled!")
        return
        
    logger.info(f"[Collector] Compiled {len(df_merged)} daily records for all Taiwan stocks.")
    
    # 3. Vectorized technical indicators calculation (per symbol)
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
