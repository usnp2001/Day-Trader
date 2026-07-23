import os
import sys
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from dal.user_watchlist_dao import UserWatchlistDao

client = TestClient(app)

def test_user_watchlist_features():
    print("==================================================")
    print(" STARTING USER WATCHLIST API TESTS")
    print("==================================================")

    # 1. Login as default user
    print("\n[Test 1] Authenticating as User...")
    login_resp = client.post("/api/auth/login", json={
        "username": "user",
        "password": "user123"
    })
    
    # If user doesn't exist, try admin
    if login_resp.status_code != 200:
        print("-> Regular user not found, logging in as admin...")
        login_resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        
    assert login_resp.status_code == 200
    token = login_resp.json()["result"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    username = login_resp.json()["result"]["username"]
    print(f"-> SUCCESS: Logged in as '{username}'.")

    # Clear watchlist before starting
    watchlist_items = UserWatchlistDao.get_watchlist(username)
    if watchlist_items:
        symbols = [item["symbol"] for item in watchlist_items]
        UserWatchlistDao.remove_multiple_from_watchlist(username, symbols)
        print(f"-> Info: Pre-cleared {len(symbols)} items from watchlist.")

    # 2. Add TSMC (2330.TW) to watchlist
    print("\n[Test 2] Adding '2330.TW' to custom watchlist...")
    res_add = client.post("/api/watchlist", json={"symbol": "2330.TW"}, headers=headers)
    assert res_add.status_code == 200
    print("-> SUCCESS:", res_add.json()["message"])

    # 3. Check if '2330.TW' is in watchlist
    print("\n[Test 3] Checking watchlist status for '2330.TW'...")
    res_check = client.get("/api/watchlist/check/2330.TW", headers=headers)
    assert res_check.status_code == 200
    assert res_check.json()["result"]["in_watchlist"] is True
    print("-> SUCCESS: Checked in_watchlist is True.")

    # 4. Try to add invalid stock symbol
    print("\n[Test 4] Adding invalid stock symbol 'INVALID.TW' (should fail)...")
    res_add_invalid = client.post("/api/watchlist", json={"symbol": "INVALID.TW"}, headers=headers)
    assert res_add_invalid.status_code == 400
    print("-> SUCCESS: Denied invalid stock addition with status 400.")

    # 5. Fetch watchlist
    print("\n[Test 5] Fetching entire watchlist...")
    res_get = client.get("/api/watchlist", headers=headers)
    assert res_get.status_code == 200
    items = res_get.json()["result"]
    assert len(items) >= 1
    assert any(i["symbol"] == "2330.TW" for i in items)
    print("-> SUCCESS: Watchlist loaded successfully and contains '2330.TW'.")

    # 6. Delete TSMC (2330.TW) from watchlist
    print("\n[Test 6] Removing '2330.TW' from watchlist...")
    res_del = client.delete("/api/watchlist?symbol=2330.TW", headers=headers)
    assert res_del.status_code == 200
    print("-> SUCCESS:", res_del.json()["message"])

    # Verify empty
    res_get_empty = client.get("/api/watchlist", headers=headers)
    assert res_get_empty.status_code == 200
    assert len(res_get_empty.json()["result"]) == 0
    print("-> SUCCESS: Watchlist is verified empty.")

    print("\n==================================================")
    print(" ALL WATCHLIST API TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_user_watchlist_features()
