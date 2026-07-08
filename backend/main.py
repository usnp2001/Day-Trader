import asyncio
import os
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from crawler import StockCrawler
from broker import MockBroker
from database import DBStore
from auth_utils import create_jwt, verify_jwt, generate_salt, hash_password

app = FastAPI(
    title="Day Trading Web Platform API - Phase 3",
    description="Backend API supporting stock filtering, autocompletion search, and JWT authenticated day trading."
)

# JWT Secret Key
JWT_SECRET = "super_secret_trading_platform_key_12345"

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate core modules (global crawler for shared stock_metadata updates)
crawler = StockCrawler()

# Pydantic models for request bodies
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class CashAdjustmentRequest(BaseModel):
    cash: float

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str

class OrderRequest(BaseModel):
    symbol: str
    action: str       # 'BUY' or 'SELL'
    price: float      # Limit price, or 0/null for market
    qty: int          # Quantity in shares/lots
    order_type: str    # 'LIMIT' or 'MARKET'

# JWT Authentication Dependency
async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    payload = verify_jwt(token, JWT_SECRET)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token or session expired")
    
    import time
    if "exp" in payload and payload["exp"] < time.time():
        raise HTTPException(status_code=401, detail="Token has expired")
        
    return payload["sub"]

async def get_current_admin(current_user: str = Depends(get_current_user)) -> str:
    user = DBStore.get_user(current_user)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Permission denied. Admin role required.")
    return current_user

# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    username = req.username.strip()
    password = req.password
    
    if not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="Username cannot be empty and password must be at least 6 characters")
        
    if DBStore.get_user(username):
        raise HTTPException(status_code=400, detail="Username is already taken")
        
    salt = generate_salt()
    hashed = hash_password(password, salt)
    
    success = DBStore.create_user(username, hashed, salt, role="user")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user account")
        
    return {"status": "success", "message": "Registered successfully"}

@app.post("/api/auth/login")
async def login_api(req: LoginRequest):
    username = req.username.strip()
    password = req.password
    
    user = DBStore.get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    hashed = hash_password(password, user["salt"])
    if hashed != user["hashed_password"]:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    import time
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + 86400
    }
    token = create_jwt(payload, JWT_SECRET)
    
    return {
        "status": "success",
        "access_token": token,
        "username": user["username"],
        "role": user["role"]
    }

# ==========================================
# ACCOUNT ENDPOINTS
# ==========================================

@app.post("/api/account/adjust_cash")
async def adjust_cash(req: CashAdjustmentRequest, current_user: str = Depends(get_current_user)):
    try:
        DBStore.update_cash(current_user, req.cash)
        return {"status": "success", "message": "Cash balance adjusted successfully", "cash": req.cash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ADMIN ENDPOINTS
# ==========================================

@app.get("/api/admin/users")
async def admin_get_users(current_admin: str = Depends(get_current_admin)):
    try:
        users = DBStore.get_all_users()
        return {"status": "success", "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/create_user")
async def admin_create_user(req: CreateUserRequest, current_admin: str = Depends(get_current_admin)):
    username = req.username.strip()
    password = req.password
    role = req.role
    
    if not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="Username cannot be empty and password must be at least 6 characters")
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'")
        
    if DBStore.get_user(username):
        raise HTTPException(status_code=400, detail="Username is already taken")
        
    salt = generate_salt()
    hashed = hash_password(password, salt)
    
    success = DBStore.create_user(username, hashed, salt, role=role)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user account")
        
    return {"status": "success", "message": f"User '{username}' created successfully as '{role}'"}

@app.delete("/api/admin/delete_user/{target_username}")
async def admin_delete_user(target_username: str, current_admin: str = Depends(get_current_admin)):
    if target_username == current_admin:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
        
    user = DBStore.get_user(target_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    success = DBStore.delete_user(target_username)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user account")
        
    return {"status": "success", "message": f"User '{target_username}' deleted successfully"}

# ==========================================
# TRADING & SCREENER ENDPOINTS (PROTECTED)
# ==========================================

@app.get("/api/screener")
async def get_screener(current_user: str = Depends(get_current_user)):
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
    page_size: int = Query(10, ge=1),
    current_user: str = Depends(get_current_user)
):
    try:
        filtered_stocks = DBStore.filter_stocks(
            price_min=price_min,
            price_max=price_max,
            min_volume=min_volume,
            pe_max=pe_max,
            ma_bullish=ma_bullish,
            exclude_us=exclude_us
        )
        
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

@app.get("/api/screener/ace")
async def ace_screener(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    current_user: str = Depends(get_current_user)
):
    try:
        # Predefined symbols for Ace Stock Selection mock data
        ace_symbols = ["2330.TW", "2317.TW", "2454.TW", "2603.TW", "3231.TW"]
        
        # Fetch actual stock metadata from DB for these symbols to make sure the app behaves realistically
        ace_stocks = DBStore.get_stocks_by_symbols(ace_symbols)
        
        total_count = len(ace_stocks)
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_stocks = ace_stocks[start_idx:end_idx]
        
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
async def search_stocks(query: str = Query("", min_length=1), current_user: str = Depends(get_current_user)):
    try:
        results = DBStore.search_stocks(query)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kline/{symbol}")
async def get_kline(symbol: str, interval: str = Query("1d"), current_user: str = Depends(get_current_user)):
    try:
        data = crawler.get_kline_data(symbol, interval)
        return {"status": "success", "symbol": symbol, "interval": interval, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory")
async def get_inventory(current_user: str = Depends(get_current_user)):
    try:
        user_broker = MockBroker(username=current_user)
        inventory = user_broker.get_inventory()
        summary = user_broker.get_account_summary()
        return {
            "status": "success",
            "summary": summary,
            "positions": inventory
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/order")
async def place_order(order_req: OrderRequest, current_user: str = Depends(get_current_user)):
    try:
        user_broker = MockBroker(username=current_user)
        order = user_broker.place_order(
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
async def get_orders(current_user: str = Depends(get_current_user)):
    try:
        user_broker = MockBroker(username=current_user)
        return {"status": "success", "orders": user_broker.orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# WEBSOCKET STREAM ENDPOINT
# ==========================================

@app.websocket("/ws/market/{symbol}")
async def websocket_market_stream(websocket: WebSocket, symbol: str, token: Optional[str] = Query(None)):
    # 1. Verify Query Token
    if not token:
        await websocket.close(code=1008)
        return
    payload = verify_jwt(token, JWT_SECRET)
    if not payload or "sub" not in payload:
        await websocket.close(code=1008)
        return
        
    import time
    if "exp" in payload and payload["exp"] < time.time():
        await websocket.close(code=1008)
        return

    username = payload["sub"]
    await websocket.accept()
    print(f"[WebSocket] Connected user '{username}' to market stream: {symbol}")
    
    base_price = 100.0
    try:
        import sqlite3
        db_conn = sqlite3.connect("trading_platform.db")
        db_conn.row_factory = sqlite3.Row
        row = db_conn.execute("SELECT price FROM stock_metadata WHERE symbol = ?", (symbol,)).fetchone()
        db_conn.close()
        if row:
            base_price = row["price"]
    except Exception:
        pass

    user_broker = MockBroker(username=username)
    try:
        while True:
            market_data = user_broker.generate_live_market_data(symbol, base_price)
            await websocket.send_json(market_data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected user '{username}' from market stream: {symbol}")
    except Exception as e:
        print(f"[WebSocket] Error in market stream for user '{username}', symbol {symbol}: {e}")

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
