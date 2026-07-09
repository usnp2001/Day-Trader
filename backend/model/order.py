from pydantic import BaseModel

class OrderRequest(BaseModel):
    symbol: str
    action: str       # 'BUY' or 'SELL'
    price: float      # Limit price, or 0/null for market
    qty: int          # Quantity in shares/lots
    order_type: str    # 'LIMIT' or 'MARKET'
