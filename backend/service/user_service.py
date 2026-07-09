import time
from typing import Dict, List, Any, Optional
from dal.user_dao import UserDao
from common.auth_utils import create_jwt, generate_salt, hash_password
from common.exceptions import ValidationException, AuthenticationException, ResourceNotFoundException, ServiceException

class UserService:
    @classmethod
    def register(cls, username: str, password_raw: str, email: str, name: str, phone: str, address: str, profile_pic: str):
        username = username.strip()
        if not username or len(password_raw) < 6:
            raise ValidationException("Username cannot be empty and password must be at least 6 characters")
            
        if UserDao.get_user(username):
            raise ValidationException("Username is already taken")
            
        salt = generate_salt()
        hashed = hash_password(password_raw, salt)
        
        success = UserDao.create_user(
            username=username,
            hashed_password=hashed,
            salt=salt,
            role="user",
            email=email,
            name=name,
            phone=phone,
            address=address,
            profile_pic=profile_pic,
            is_active=1
        )
        if not success:
            raise ServiceException("Failed to create user account", status_code=500)
            
        return {"status": "success", "message": "Registered successfully"}

    @classmethod
    def login(cls, username: str, password_raw: str, jwt_secret: str):
        username = username.strip()
        user = UserDao.get_user(username)
        if not user:
            raise AuthenticationException("Invalid username or password")
            
        if user.get("is_active") == 0:
            raise AuthorizationException("此帳戶已被停用，請聯絡管理員。")
            
        hashed = hash_password(password_raw, user["salt"])
        if hashed != user["hashed_password"]:
            raise AuthenticationException("Invalid username or password")
            
        payload = {
            "sub": user["username"],
            "role": user["role"],
            "exp": int(time.time()) + 86400
        }
        token = create_jwt(payload, jwt_secret)
        
        return {
            "status": "success",
            "access_token": token,
            "username": user["username"],
            "role": user["role"]
        }

    @classmethod
    def get_profile(cls, username: str):
        user = UserDao.get_user(username)
        if not user:
            raise ResourceNotFoundException("User not found")
        return {
            "status": "success",
            "profile": {
                "username": user["username"],
                "role": user["role"],
                "email": user["email"],
                "name": user["name"],
                "phone": user["phone"],
                "address": user["address"],
                "profile_pic": user["profile_pic"]
            }
        }

    @classmethod
    def update_profile(cls, username: str, email: str, name: str, phone: str, address: str, profile_pic: str, password_raw: Optional[str]):
        user = UserDao.get_user(username)
        if not user:
            raise ResourceNotFoundException("User not found")
            
        hashed_pwd = None
        salt = None
        if password_raw:
            if len(password_raw) < 6:
                raise ValidationException("Password must be at least 6 characters")
            salt = generate_salt()
            hashed_pwd = hash_password(password_raw, salt)
            
        success = UserDao.update_user_profile(
            username=username,
            email=email,
            name=name,
            phone=phone,
            address=address,
            profile_pic=profile_pic,
            hashed_password=hashed_pwd,
            salt=salt
        )
        if not success:
            raise ServiceException("Failed to update profile", status_code=500)
            
        return {"status": "success", "message": "Profile updated successfully"}

    @classmethod
    def admin_get_users(cls):
        return {"status": "success", "users": UserDao.get_all_users()}

    @classmethod
    def admin_create_user(cls, username: str, password_raw: str, role: str):
        username = username.strip()
        if not username or len(password_raw) < 6:
            raise ValidationException("Username cannot be empty and password must be at least 6 characters")
        if role not in ["admin", "user"]:
            raise ValidationException("Invalid role. Must be 'admin' or 'user'")
            
        if UserDao.get_user(username):
            raise ValidationException("Username is already taken")
            
        salt = generate_salt()
        hashed = hash_password(password_raw, salt)
        
        success = UserDao.create_user(username, hashed, salt, role=role)
        if not success:
            raise ServiceException("Failed to create user account", status_code=500)
            
        return {"status": "success", "message": f"User '{username}' created successfully as '{role}'"}

    @classmethod
    def admin_update_user(cls, current_admin: str, target_username: str, role: str, email: str, name: str, phone: str, address: str, profile_pic: str, is_active: int, cash: float):
        if target_username == current_admin and is_active == 0:
            raise ValidationException("Cannot disable your own admin account")
            
        success = UserDao.admin_update_user(
            username=target_username,
            role=role,
            email=email,
            name=name,
            phone=phone,
            address=address,
            profile_pic=profile_pic,
            is_active=is_active,
            cash=cash
        )
        if not success:
            raise ServiceException("Failed to update user details", status_code=500)
            
        return {"status": "success", "message": f"User '{target_username}' updated successfully"}

    @classmethod
    def admin_toggle_user(cls, current_admin: str, target_username: str):
        if target_username == current_admin:
            raise ValidationException("Cannot toggle your own admin account status")
            
        user = UserDao.get_user(target_username)
        if not user:
            raise ResourceNotFoundException("User not found")
            
        new_status = 0 if user["is_active"] == 1 else 1
        success = UserDao.toggle_user_active(target_username, new_status)
        if not success:
            raise ServiceException("Failed to toggle user status", status_code=500)
            
        status_str = "啟用" if new_status == 1 else "停用"
        return {"status": "success", "message": f"使用者已{status_str}"}

    @classmethod
    def admin_delete_user(cls, current_admin: str, target_username: str):
        if target_username == current_admin:
            raise ValidationException("Cannot delete your own admin account")
            
        user = UserDao.get_user(target_username)
        if not user:
            raise ResourceNotFoundException("User not found")
            
        success = UserDao.delete_user(target_username)
        if not success:
            raise ServiceException("Failed to delete user account", status_code=500)
            
        return {"status": "success", "message": f"User '{target_username}' deleted successfully"}
