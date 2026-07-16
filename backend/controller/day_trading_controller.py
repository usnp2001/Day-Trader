from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from service.day_trading_service import DayTradingService
from controller.dependencies import get_current_user
from models.output.api_response import ApiResponse

router = APIRouter(prefix="/api/simulation")

class RunSimulationRequest(BaseModel):
    allocated_limit: float = Field(500000.0, description="Allocated budget limit per stock in TWD", ge=1000.0)

@router.post("/import")
async def import_ticks(current_user: str = Depends(get_current_user)):
    """Triggers the import of top 50 volume ticks into the database."""
    res = DayTradingService.import_top_50_ticks()
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)

@router.post("/run")
async def run_simulation(req: RunSimulationRequest, current_user: str = Depends(get_current_user)):
    """Executes the Peak/Trough trading simulation with the given budget allocation limit."""
    res = DayTradingService.run_simulation(username=current_user, allocated_limit=req.allocated_limit)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)

@router.post("/run-open-base")
async def run_simulation_open_base(req: RunSimulationRequest, current_user: str = Depends(get_current_user)):
    """Executes the Open Price Base trading simulation with the given budget allocation limit."""
    res = DayTradingService.run_simulation_open_base(username=current_user, allocated_limit=req.allocated_limit)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return ApiResponse.create(result=res)

@router.get("/results")
async def get_results(current_user: str = Depends(get_current_user)):
    """Retrieves simulation results and overall metrics for the logged-in user."""
    res = DayTradingService.get_simulation_results(username=current_user)
    return ApiResponse.create(result=res)

@router.get("/trades/{symbol}")
async def get_trades(symbol: str, current_user: str = Depends(get_current_user)):
    """Retrieves individual trade logs for a specific stock during the simulation."""
    res = DayTradingService.get_trades_for_stock(username=current_user, symbol=symbol)
    return ApiResponse.create(result={"symbol": symbol, "trades": res})

@router.get("/tick-rules")
async def get_tick_rules(current_user: str = Depends(get_current_user)):
    """Retrieves tick size and breakeven rules from the database."""
    res = DayTradingService.get_tick_rules()
    return ApiResponse.create(result=res)
