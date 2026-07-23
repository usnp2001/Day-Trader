import os
import sys
import datetime
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from dal.day_trading_dao import DayTradingDao

client = TestClient(app)

def test_ticks_bridge_features():
    print("==================================================")
    print(" STARTING TICKS BRIDGE API TESTS")
    print("==================================================")

    # 1. Login as admin
    print("\n[Test 1] Authenticating...")
    login_resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["result"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("-> SUCCESS: Logged in.")

    # 2. Insert mock ticks for 2330.TW for today
    print("\n[Test 2] Inserting mock ticks into day_trading_ticks for today...")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Pre-clear ticks
    DayTradingDao.clear_ticks()
    
    mock_ticks = [
        {
            "symbol": "2330.TW",
            "timestamp": "09:00:00",
            "price": 880.0,
            "volume": 5000,
            "tick_type": "OUTER",
            "created_date": today_str
        },
        {
            "symbol": "2330.TW",
            "timestamp": "09:01:00",
            "price": 881.5,
            "volume": 3200,
            "tick_type": "OUTER",
            "created_date": today_str
        }
    ]
    DayTradingDao.insert_ticks(mock_ticks)
    print(f"-> SUCCESS: Inserted 2 mock ticks for 2330.TW with created_date = {today_str}.")

    # 3. Call GET /api/kline/2330.TW?interval=1m and verify it returns our mock ticks!
    print("\n[Test 3] Calling GET /api/kline/2330.TW?interval=1m to verify intercept...")
    res = client.get("/api/kline/2330.TW?interval=1m", headers=headers)
    assert res.status_code == 200
    data = res.json()["result"]["data"]
    
    # Verify it returned exactly our 2 inserted mock ticks
    assert len(data) == 2
    assert data[0]["time"] == "09:00:00"
    assert data[0]["close"] == 880.0
    assert data[0]["volume"] == 5000
    assert data[1]["time"] == "09:01:00"
    assert data[1]["close"] == 881.5
    assert data[1]["volume"] == 3200
    print("-> SUCCESS: Intercept verified. Loaded ticks from day_trading_ticks containing volume successfully!")

    # 4. Clean up ticks
    DayTradingDao.clear_ticks()
    print("-> SUCCESS: Cleaned up day_trading_ticks.")

    print("\n==================================================")
    print(" ALL TICKS BRIDGE API TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_ticks_bridge_features()
