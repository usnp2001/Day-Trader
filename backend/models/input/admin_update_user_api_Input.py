from pydantic import BaseModel
from typing import Optional

class AdminUserUpdateRequest(BaseModel):
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_pic: Optional[str] = None
    is_active: int
    cash: float
