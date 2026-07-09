from pydantic import BaseModel

class CashAdjustmentRequest(BaseModel):
    cash: float
