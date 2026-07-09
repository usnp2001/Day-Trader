from typing import List, Dict, Any
from common.base_dao import BaseDAO

class OrderDao(BaseDAO):
    @classmethod
    def add_order(cls, username: str, order: Dict[str, Any]):
        conn = cls.get_connection()
        conn.execute("""
            INSERT INTO orders (order_id, username, symbol, action, price, qty, order_type, status, exec_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["order_id"],
            username,
            order["symbol"],
            order["action"],
            order["price"],
            order["qty"],
            order["order_type"],
            order["status"],
            order["exec_price"],
            order["timestamp"]
        ))
        conn.commit()
        conn.close()

    @classmethod
    def get_all_orders(cls, username: str) -> List[Dict[str, Any]]:
        conn = cls.get_connection()
        rows = conn.execute("SELECT order_id, symbol, action, price, qty, order_type, status, exec_price, timestamp FROM orders WHERE username = ? ORDER BY rowid DESC", (username,)).fetchall()
        conn.close()
        
        orders = []
        for r in rows:
            orders.append({
                "order_id": r["order_id"],
                "symbol": r["symbol"],
                "action": r["action"],
                "price": r["price"],
                "qty": r["qty"],
                "order_type": r["order_type"],
                "status": r["status"],
                "exec_price": r["exec_price"],
                "timestamp": r["timestamp"]
            })
        return orders
