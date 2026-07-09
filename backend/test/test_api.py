# test_api.py - Programmatic REST API Verification Test

from fastapi.testclient import TestClient
import os
import sys

# Add backend to python path if run from test directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

client = TestClient(app)

def test_flow():
    print("==================================================")
    print(" STARTING BACKEND TRADING PLATFORM API TESTS")
    print("==================================================")

    # 0. Authenticate admin user
    login_resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test Stock Screener endpoint
    print("\n[Test 1] Fetching Stock Screener List...")
    response = client.get("/api/screener", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    stocks = json_data["data"]
    print(f"-> SUCCESS: Found {len(stocks)} stocks.")
    for idx, s in enumerate(stocks[:3]):
        print(f"   [{idx+1}] {s['name']} ({s['symbol']}): Price={s['price']}, Vol={s['volume']}")

    # 2. Test initial Inventory endpoint
    print("\n[Test 2] Fetching Account Inventory & Summary...")
    response = client.get("/api/inventory", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    summary = json_data["summary"]
    positions = json_data["positions"]
    
    initial_cash = summary["cash"]
    print(f"-> SUCCESS: Initial Cash={initial_cash}, Active Positions Count={len(positions)}")
    for pos in positions:
        print(f"   Position: {pos['name']} ({pos['symbol']}) Qty={pos['qty']} BuyPrice={pos['buy_price']}")

    # 3. Test submitting a BUY order (LIMIT)
    print("\n[Test 3] Submitting BUY order for 1000 shares of TSMC (2330.TW)...")
    buy_req = {
        "symbol": "2330.TW",
        "action": "BUY",
        "price": 900.0,
        "qty": 1000,
        "order_type": "LIMIT"
    }
    response = client.post("/api/order", json=buy_req, headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    order = json_data["order"]
    assert order["status"] == "FILLED"
    assert order["exec_price"] == 900.0
    print(f"-> SUCCESS: Order {order['order_id']} Executed at price {order['exec_price']} for quantity {order['qty']}.")

    # 4. Test updated Inventory & cash persistence
    print("\n[Test 4] Querying Inventory again to verify cash deduction and position update...")
    response = client.get("/api/inventory", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    summary = json_data["summary"]
    positions = json_data["positions"]
    
    new_cash = summary["cash"]
    expected_deduction = 900.0 * 1000
    print(f"   Old Cash: {initial_cash} | New Cash: {new_cash} | Difference: {initial_cash - new_cash}")
    assert abs((initial_cash - new_cash) - expected_deduction) < 0.01
    
    tsmc_pos = next((p for p in positions if p["symbol"] == "2330.TW"), None)
    assert tsmc_pos is not None
    print(f"-> SUCCESS: TSMC position successfully updated to Qty={tsmc_pos['qty']} with average price={tsmc_pos['buy_price']}.")

    # 5. Test Order History endpoint
    print("\n[Test 5] Fetching Order Transaction Log...")
    response = client.get("/api/orders", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    orders = json_data["orders"]
    print(f"-> SUCCESS: Retreived {len(orders)} total orders from history.")
    print(f"   Latest Order: ID={orders[0]['order_id']} | Action={orders[0]['action']} | Symbol={orders[0]['symbol']} | Status={orders[0]['status']}")
    
    print("\n==================================================")
    print(" ALL API VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_flow()
