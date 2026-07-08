import unittest
import json
from fastapi.testclient import TestClient
import os
import sys

# Adjust import path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import DBStore, init_db
from auth_utils import hash_password, verify_jwt

class TestAuthSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure database is initialized
        init_db()
        cls.client = TestClient(app)

    def test_password_hashing(self):
        # Test hash password
        salt = "test_salt_123"
        pwd = "my_password"
        h1 = hash_password(pwd, salt)
        h2 = hash_password(pwd, salt)
        self.assertEqual(h1, h2)
        self.assertNotEqual(pwd, h1)

    def test_admin_login(self):
        # Login with default admin account
        response = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["role"], "admin")
        self.assertIn("access_token", data)

    def test_unauthorized_access(self):
        # Access protected route without authorization header
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 401)

    def test_admin_create_and_delete_user(self):
        # 1. Login as admin
        login_resp = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Clean up any residual testuser to keep test idempotent
        self.client.delete("/api/admin/delete_user/testuser", headers=headers)

        # 2. Create user via admin API
        create_resp = self.client.post("/api/admin/create_user", json={
            "username": "testuser",
            "password": "testpassword",
            "role": "user"
        }, headers=headers)
        self.assertEqual(create_resp.status_code, 200)
        
        # 3. Verify user can login
        user_login_resp = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
        self.assertEqual(user_login_resp.status_code, 200)
        user_token = user_login_resp.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 4. Verify regular user cannot access admin APIs
        users_list_resp = self.client.get("/api/admin/users", headers=user_headers)
        self.assertEqual(users_list_resp.status_code, 403) # Forbidden

        # 5. Verify user can adjust cash balance
        adjust_resp = self.client.post("/api/account/adjust_cash", json={
            "cash": 8888.88
        }, headers=user_headers)
        self.assertEqual(adjust_resp.status_code, 200)
        self.assertEqual(adjust_resp.json()["cash"], 8888.88)

        # Verify inventory shows the adjusted cash
        inv_resp = self.client.get("/api/inventory", headers=user_headers)
        self.assertEqual(inv_resp.status_code, 200)
        self.assertEqual(inv_resp.json()["summary"]["cash"], 8888.88)

        # 6. Admin deletes user
        del_resp = self.client.delete("/api/admin/delete_user/testuser", headers=headers)
        self.assertEqual(del_resp.status_code, 200)

        # 7. Verify user cannot login anymore
        user_login_failed = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
        self.assertEqual(user_login_failed.status_code, 401)

if __name__ == "__main__":
    unittest.main()
