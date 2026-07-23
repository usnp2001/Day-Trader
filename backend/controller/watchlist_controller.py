from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from dal.user_watchlist_dao import UserWatchlistDao
from dal.stock_metadata_dao import StockMetadataDao
from service.day_trading_service import DayTradingService
from controller.dependencies import get_current_user
from models.output.api_response import ApiResponse

router = APIRouter(prefix="/api/watchlist")

class AddWatchlistItemRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol to add (e.g. '2330.TW')")

class DeleteMultipleWatchlistRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols to delete")

class WatchlistSimulationRequest(BaseModel):
    allocated_limit: float = Field(500000.0, description="Allocated budget limit per stock in TWD", ge=1000.0)
    symbols: List[str] = Field(..., description="List of stock symbols to run simulation on")

@router.get("")
async def get_watchlist(current_user: str = Depends(get_current_user)):
    """Retrieves all watchlisted stocks with metadata for the current user."""
    watchlist = UserWatchlistDao.get_watchlist(current_user)
    return ApiResponse.create(result=watchlist)

@router.get("/check/{symbol}")
async def check_watchlist(symbol: str, current_user: str = Depends(get_current_user)):
    """Checks if a specific symbol is in the user's watchlist."""
    is_present = UserWatchlistDao.is_in_watchlist(current_user, symbol)
    return ApiResponse.create(result={"in_watchlist": is_present})

@router.post("")
async def add_watchlist_item(req: AddWatchlistItemRequest, current_user: str = Depends(get_current_user)):
    """Adds a stock to the user's watchlist after validating its existence in metadata."""
    symbol = req.symbol.strip().upper()
    
    # Check if stock exists in stock_metadata
    conn = StockMetadataDao.get_connection()
    exists = conn.execute("SELECT 1 FROM stock_metadata WHERE symbol = ?", (symbol,)).fetchone()
    conn.close()
    
    if not exists:
        raise HTTPException(status_code=400, detail=f"找不到股票代號 {symbol} 的元數據，請先執行資料庫同步！")
        
    added = UserWatchlistDao.add_to_watchlist(current_user, symbol)
    if not added:
        return ApiResponse.create(message=f"股票 {symbol} 已經在您的自選清單中。")
    return ApiResponse.create(message=f"已成功將 {symbol} 加入自選清單。")

@router.delete("")
async def delete_watchlist_item(symbol: str = Query(...), current_user: str = Depends(get_current_user)):
    """Removes a single stock from the user's watchlist."""
    removed = UserWatchlistDao.remove_from_watchlist(current_user, symbol.strip().upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"自選清單中找不到股票 {symbol}")
    return ApiResponse.create(message=f"已從自選清單中移除 {symbol}。")

@router.post("/delete-multiple")
async def delete_multiple_watchlist_items(req: DeleteMultipleWatchlistRequest, current_user: str = Depends(get_current_user)):
    """Removes multiple stocks from the user's watchlist."""
    removed_count = UserWatchlistDao.remove_multiple_from_watchlist(current_user, [s.strip().upper() for s in req.symbols])
    return ApiResponse.create(message=f"已成功從自選清單中移除 {removed_count} 檔股票。")

@router.post("/import")
async def import_watchlist_ticks(current_user: str = Depends(get_current_user)):
    """Triggers yfinance/mock ticks import for all stocks in the user's custom watchlist."""
    res = DayTradingService.import_watchlist_ticks(current_user)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)

@router.post("/run")
async def run_watchlist_simulation(req: WatchlistSimulationRequest, current_user: str = Depends(get_current_user)):
    """Executes the Peak/Trough day trading simulation on the checked watchlist stocks."""
    res = DayTradingService.run_simulation(
        username=current_user,
        allocated_limit=req.allocated_limit,
        symbols_filter=req.symbols
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)

@router.post("/run-open-base")
async def run_watchlist_simulation_open_base(req: WatchlistSimulationRequest, current_user: str = Depends(get_current_user)):
    """Executes the Open Price Base day trading simulation on the checked watchlist stocks."""
    res = DayTradingService.run_simulation_open_base(
        username=current_user,
        allocated_limit=req.allocated_limit,
        symbols_filter=req.symbols
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)
