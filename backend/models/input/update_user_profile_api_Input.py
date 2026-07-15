from pydantic import BaseModel
from typing import Optional

class ProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_pic: Optional[str] = None
    password: Optional[str] = None
