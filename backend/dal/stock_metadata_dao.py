import sqlite3
from typing import List, Dict, Any, Optional
from common.base_dao import BaseDAO

class StockMetadataDao(BaseDAO):
    @classmethod
    def search_stocks(cls, query: str) -> List[Dict[str, Any]]:
        """Returns fuzzy matches (max 10) by symbol or name for autocomplete suggestions."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT symbol, name FROM stock_metadata
            WHERE symbol LIKE ? OR name LIKE ?
            LIMIT 10
        """, (f"%{query}%", f"%{query}%")).fetchall()
        conn.close()
        return [{"symbol": r["symbol"], "name": r["name"]} for r in rows]

    @classmethod
    def filter_stocks(
        cls,
        price_min: float = 0.0,
        price_max: float = 999999.0,
        min_volume: int = 0,
        pe_max: float = 999999.0,
        ma_bullish: bool = False,
        exclude_us: bool = False
    ) -> List[Dict[str, Any]]:
        """Query and filter stocks based on technical and fundamental criteria."""
        conn = cls.get_connection()
        query = """
            SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                   pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
            FROM stock_metadata
            WHERE price >= ? AND price <= ? AND volume >= ? AND (pe_ratio IS NULL OR pe_ratio <= ?)
        """
        params = [price_min, price_max, min_volume, pe_max]
        
        if ma_bullish:
            query += " AND ma5 > ma20"
            
        if exclude_us:
            query += " AND (symbol LIKE '%.TW' OR symbol LIKE '%.TWO')"
            
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "price": r["price"],
                "change": r["change"],
                "change_percent": r["change_percent"],
                "volume": r["volume"],
                "pe_ratio": r["pe_ratio"],
                "ma5": r["ma5"],
                "ma20": r["ma20"],
                "stockId": r["stockId"],
                "pb_ratio": r["pb_ratio"],
                "dividend_yield": r["dividend_yield"],
                "foreign_net_buy": r["foreign_net_buy"],
                "trust_net_buy": r["trust_net_buy"],
                "dealer_net_buy": r["dealer_net_buy"],
                "margin_balance": r["margin_balance"],
                "short_balance": r["short_balance"],
                "revenue_yoy": r["revenue_yoy"]
            })
        return stocks

    @classmethod
    def get_stocks_by_symbols(cls, symbols: List[str]) -> List[Dict[str, Any]]:
        """Query and return metadata for a specific list of stock symbols."""
        if not symbols:
            return []
        conn = cls.get_connection()
        placeholders = ",".join(["?"] * len(symbols))
        query = f"""
            SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                   pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
            FROM stock_metadata
            WHERE symbol IN ({placeholders})
        """
        rows = conn.execute(query, symbols).fetchall()
        conn.close()
        
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "price": r["price"],
                "change": r["change"],
                "change_percent": r["change_percent"],
                "volume": r["volume"],
                "pe_ratio": r["pe_ratio"],
                "ma5": r["ma5"],
                "ma20": r["ma20"],
                "stockId": r["stockId"],
                "pb_ratio": r["pb_ratio"],
                "dividend_yield": r["dividend_yield"],
                "foreign_net_buy": r["foreign_net_buy"],
                "trust_net_buy": r["trust_net_buy"],
                "dealer_net_buy": r["dealer_net_buy"],
                "margin_balance": r["margin_balance"],
                "short_balance": r["short_balance"],
                "revenue_yoy": r["revenue_yoy"]
            })
        return stocks

    @classmethod
    def update_stock_metadata(cls, stocks_list: List[Dict[str, Any]]):
        """Updates or inserts stock details in bulk (used by backend crawlers)."""
        conn = cls.get_connection()
        cursor = conn.cursor()
        for s in stocks_list:
            symbol = s["symbol"]
            # Dynamically compute stockId if not provided
            if "stockId" in s:
                stock_id = s["stockId"]
            else:
                if symbol.endswith(".TW") or symbol.endswith(".TWO"):
                    try:
                        stock_id = int(symbol.split(".")[0])
                    except ValueError:
                        stock_id = 0
                else:
                    stock_id = 0

            cursor.execute("""
                INSERT INTO stock_metadata (
                    symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                    pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    price=excluded.price,
                    change=excluded.change,
                    change_percent=excluded.change_percent,
                    volume=excluded.volume,
                    pe_ratio=COALESCE(excluded.pe_ratio, pe_ratio),
                    ma5=COALESCE(excluded.ma5, ma5),
                    ma20=COALESCE(excluded.ma20, ma20),
                    stockId=excluded.stockId,
                    pb_ratio=COALESCE(excluded.pb_ratio, pb_ratio),
                    dividend_yield=COALESCE(excluded.dividend_yield, dividend_yield),
                    foreign_net_buy=COALESCE(excluded.foreign_net_buy, foreign_net_buy),
                    trust_net_buy=COALESCE(excluded.trust_net_buy, trust_net_buy),
                    dealer_net_buy=COALESCE(excluded.dealer_net_buy, dealer_net_buy),
                    margin_balance=COALESCE(excluded.margin_balance, margin_balance),
                    short_balance=COALESCE(excluded.short_balance, short_balance),
                    revenue_yoy=COALESCE(excluded.revenue_yoy, revenue_yoy)
            """, (
                s["symbol"], s["name"], s.get("price", 0.0), s.get("change", 0.0), s.get("change_percent", 0.0),
                s.get("volume", 0), s.get("pe_ratio"), s.get("ma5"), s.get("ma20"), stock_id,
                s.get("pb_ratio"), s.get("dividend_yield"), s.get("foreign_net_buy"), s.get("trust_net_buy"),
                s.get("dealer_net_buy"), s.get("margin_balance"), s.get("short_balance"), s.get("revenue_yoy")
            ))
        conn.commit()
        conn.close()
