from fastapi import APIRouter, Depends, Query
from service.stock_service import StockService
from controller.dependencies import get_current_user, get_current_admin

router = APIRouter(prefix="/api")

@router.get("/screener")
async def get_screener(current_user: str = Depends(get_current_user)):
    return {"status": "success", "data": StockService.get_all_raw_stocks()}

@router.get("/screener/filter")
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
    return StockService.filter_stocks(
        price_min=price_min,
        price_max=price_max,
        min_volume=min_volume,
        pe_max=pe_max,
        ma_bullish=ma_bullish,
        exclude_us=exclude_us,
        page=page,
        page_size=page_size
    )

@router.get("/screener/ace")
async def ace_screener(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    current_user: str = Depends(get_current_user)
):
    return StockService.get_ace_stocks(page=page, page_size=page_size)

@router.get("/stocks/search")
async def search_stocks(query: str = Query("", min_length=1), current_user: str = Depends(get_current_user)):
    return {"status": "success", "results": StockService.search_stocks(query)}

@router.get("/kline/{symbol}")
async def get_kline(symbol: str, interval: str = Query("1d"), current_user: str = Depends(get_current_user)):
    data = StockService.get_kline_data(symbol, interval)
    return {"status": "success", "symbol": symbol, "interval": interval, "data": data}

@router.post("/admin/sync_finmind", status_code=202)
async def admin_sync_finmind(current_admin: str = Depends(get_current_admin)):
    return StockService.trigger_finmind_sync(current_admin)

@router.post("/admin/sync_yfinance", status_code=202)
async def admin_sync_yfinance(current_admin: str = Depends(get_current_admin)):
    return StockService.trigger_yfinance_sync(current_admin)

@router.post("/admin/sync_official", status_code=202)
async def admin_sync_official(current_admin: str = Depends(get_current_admin)):
    return StockService.trigger_official_sync(current_admin)

@router.get("/screener/ai")
async def ai_screener(current_user: str = Depends(get_current_user)):
    return StockService.get_ai_predictions()
