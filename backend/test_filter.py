# test_filter.py - Verification script for Stock Screening and Autocomplete APIs

from fastapi.testclient import TestClient
import os
import sys

# Add backend to python path if run from root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import DBStore

client = TestClient(app)

def test_screener_features():
    print("==================================================")
    print(" STARTING SCREENER FILTER & AUTOCOMPLETE TESTS")
    print("==================================================")

    # 1. Test Autocomplete Search API
    print("\n[Test 1] Testing Autocomplete Search Fuzzy Query...")
    # Query '台' (should match 台積電, 台達電)
    res_tw = client.get("/api/stocks/search?query=台")
    assert res_tw.status_code == 200
    json_tw = res_tw.json()
    assert json_tw["status"] == "success"
    results_tw = json_tw["results"]
    print(f"-> SUCCESS: Found {len(results_tw)} matches for query '台'")
    for r in results_tw:
        print(f"   Match: {r['name']} ({r['symbol']})")
    assert any(x["name"] == "台積電" for x in results_tw)

    # Query 'NV' (should match NVDA)
    res_us = client.get("/api/stocks/search?query=NV")
    assert res_us.status_code == 200
    json_us = res_us.json()
    assert json_us["status"] == "success"
    results_us = json_us["results"]
    print(f"-> SUCCESS: Found {len(results_us)} matches for query 'NV'")
    for r in results_us:
        print(f"   Match: {r['name']} ({r['symbol']})")
    assert any(x["symbol"] == "NVDA" for x in results_us)

    # 2. Test Multi-Conditional Stock Filter API
    print("\n[Test 2] Testing Stock Filtering (Price: 100~500, Min Volume: 10000, PE <= 30)...")
    filter_params = {
        "price_min": 100.0,
        "price_max": 500.0,
        "min_volume": 10000,
        "pe_max": 30.0,
        "ma_bullish": False,
        "page": 1,
        "page_size": 5
    }
    res_filter = client.get("/api/screener/filter", params=filter_params)
    assert res_filter.status_code == 200
    json_filter = res_filter.json()
    assert json_filter["status"] == "success"
    stocks = json_filter["stocks"]
    total_pages = json_filter["total_pages"]
    total_count = json_filter["total_count"]
    
    print(f"-> SUCCESS: Found {total_count} stocks matching conditions (showing page 1/{total_pages})")
    for s in stocks:
        print(f"   Stock: {s['name']} ({s['symbol']}) | Price={s['price']} | Vol={s['volume']} | PE={s['pe_ratio']}")
        assert s["price"] >= 100.0 and s["price"] <= 500.0
        assert s["volume"] >= 10000
        assert s["pe_ratio"] is None or s["pe_ratio"] <= 30.0

    # 3. Test Moving Average Bullish Alignment Filter
    print("\n[Test 3] Testing Moving Average Bullish Filter (MA5 > MA20)...")
    res_ma = client.get("/api/screener/filter", params={"ma_bullish": True, "page_size": 20})
    assert res_ma.status_code == 200
    json_ma = res_ma.json()
    ma_stocks = json_ma["stocks"]
    print(f"-> SUCCESS: Found {len(ma_stocks)} stocks with MA5 > MA20 bullish crossovers")
    for s in ma_stocks:
        print(f"   Stock: {s['name']} ({s['symbol']}) | MA5={s['ma5']} | MA20={s['ma20']} | Difference={round(s['ma5'] - s['ma20'], 2)}")
        assert s["ma5"] > s["ma20"]

    # 4. Test Exclude US Stocks Filter
    print("\n[Test 4] Testing Exclude US Stocks Filter (exclude_us = True)...")
    res_no_us = client.get("/api/screener/filter", params={"exclude_us": True, "page_size": 30})
    assert res_no_us.status_code == 200
    json_no_us = res_no_us.json()
    no_us_stocks = json_no_us["stocks"]
    print(f"-> SUCCESS: Found {len(no_us_stocks)} stocks after excluding US markets")
    for s in no_us_stocks:
        print(f"   Stock: {s['name']} ({s['symbol']})")
        assert s["symbol"].endswith(".TW")

    print("\n==================================================")
    print(" ALL FILTER & SEARCH VERIFICATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    test_screener_features()
