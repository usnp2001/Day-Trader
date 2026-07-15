from fastapi import APIRouter, Depends
from models.input.adjust_cash_Input import CashAdjustmentRequest
from service.account_service import AccountService
from controller.dependencies import get_current_user

router = APIRouter(prefix="/api")

@router.post("/account/adjust_cash")
async def adjust_cash(req: CashAdjustmentRequest, current_user: str = Depends(get_current_user)):
    return AccountService.adjust_cash(current_user, req.cash)

@router.get("/inventory")
async def get_inventory(current_user: str = Depends(get_current_user)):
    return AccountService.get_inventory_summary(current_user)
