from broker import MockBroker
from typing import Dict, Any

class OrderService:
    @classmethod
    def place_order(cls, username: str, symbol: str, action: str, price: float, qty: int, order_type: str) -> Dict[str, Any]:
        user_broker = MockBroker(username=username)
        order = user_broker.place_order(
            symbol=symbol,
            action=action,
            price=price,
            qty=qty,
            order_type=order_type
        )
        return {"status": "success", "order": order}

    @classmethod
    def get_orders(cls, username: str) -> Dict[str, Any]:
        user_broker = MockBroker(username=username)
        return {"status": "success", "orders": user_broker.orders}
