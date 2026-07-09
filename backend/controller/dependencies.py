import time
from fastapi import Header, HTTPException, Depends
from typing import Optional
from common.config import JWT_SECRET
from common.auth_utils import verify_jwt
from dal.user_dao import UserDao

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    payload = verify_jwt(token, JWT_SECRET)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token or session expired")
    
    if "exp" in payload and payload["exp"] < time.time():
        raise HTTPException(status_code=401, detail="Token has expired")
        
    username = payload["sub"]
    # Check if user is active in DB to prevent immediate access of disabled accounts
    user = UserDao.get_user(username)
    if not user or user.get("is_active") == 0:
        raise HTTPException(status_code=403, detail="此帳戶不存在或已被停用。")
        
    return username

async def get_current_admin(current_user: str = Depends(get_current_user)) -> str:
    user = UserDao.get_user(current_user)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Permission denied. Admin role required.")
    return current_user
