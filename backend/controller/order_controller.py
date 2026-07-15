from fastapi import APIRouter, Depends
from models.input.place_order_Input import OrderRequest
from service.order_service import OrderService
from controller.dependencies import get_current_user

router = APIRouter(prefix="/api")

@router.post("/order")
async def place_order(order_req: OrderRequest, current_user: str = Depends(get_current_user)):
    return OrderService.place_order(
        username=current_user,
        symbol=order_req.symbol,
        action=order_req.action,
        price=order_req.price,
        qty=order_req.qty,
        order_type=order_req.order_type
    )

@router.get("/orders")
async def get_orders(current_user: str = Depends(get_current_user)):
    return OrderService.get_orders(current_user)
