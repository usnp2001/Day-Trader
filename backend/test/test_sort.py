# test_sort.py - Verification script for Stock sorting functionality
import os
import sys

# Add backend to python path if run from test directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_sorting():
    print("==================================================")
    print(" STARTING SCREENER SORTING VERIFICATION TESTS")
    print("==================================================")

    # 1. Authenticate admin user
    login_resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["result"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Test default (unsorted/volume filter)
    print("\n[Test 1] Fetching default list to get baseline...")
    res = client.get("/api/screener/filter", params={"page_size": 10}, headers=headers)
    assert res.status_code == 200
    stocks_default = res.json()["result"]["stocks"]
    print(f"Default list (first 3): {[s['symbol'] for s in stocks_default[:3]]}")

    # 3. Test sort by price descending
    print("\n[Test 2] Testing sorting by price DESC...")
    res_desc = client.get("/api/screener/filter", params={"page_size": 15, "sort_by": "price", "sort_order": "desc"}, headers=headers)
    assert res_desc.status_code == 200
    stocks_desc = res_desc.json()["result"]["stocks"]
    prices_desc = [s["price"] for s in stocks_desc]
    print(f"Prices DESC: {prices_desc}")
    # Assert values are descending (ignoring None values which should be at the end)
    non_none_prices = [p for p in prices_desc if p is not None]
    assert non_none_prices == sorted(non_none_prices, reverse=True)
    print("-> SUCCESS: Prices DESC are correctly ordered!")

    # 4. Test sort by price ascending
    print("\n[Test 3] Testing sorting by price ASC...")
    res_asc = client.get("/api/screener/filter", params={"page_size": 15, "sort_by": "price", "sort_order": "asc"}, headers=headers)
    assert res_asc.status_code == 200
    stocks_asc = res_asc.json()["result"]["stocks"]
    prices_asc = [s["price"] for s in stocks_asc]
    print(f"Prices ASC: {prices_asc}")
    non_none_prices_asc = [p for p in prices_asc if p is not None]
    assert non_none_prices_asc == sorted(non_none_prices_asc)
    print("-> SUCCESS: Prices ASC are correctly ordered!")

    # 5. Test sorting by volume descending
    print("\n[Test 4] Testing sorting by volume DESC...")
    res_vol = client.get("/api/screener/filter", params={"page_size": 10, "sort_by": "volume", "sort_order": "desc"}, headers=headers)
    assert res_vol.status_code == 200
    vols = [s["volume"] for s in res_vol.json()["result"]["stocks"]]
    print(f"Volumes DESC: {vols}")
    assert vols == sorted(vols, reverse=True)
    print("-> SUCCESS: Volumes DESC are correctly ordered!")

    print("\n==================================================")
    print(" ALL SORTING VERIFICATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    test_sorting()
