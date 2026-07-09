from typing import List, Dict, Any
from common.base_dao import BaseDAO

class PositionDao(BaseDAO):
    @classmethod
    def get_positions(cls, username: str) -> List[Dict[str, Any]]:
        conn = cls.get_connection()
        rows = conn.execute("SELECT symbol, name, qty, buy_price FROM positions WHERE username = ? AND qty != 0", (username,)).fetchall()
        conn.close()
        
        positions = []
        for r in rows:
            positions.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "qty": r["qty"],
                "buy_price": r["buy_price"],
                "current_price": r["buy_price"], # Default current price to buy price initially
                "market_value": r["qty"] * r["buy_price"],
                "unrealized_pnl": 0.0,
                "pnl_percent": 0.0
            })
        return positions

    @classmethod
    def update_position(cls, username: str, symbol: str, name: str, qty: int, buy_price: float):
        conn = cls.get_connection()
        if qty == 0:
            conn.execute("DELETE FROM positions WHERE username = ? AND symbol = ?", (username, symbol))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO positions (username, symbol, name, qty, buy_price)
                VALUES (?, ?, ?, ?, ?)
            """, (username, symbol, name, qty, buy_price))
        conn.commit()
        conn.close()
