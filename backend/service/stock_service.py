import math
import subprocess
import sys
from typing import List, Dict, Any
from dal.stock_metadata_dao import StockMetadataDao
from dal.ace_watchlist_dao import AceWatchlistDao
from crawler import StockCrawler
from common.logger import logger
from common.exceptions import ServiceException

class StockService:
    _crawler_instance = StockCrawler()

    @classmethod
    def get_all_raw_stocks(cls) -> List[Dict[str, Any]]:
        # This calls yfinance sync helper or scrapes symbols from crawler module
        from crawler import sqlite3_connect_helper
        return sqlite3_connect_helper()

    @classmethod
    def filter_stocks(
        cls,
        price_min: float,
        price_max: float,
        min_volume: int,
        pe_max: float,
        ma_bullish: bool,
        exclude_us: bool,
        page: int,
        page_size: int
    ) -> Dict[str, Any]:
        filtered_stocks = StockMetadataDao.filter_stocks(
            price_min=price_min,
            price_max=price_max,
            min_volume=min_volume,
            pe_max=pe_max,
            ma_bullish=ma_bullish,
            exclude_us=exclude_us
        )
        
        total_count = len(filtered_stocks)
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_stocks = filtered_stocks[start_idx:end_idx]
        
        return {
            "status": "success",
            "stocks": paginated_stocks,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }

    @classmethod
    def get_ace_stocks(cls, page: int, page_size: int) -> Dict[str, Any]:
        # Try fetching from the PostgreSQL/SQLite ace_watchlist database
        try:
            ace_symbols = AceWatchlistDao.get_all_symbols()
        except Exception as e:
            logger.error(f"[Service] Failed to load ace_watchlist: {e}")
            ace_symbols = []
            
        # Safety fallback if empty or database loading fails
        if not ace_symbols:
            ace_symbols = ["2330.TW", "2317.TW", "2454.TW", "2603.TW", "3231.TW"]
            
        ace_stocks = StockMetadataDao.get_stocks_by_symbols(ace_symbols)
        
        total_count = len(ace_stocks)
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_stocks = ace_stocks[start_idx:end_idx]
        
        return {
            "status": "success",
            "stocks": paginated_stocks,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }

    @classmethod
    def search_stocks(cls, query: str) -> List[Dict[str, Any]]:
        return StockMetadataDao.search_stocks(query)

    @classmethod
    def get_kline_data(cls, symbol: str, interval: str) -> List[Dict[str, Any]]:
        return cls._crawler_instance.get_kline_data(symbol, interval)

    @classmethod
    def _get_job_path(cls, job_filename: str) -> str:
        import os
        # If running inside Docker (where /app/jobs exists)
        if os.path.exists("/app/jobs"):
            return os.path.abspath(os.path.join("/app", "jobs", job_filename))
        # If running on Host (jobs folder is sibling to backend folder)
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", job_filename))

    @classmethod
    def trigger_finmind_sync(cls, current_admin: str):
        try:
            logger.info(f"[Sync] Admin '{current_admin}' triggered background FinMind synchronization.")
            job_path = cls._get_job_path("sync_finmind.py")
            subprocess.Popen([sys.executable, job_path])
            return {"status": "success", "message": "Background synchronization started"}
        except Exception as e:
            logger.error(f"[Sync] Failed to start FinMind synchronization subprocess: {e}")
            raise ServiceException(f"Failed to start sync: {str(e)}", status_code=500)

    @classmethod
    def trigger_yfinance_sync(cls, current_admin: str):
        try:
            logger.info(f"[Sync] Admin '{current_admin}' triggered background yFinance synchronization.")
            job_path = cls._get_job_path("sync_yfinance.py")
            subprocess.Popen([sys.executable, job_path])
            return {"status": "success", "message": "Background yFinance synchronization started"}
        except Exception as e:
            logger.error(f"[Sync] Failed to start yFinance synchronization subprocess: {e}")
            raise ServiceException(f"Failed to start sync: {str(e)}", status_code=500)

    @classmethod
    def trigger_official_sync(cls, current_admin: str):
        try:
            logger.info(f"[Sync] Admin '{current_admin}' triggered background Official Open Data synchronization.")
            job_path = cls._get_job_path("sync_official.py")
            subprocess.Popen([sys.executable, job_path])
            return {"status": "success", "message": "Background Official Open Data synchronization started"}
        except Exception as e:
            logger.error(f"[Sync] Failed to start Official Open Data synchronization subprocess: {e}")
            raise ServiceException(f"Failed to start sync: {str(e)}", status_code=500)

    @classmethod
    def get_ai_predictions(cls) -> Dict[str, Any]:
        import os
        import pickle
        import datetime
        import pandas as pd
        import numpy as np
        import yfinance as yf
        from dal.stock_metadata_dao import StockMetadataDao
        
        # 1. Resolve model path (supporting both Docker subdirectory mount and local Host sibling layout)
        base_dir_host = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path_host = os.path.join(base_dir_host, "jobs", "ai_stock_model.pkl")
        
        base_dir_docker = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path_docker = os.path.join(base_dir_docker, "jobs", "ai_stock_model.pkl")
        
        if os.path.exists(path_docker):
            model_path = path_docker
        elif os.path.exists(path_host):
            model_path = path_host
        else:
            model_path = "jobs/ai_stock_model.pkl"
            
        if not os.path.exists(model_path):
            raise ServiceException(
                "AI 模型檔案 (ai_stock_model.pkl) 尚未上傳！請先在 Google Colab 訓練完成後，將其下載並放入 jobs/ 資料夾下。",
                status_code=400
            )
            
        # 2. Load model
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
        except Exception as e:
            raise ServiceException(f"無法載入模型檔案: {str(e)}", status_code=500)
            
        # 3. Get top 50 volume stocks from DB (excluding US stocks, only TW)
        conn = StockMetadataDao.get_connection()
        rows = conn.execute("""
            SELECT symbol FROM stock_metadata
            WHERE symbol LIKE '%.TW' OR symbol LIKE '%.TWO'
            ORDER BY volume DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        
        watchlist_symbols = [r["symbol"] for r in rows]
        db_stocks = StockMetadataDao.get_stocks_by_symbols(watchlist_symbols)
        if not db_stocks:
            raise ServiceException("資料庫中無自選股資料，請先執行同步！", status_code=400)
            
        symbols = [s["symbol"] for s in db_stocks]
        
        # 4. Download last 40 days K-lines from yfinance
        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=70)
            raw_kf = yf.download(symbols, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by='ticker', auto_adjust=True)
        except Exception as e:
            raise ServiceException(f"從 yfinance 下載歷史資料失敗: {str(e)}", status_code=500)
            
        # 5. Process features per stock
        feature_cols = [
            "close_to_ma5", "close_to_ma20", "ma5_to_ma20",
            "volume_ratio", "rsi_14", "kd_k", "kd_d",
            "macd_dif", "macd_dem", "macd_osc",
            "foreign_ratio", "trust_ratio", "dealer_ratio",
            "margin_ratio", "short_ratio"
        ]
        
        predictions = []
        for stock in db_stocks:
            sym = stock["symbol"]
            if sym not in raw_kf.columns.levels[0]:
                continue
                
            sym_df = raw_kf[sym].dropna(subset=['Close']).copy()
            if len(sym_df) < 20:
                continue
                
            # Sort chronologically
            sym_df = sym_df.sort_index()
            
            close = sym_df["Close"]
            low = sym_df["Low"]
            high = sym_df["High"]
            volume = sym_df["Volume"]
            
            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            
            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(com=13, adjust=False).mean()
            avg_loss = loss.ewm(com=13, adjust=False).mean()
            rs = avg_gain / (avg_loss + 1e-9)
            rsi = 100 - (100 / (1 + rs))
            
            # KD
            low_9 = low.rolling(9).min()
            high_9 = high.rolling(9).max()
            rsv = (close - low_9) / (high_9 - low_9 + 1e-9) * 100
            kd_k = rsv.ewm(alpha=1/3, adjust=False).mean()
            kd_d = kd_k.ewm(alpha=1/3, adjust=False).mean()
            
            # MACD
            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            dif = ema_12 - ema_26
            dem = dif.ewm(span=9, adjust=False).mean()
            osc = dif - dem
            
            last_idx = sym_df.index[-1]
            last_volume = float(volume.loc[last_idx])
            
            feat_dict = {
                "close_to_ma5": float(close.loc[last_idx] / (ma5.loc[last_idx] + 1e-9)),
                "close_to_ma20": float(close.loc[last_idx] / (ma20.loc[last_idx] + 1e-9)),
                "ma5_to_ma20": float(ma5.loc[last_idx] / (ma20.loc[last_idx] + 1e-9)),
                "volume_ratio": float(last_volume / (volume.rolling(5).mean().loc[last_idx] + 1e-9)),
                "rsi_14": float(rsi.loc[last_idx]),
                "kd_k": float(kd_k.loc[last_idx]),
                "kd_d": float(kd_d.loc[last_idx]),
                "macd_dif": float(dif.loc[last_idx]),
                "macd_dem": float(dem.loc[last_idx]),
                "macd_osc": float(osc.loc[last_idx]),
                "foreign_ratio": float((stock.get("foreign_net_buy") or 0) / (last_volume + 1e-9)),
                "trust_ratio": float((stock.get("trust_net_buy") or 0) / (last_volume + 1e-9)),
                "dealer_ratio": float((stock.get("dealer_net_buy") or 0) / (last_volume + 1e-9)),
                "margin_ratio": float((stock.get("margin_balance") or 0) / (last_volume + 1e-9)),
                "short_ratio": float((stock.get("short_balance") or 0) / (last_volume + 1e-9))
            }
            
            X = pd.DataFrame([feat_dict])[feature_cols]
            prob = float(model.predict_proba(X)[0][1])
            
            predictions.append({
                "symbol": sym,
                "name": stock["name"],
                "price": float(close.loc[last_idx]),
                "change": stock["change"],
                "change_percent": stock["change_percent"],
                "volume": int(last_volume),
                "pe_ratio": stock["pe_ratio"],
                "ma5": float(ma5.loc[last_idx]),
                "ma20": float(ma20.loc[last_idx]),
                "pb_ratio": stock.get("pb_ratio"),
                "dividend_yield": stock.get("dividend_yield"),
                "foreign_net_buy": stock.get("foreign_net_buy"),
                "trust_net_buy": stock.get("trust_net_buy"),
                "dealer_net_buy": stock.get("dealer_net_buy"),
                "margin_balance": stock.get("margin_balance"),
                "short_balance": stock.get("short_balance"),
                "revenue_yoy": stock.get("revenue_yoy"),
                "ai_prob": round(prob * 100, 2)
            })
            
        predictions = sorted(predictions, key=lambda x: x["ai_prob"], reverse=True)
        return {"status": "success", "stocks": predictions}


