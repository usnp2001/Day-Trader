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
    def add_symbols_to_watchlist(cls, rows: List[tuple], conn=None):
        """Adds a list of stock symbols with characteristics features to the ace_watchlist.

        Each tuple in rows should be: (symbol, update_date, strength_dna, hint_double, magic_band, short_sniper, rebound_sprint, create_date)
        """
        if not rows:
            return
            
        should_close = False
        if conn is None:
            conn = cls.get_connection()
            should_close = True
            
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO ace_watchlist (symbol, update_date, strength_dna, hint_double, magic_band, short_sniper, rebound_sprint, create_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET 
                update_date = EXCLUDED.update_date,
                strength_dna = EXCLUDED.strength_dna,
                hint_double = EXCLUDED.hint_double,
                magic_band = EXCLUDED.magic_band,
                short_sniper = EXCLUDED.short_sniper,
                rebound_sprint = EXCLUDED.rebound_sprint,
                create_date = EXCLUDED.create_date
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
