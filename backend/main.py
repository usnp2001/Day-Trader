import sys
import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from typing import Optional

# Setup sys.path to resolve backend package imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from common.config import JWT_SECRET
from common.logger import logger
from common.auth_utils import verify_jwt
from common.exceptions import ServiceException
from dal.database_init import init_db
from dal.user_dao import UserDao
from dal.stock_metadata_dao import StockMetadataDao
from broker import MockBroker
from crawler import StockCrawler

# Controllers
from controller import auth_controller, account_controller, order_controller, stock_controller, admin_controller

app = FastAPI(
    title="Day Trading Web Platform API - Phase 3 (MVC Refactoring)",
    description="Backend API rebuilt with structured MVC & Three-Tier architecture."
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Custom Exception Handler
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

# Include Routers
app.include_router(auth_controller.router)
app.include_router(account_controller.router)
app.include_router(order_controller.router)
app.include_router(stock_controller.router)
app.include_router(admin_controller.router)

# Instantiate crawler for startup background sync
crawler = StockCrawler()

# Background Task: Sync yfinance metadata on startup
async def background_yfinance_sync():
    logger.info("[Startup] Waiting 3 seconds before initiating background metadata sync...")
    await asyncio.sleep(3)
    try:
        crawler.sync_all_stock_metadata()
    except Exception as e:
        logger.error(f"[Startup] Background sync encountered an error: {e}")

@app.on_event("startup")
async def on_startup():
    # 1. Initialize SQLite Database Tables & Seeds
    init_db()
    
    # 2. Trigger startup sync task
    asyncio.create_task(background_yfinance_sync())

# WebSocket Stream Endpoint
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

    username = payload["sub"]
    await websocket.accept()
    logger.info(f"[WebSocket] Connected user '{username}' to market stream: {symbol}")
    
    base_price = 100.0
    try:
        res = StockMetadataDao.get_stocks_by_symbols([symbol])
        if res:
            base_price = res[0]["price"]
    except Exception:
        pass

    user_broker = MockBroker(username=username)
    try:
        while True:
            market_data = user_broker.generate_live_market_data(symbol, base_price)
            await websocket.send_json(market_data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Disconnected user '{username}' from market stream: {symbol}")
    except Exception as e:
        logger.error(f"[WebSocket] Error in market stream for user '{username}', symbol {symbol}: {e}")

# Mount static frontend assets
frontend_dir = os.path.abspath(os.path.join(backend_dir, "..", "frontend"))

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"[Static] Mounted frontend files from: {frontend_dir}")
else:
    logger.warning(f"[Warning] Frontend directory not found at: {frontend_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
