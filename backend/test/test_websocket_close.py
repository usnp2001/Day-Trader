import os
import sys
import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

client = TestClient(app)

def test_websocket_market_stream():
    print("==================================================")
    print(" STARTING WEBSOCKET MARKET STREAM HOURS TESTS")
    print("==================================================")

    # 1. Login as admin to get token
    print("\n[Test 1] Authenticating...")
    login_resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["result"]["access_token"]
    print("-> SUCCESS: Token obtained.")

    # 2. Test websocket when market is closed (e.g. 15:00:00)
    print("\n[Test 2] Testing WebSocket connection after market close (15:00:00)...")
    fake_now_closed = datetime.datetime(2026, 7, 23, 15, 0, 0)
    
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_now_closed
        mock_datetime.time = datetime.time
        
        # Connect to websocket
        url = f"/ws/market/2330.TW?token={token}"
        with client.websocket_connect(url) as ws:
            # Receive one packet
            data = ws.receive_json()
            assert data["is_closed"] is True
            assert data["symbol"] == "2330.TW"
            assert data["time"] == "13:30:00"
            print("-> SUCCESS: Received static final result snapshot with is_closed=True.")

    # 3. Test websocket when market is open (e.g. 10:00:00)
    print("\n[Test 3] Testing WebSocket connection during active hours (10:00:00)...")
    fake_now_open = datetime.datetime(2026, 7, 23, 10, 0, 0)
    
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_now_open
        mock_datetime.time = datetime.time
        
        url = f"/ws/market/2330.TW?token={token}"
        with client.websocket_connect(url) as ws:
            # Receive first packet
            data1 = ws.receive_json()
            assert data1["is_closed"] is False
            assert "price" in data1
            
            # Receive second packet
            data2 = ws.receive_json()
            assert data2["is_closed"] is False
            print(f"-> SUCCESS: Received dynamic ticks: Tick 1={data1['price']}, Tick 2={data2['price']}.")

    print("\n==================================================")
    print(" ALL WEBSOCKET STREAM HOURS TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    test_websocket_market_stream()
