from typing import List
from common.base_dao import BaseDAO

class AceWatchlistDao(BaseDAO):
    @classmethod
    def clear_watchlist(cls, conn=None):
        """Clears all records in the ace_watchlist table."""
        should_close = False
        if conn is None:
            conn = cls.get_connection()
            should_close = True
            
        conn.execute("DELETE FROM ace_watchlist")
        conn.commit()
        
        if should_close:
            conn.close()

    @classmethod
    def add_symbols_to_watchlist(cls, symbols: List[str], update_date: str, conn=None):
        """Adds a list of stock symbols to the ace_watchlist."""
        if not symbols:
            return
            
        should_close = False
        if conn is None:
            conn = cls.get_connection()
            should_close = True
            
        cursor = conn.cursor()
        
        # Prepare batch insert rows
        rows = [(sym, update_date) for sym in symbols]
        
        cursor.executemany("""
            INSERT INTO ace_watchlist (symbol, update_date)
            VALUES (?, ?)
            ON CONFLICT (symbol) DO UPDATE SET update_date = EXCLUDED.update_date
        """, rows)
        
        conn.commit()
        
        if should_close:
            conn.close()

    @classmethod
    def get_all_symbols(cls) -> List[str]:
        """Fetches all symbols currently in the ace_watchlist."""
        conn = cls.get_connection()
        rows = conn.execute("SELECT symbol FROM ace_watchlist").fetchall()
        conn.close()
        return [r["symbol"] for r in rows]
