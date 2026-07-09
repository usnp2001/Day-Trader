import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from typing import Optional

from model.auth import RegisterRequest, LoginRequest, ProfileUpdateRequest, AdminUserUpdateRequest, CreateUserRequest
from service.user_service import UserService
from controller.dependencies import get_current_user, get_current_admin
from common.config import JWT_SECRET

router = APIRouter(prefix="/api")

@router.post("/auth/register")
async def register(req: RegisterRequest):
    return UserService.register(
        username=req.username,
        password_raw=req.password,
        email=req.email,
        name=req.name,
        phone=req.phone,
        address=req.address,
        profile_pic=req.profile_pic
    )

@router.post("/auth/login")
async def login_api(req: LoginRequest):
    return UserService.login(
        username=req.username,
        password_raw=req.password,
        jwt_secret=JWT_SECRET
    )

@router.post("/upload_avatar")
async def upload_avatar(file: UploadFile = File(...)):
    # Verify file extension (only allow common image extensions)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Allowed: jpg, jpeg, png, gif, webp")
    
    # Define absolute uploads folder inside frontend
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    upload_dir = os.path.join(frontend_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename to avoid duplicates/overwrites
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    return {"status": "success", "avatar_url": f"/uploads/{filename}"}

@router.get("/user/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    return UserService.get_profile(current_user)

@router.put("/user/profile")
async def update_user_profile_api(req: ProfileUpdateRequest, current_user: str = Depends(get_current_user)):
    return UserService.update_profile(
        username=current_user,
        email=req.email,
        name=req.name,
        phone=req.phone,
        address=req.address,
        profile_pic=req.profile_pic,
        password_raw=req.password
    )

@router.get("/admin/users")
async def admin_get_users(current_admin: str = Depends(get_current_admin)):
    return UserService.admin_get_users()

@router.post("/admin/create_user")
async def admin_create_user(req: CreateUserRequest, current_admin: str = Depends(get_current_admin)):
    return UserService.admin_create_user(
        username=req.username,
        password_raw=req.password,
        role=req.role
    )

@router.put("/admin/update_user/{target_username}")
async def admin_update_user_api(
    target_username: str,
    req: AdminUserUpdateRequest,
    current_admin: str = Depends(get_current_admin)
):
    return UserService.admin_update_user(
        current_admin=current_admin,
        target_username=target_username,
        role=req.role,
        email=req.email,
        name=req.name,
        phone=req.phone,
        address=req.address,
        profile_pic=req.profile_pic,
        is_active=req.is_active,
        cash=req.cash
    )

@router.post("/admin/toggle_user/{target_username}")
async def admin_toggle_user(
    target_username: str,
    current_admin: str = Depends(get_current_admin)
):
    return UserService.admin_toggle_user(current_admin, target_username)

@router.delete("/admin/delete_user/{target_username}")
async def admin_delete_user(
    target_username: str,
    current_admin: str = Depends(get_current_admin)
):
    return UserService.admin_delete_user(current_admin, target_username)
