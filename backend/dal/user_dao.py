import sqlite3
from typing import Dict, List, Any, Optional
from common.base_dao import BaseDAO

class UserDao(BaseDAO):
    @classmethod
    def get_user(cls, username: str) -> Optional[Dict[str, Any]]:
        conn = cls.get_connection()
        row = conn.execute("""
            SELECT username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active 
            FROM users 
            WHERE username = ?
        """, (username,)).fetchone()
        conn.close()
        if row:
            return {
                "username": row["username"],
                "hashed_password": row["hashed_password"],
                "salt": row["salt"],
                "role": row["role"],
                "email": row["email"],
                "name": row["name"],
                "phone": row["phone"],
                "address": row["address"],
                "profile_pic": row["profile_pic"],
                "is_active": row["is_active"]
            }
        return None

    @classmethod
    def create_user(
        cls,
        username: str, 
        hashed_password: str, 
        salt: str, 
        role: str = "user",
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: int = 1
    ) -> bool:
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active))
            cursor.execute("""
                INSERT INTO account (username, cash)
                VALUES (?, 10000000.0)
            """, (username,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @classmethod
    def update_user_profile(
        cls,
        username: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        hashed_password: Optional[str] = None,
        salt: Optional[str] = None
    ) -> bool:
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            query = "UPDATE users SET email = ?, name = ?, phone = ?, address = ?, profile_pic = ?"
            params = [email, name, phone, address, profile_pic]
            if hashed_password and salt:
                query += ", hashed_password = ?, salt = ?"
                params.extend([hashed_password, salt])
            query += " WHERE username = ?"
            params.append(username)
            cursor.execute(query, params)
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @classmethod
    def admin_update_user(
        cls,
        username: str,
        role: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: int = 1,
        cash: float = 10000000.0
    ) -> bool:
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users 
                SET role = ?, email = ?, name = ?, phone = ?, address = ?, profile_pic = ?, is_active = ?
                WHERE username = ?
            """, (role, email, name, phone, address, profile_pic, is_active, username))
            cursor.execute("""
                INSERT OR REPLACE INTO account (username, cash)
                VALUES (?, ?)
            """, (username, cash))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @classmethod
    def get_all_users(cls) -> List[Dict[str, Any]]:
        conn = cls.get_connection()
        rows = conn.execute("""
            SELECT u.username, u.role, u.email, u.name, u.phone, u.address, u.profile_pic, u.is_active, COALESCE(a.cash, 0.0) as cash
            FROM users u
            LEFT JOIN account a ON u.username = a.username
        """).fetchall()
        conn.close()
        return [{
            "username": r["username"],
            "role": r["role"],
            "email": r["email"],
            "name": r["name"],
            "phone": r["phone"],
            "address": r["address"],
            "profile_pic": r["profile_pic"],
            "is_active": r["is_active"],
            "cash": r["cash"]
        } for r in rows]

    @classmethod
    def delete_user(cls, username: str) -> bool:
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            cursor.execute("DELETE FROM account WHERE username = ?", (username,))
            cursor.execute("DELETE FROM positions WHERE username = ?", (username,))
            cursor.execute("DELETE FROM orders WHERE username = ?", (username,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @classmethod
    def toggle_user_active(cls, username: str, new_status: int) -> bool:
        conn = cls.get_connection()
        try:
            conn.execute("UPDATE users SET is_active = ? WHERE username = ?", (new_status, username))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
