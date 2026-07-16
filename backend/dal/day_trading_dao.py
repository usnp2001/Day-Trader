from typing import List, Dict, Any
from common.base_dao import BaseDAO

class DayTradingDao(BaseDAO):
    @classmethod
    def clear_ticks(cls):
        """Clears all records in day_trading_ticks."""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM day_trading_ticks")
        conn.commit()
        conn.close()

    @classmethod
    def insert_ticks(cls, ticks_list: List[Dict[str, Any]]):
        """Bulk inserts stock ticks."""
        if not ticks_list:
            return
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO day_trading_ticks (symbol, timestamp, price, volume, tick_type)
            VALUES (?, ?, ?, ?, ?)
        """, [(t["symbol"], t["timestamp"], t["price"], t["volume"], t.get("tick_type", "OUTER")) for t in ticks_list])
        conn.commit()
        conn.close()

    @classmethod
    def get_all_ticks(cls) -> List[Dict[str, Any]]:
        """Retrieves all ticks sorted by symbol and timestamp."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT symbol, timestamp, price, volume, tick_type
            FROM day_trading_ticks
            ORDER BY symbol, timestamp ASC
        """).fetchall()
        conn.close()
        return [{"symbol": r["symbol"], "timestamp": r["timestamp"], "price": r["price"], "volume": r["volume"], "tick_type": r["tick_type"]} for r in rows]

    @classmethod
    def get_ticks_by_symbol(cls, symbol: str) -> List[Dict[str, Any]]:
        """Retrieves ticks for a specific symbol sorted by timestamp."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT symbol, timestamp, price, volume, tick_type
            FROM day_trading_ticks
            WHERE symbol = ?
            ORDER BY timestamp ASC
        """, (symbol,)).fetchall()
        conn.close()
        return [{"symbol": r["symbol"], "timestamp": r["timestamp"], "price": r["price"], "volume": r["volume"], "tick_type": r["tick_type"]} for r in rows]

    @classmethod
    def clear_user_simulation_data(cls, username: str):
        """Clears existing trades and summary for the given user."""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM day_trading_trades WHERE username = ?", (username,))
        cursor.execute("DELETE FROM day_trading_summary WHERE username = ?", (username,))
        conn.commit()
        conn.close()

    @classmethod
    def insert_trades(cls, trades_list: List[Dict[str, Any]]):
        """Inserts multiple trade detail records."""
        if not trades_list:
            return
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO day_trading_trades (trade_id, username, symbol, action, trade_type, price, qty, fee, tax, pnl, timestamp, tick_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                t["trade_id"], t["username"], t["symbol"], t["action"], t["trade_type"],
                t["price"], t["qty"], t["fee"], t["tax"], t["pnl"], t["timestamp"], t.get("tick_type", "OUTER")
            ) for t in trades_list
        ])
        conn.commit()
        conn.close()

    @classmethod
    def insert_summaries(cls, summaries_list: List[Dict[str, Any]]):
        """Inserts or replaces stock trading summary records."""
        if not summaries_list:
            return
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Use INSERT INTO logic
        for s in summaries_list:
            cursor.execute("""
                INSERT INTO day_trading_summary (
                    username, symbol, name, volume, open_price, close_price, high_price, low_price, pnl, trend, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["username"], s["symbol"], s["name"], s["volume"], s["open_price"],
                s["close_price"], s["high_price"], s["low_price"], s["pnl"], s["trend"], s["status"]
            ))
        conn.commit()
        conn.close()

    @classmethod
    def get_simulation_summary(cls, username: str) -> List[Dict[str, Any]]:
        """Retrieves simulation summaries for the given user."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT username, symbol, name, volume, open_price, close_price, high_price, low_price, pnl, trend, status
            FROM day_trading_summary
            WHERE username = ?
            ORDER BY symbol ASC
        """, (username,)).fetchall()
        conn.close()
        return [{
            "username": r["username"],
            "symbol": r["symbol"],
            "name": r["name"],
            "volume": r["volume"],
            "open_price": r["open_price"],
            "close_price": r["close_price"],
            "high_price": r["high_price"],
            "low_price": r["low_price"],
            "pnl": r["pnl"],
            "trend": r["trend"],
            "status": r["status"]
        } for r in rows]

    @classmethod
    def get_trades_by_symbol(cls, username: str, symbol: str) -> List[Dict[str, Any]]:
        """Retrieves trade records for a specific user and symbol."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT trade_id, username, symbol, action, trade_type, price, qty, fee, tax, pnl, timestamp, tick_type
            FROM day_trading_trades
            WHERE username = ? AND symbol = ?
            ORDER BY timestamp ASC, trade_id ASC
        """, (username, symbol)).fetchall()
        conn.close()
        return [{
            "trade_id": r["trade_id"],
            "username": r["username"],
            "symbol": r["symbol"],
            "action": r["action"],
            "trade_type": r["trade_type"],
            "price": r["price"],
            "qty": r["qty"],
            "fee": r["fee"],
            "tax": r["tax"],
            "pnl": r["pnl"],
            "timestamp": r["timestamp"],
            "tick_type": r["tick_type"]
        } for r in rows]

    @classmethod
    def get_tick_rules(cls) -> List[Dict[str, Any]]:
        """Retrieves all tick rules and breakeven prices."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT price_min, price_max, tick_size, example_price, breakeven_30, breakeven_20, breakeven_10
            FROM day_trading_tick_rules
            ORDER BY price_min ASC
        """).fetchall()
        conn.close()
        return [{
            "price_min": r["price_min"],
            "price_max": r["price_max"],
            "tick_size": r["tick_size"],
            "example_price": r["example_price"],
            "breakeven_30": r["breakeven_30"],
            "breakeven_20": r["breakeven_20"],
            "breakeven_10": r["breakeven_10"]
        } for r in rows]
