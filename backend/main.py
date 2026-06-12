import asyncio
import os
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from crawler import StockCrawler
from broker import MockBroker
from database import DBStore

app = FastAPI(
    title="Day Trading Web Platform API - Phase 2",
    description="Backend API supporting stock filtering, autocompletion search, and real-time trading terminals."
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate core modules
crawler = StockCrawler()
broker = MockBroker()

# Pydantic models for request bodies
class OrderRequest(BaseModel):
    symbol: str
    action: str       # 'BUY' or 'SELL'
    price: float       # Limit price, or 0/null for market
    qty: int          # Quantity in shares/lots
    order_type: str    # 'LIMIT' or 'MARKET'

# API Endpoints
@app.get("/api/screener")
async def get_screener():
    """Fetch the default active stock watchlist from database cache."""
    try:
        from crawler import sqlite3_connect_helper
        data = sqlite3_connect_helper()
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screener/filter")
async def filter_screener(
    price_min: float = Query(0.0),
    price_max: float = Query(999999.0),
    min_volume: int = Query(0),
    pe_max: float = Query(999999.0),
    ma_bullish: bool = Query(False),
    exclude_us: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1)
):
    """Filter stocks in DB based on multiple criteria and return paginated results."""
    try:
        filtered_stocks = DBStore.filter_stocks(
            price_min=price_min,
            price_max=price_max,
            min_volume=min_volume,
            pe_max=pe_max,
            ma_bullish=ma_bullish,
            exclude_us=exclude_us
        )
        
        # Paginate results
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stocks/search")
async def search_stocks(query: str = Query("", min_length=1)):
    """Fuzzy search for symbols or names (Autocompletesuggestions)."""
    try:
        results = DBStore.search_stocks(query)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kline/{symbol}")
async def get_kline(symbol: str, interval: str = Query("1d")):
    """Fetch historical K-line candles for chart initialization."""
    try:
        data = crawler.get_kline_data(symbol, interval)
        return {"status": "success", "symbol": symbol, "interval": interval, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory")
async def get_inventory():
    """Fetch current portfolio holdings and cash balance."""
    try:
        inventory = broker.get_inventory()
        summary = broker.get_account_summary()
        return {
            "status": "success",
            "summary": summary,
            "positions": inventory
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/order")
async def place_order(order_req: OrderRequest):
    """Place a simulated trade order."""
    try:
        order = broker.place_order(
            symbol=order_req.symbol,
            action=order_req.action,
            price=order_req.price,
            qty=order_req.qty,
            order_type=order_req.order_type
        )
        return {"status": "success", "order": order}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders")
async def get_orders():
    """Fetch historical transaction log."""
    try:
        return {"status": "success", "orders": broker.orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket Endpoint
@app.websocket("/ws/market/{symbol}")
async def websocket_market_stream(websocket: WebSocket, symbol: str):
    await websocket.accept()
    print(f"[WebSocket] Connected to market stream for symbol: {symbol}")
    
    # Establish reference baseline price from DB cache
    base_price = 100.0
    try:
        conn = DBStore.search_stocks(symbol)
        if conn:
            # Check price in db metadata
            import sqlite3
            db_conn = sqlite3.connect("trading_platform.db")
            db_conn.row_factory = sqlite3.Row
            row = db_conn.execute("SELECT price FROM stock_metadata WHERE symbol = ?", (symbol,)).fetchone()
            db_conn.close()
            if row:
                base_price = row["price"]
    except Exception:
        pass

    try:
        while True:
            market_data = broker.generate_live_market_data(symbol, base_price)
            await websocket.send_json(market_data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected from market stream for symbol: {symbol}")
    except Exception as e:
        print(f"[WebSocket] Error in market stream for {symbol}: {e}")

# Background Task: Sync yfinance metadata on startup
async def background_yfinance_sync():
    print("[Startup] Waiting 3 seconds before initiating background metadata sync...")
    await asyncio.sleep(3)
    try:
        crawler.sync_all_stock_metadata()
    except Exception as e:
        print(f"[Startup] Background sync encountered an error: {e}")

@app.on_event("startup")
async def on_startup():
    # Schedule background yfinance crawler sync
    asyncio.create_task(background_yfinance_sync())

# Mount static frontend assets
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    print(f"[Static] Mounted frontend files from: {frontend_dir}")
else:
    print(f"[Warning] Frontend directory not found at: {frontend_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
