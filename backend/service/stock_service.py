import math
import subprocess
import sys
from typing import List, Dict, Any
from dal.stock_metadata_dao import StockMetadataDao
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
        # Predefined symbols for Ace Stock Selection mock data
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
    def trigger_finmind_sync(cls, current_admin: str):
        try:
            logger.info(f"[Sync] Admin '{current_admin}' triggered background FinMind synchronization.")
            subprocess.Popen([sys.executable, "jobs/sync_finmind.py"])
            return {"status": "success", "message": "Background synchronization started"}
        except Exception as e:
            logger.error(f"[Sync] Failed to start FinMind synchronization subprocess: {e}")
            raise ServiceException(f"Failed to start sync: {str(e)}", status_code=500)
stream = None
