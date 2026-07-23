from typing import List, Dict, Any
from common.base_dao import BaseDAO

class UserWatchlistDao(BaseDAO):
    @classmethod
    def get_watchlist(cls, username: str) -> List[Dict[str, Any]]:
        """Fetches the user's custom watchlist joined with metadata and day trading simulation summaries."""
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT w.symbol, m.name, m.price, m.change, m.change_percent, m.volume,
                   s.pnl AS sim_pnl, s.status AS sim_status
            FROM user_watchlist w
            LEFT JOIN stock_metadata m ON w.symbol = m.symbol
            LEFT JOIN day_trading_summary s ON w.username = s.username AND w.symbol = s.symbol
            WHERE w.username = ?
            ORDER BY w.symbol ASC
        """, (username,)).fetchall()
        conn.close()
        
        watchlist = []
        for r in rows:
            watchlist.append({
                "symbol": r["symbol"],
                "name": r["name"] or "未知",
                "price": r["price"] or 0.0,
                "change": r["change"] or 0.0,
                "change_percent": r["change_percent"] or 0.0,
                "volume": r["volume"] or 0,
                "sim_pnl": r["sim_pnl"],
                "sim_status": r["sim_status"]
            })
        return watchlist

    @classmethod
    def is_in_watchlist(cls, username: str, symbol: str) -> bool:
        """Checks if a stock symbol is in the user's watchlist."""
        conn = cls.get_connection()
        row = conn.execute("""
            SELECT 1 FROM user_watchlist
            WHERE username = ? AND symbol = ?
        """, (username, symbol)).fetchone()
        conn.close()
        return row is not None

    @classmethod
    def add_to_watchlist(cls, username: str, symbol: str) -> bool:
        """Adds a symbol to the user's watchlist if not already present."""
        if cls.is_in_watchlist(username, symbol):
            return False
            
        conn = cls.get_connection()
        try:
            conn.execute("""
                INSERT INTO user_watchlist (username, symbol)
                VALUES (?, ?)
            """, (username, symbol))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @classmethod
    def remove_from_watchlist(cls, username: str, symbol: str) -> bool:
        """Removes a single symbol from the user's watchlist."""
        conn = cls.get_connection()
        try:
            cursor = conn.execute("""
                DELETE FROM user_watchlist
                WHERE username = ? AND symbol = ?
            """, (username, symbol))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @classmethod
    def remove_multiple_from_watchlist(cls, username: str, symbols: List[str]) -> int:
        """Removes multiple symbols from the user's watchlist inside a single transaction."""
        if not symbols:
            return 0
        conn = cls.get_connection()
        try:
            placeholders = ",".join(["?"] * len(symbols))
            cursor = conn.execute(f"""
                DELETE FROM user_watchlist
                WHERE username = ? AND symbol IN ({placeholders})
            """, [username] + symbols)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
