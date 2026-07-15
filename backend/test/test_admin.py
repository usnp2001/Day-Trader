import os
import sys
import io
import pandas as pd
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from dal.system_config_dao import SystemConfigDao
from dal.ace_watchlist_dao import AceWatchlistDao

client = TestClient(app)

def test_admin_ace_features():
    print("==================================================")
    print(" STARTING ADMIN ACE WATCHLIST API TESTS")
    print("==================================================")

    # 1. Login as admin
    print("\n[Test 1] Authenticating as Admin...")
    login_resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("-> SUCCESS: Logged in.")

    # 2. Get Config
    print("\n[Test 2] Getting current Ace Config...")
    res_get = client.get("/api/admin/ace/config", headers=headers)
    assert res_get.status_code == 200
    json_get = res_get.json()
    assert json_get["status"] == "success"
    print(f"-> SUCCESS: Current URL: '{json_get['wearn_excel_url']}'")

    # 3. Update Config
    print("\n[Test 3] Updating Ace Config...")
    new_url = "https://wearn.com/strategy/excel_test.xlsx"
    new_cookies = "session=test_cookie_123"
    res_post = client.post("/api/admin/ace/config", json={
        "wearn_excel_url": new_url,
        "wearn_cookies": new_cookies
    }, headers=headers)
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "success"
    
    # Verify in DB
    assert SystemConfigDao.get_config("wearn_excel_url") == new_url
    assert SystemConfigDao.get_config("wearn_cookies") == new_cookies
    print("-> SUCCESS: Config updated in database.")

    # 4. Upload Excel
    print("\n[Test 4] Uploading mock Excel file...")
    # Create an Excel in memory using pandas and io.BytesIO
    mock_data = {
        "股票代號": ["2330", "2317", "2454"],
        "股票名稱": ["台積電", "鴻海", "聯發科"]
    }
    df = pd.DataFrame(mock_data)
    excel_io = io.BytesIO()
    with pd.ExcelWriter(excel_io, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    excel_io.seek(0)
    
    files = {"file": ("mock_ace.xlsx", excel_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res_upload = client.post("/api/admin/ace/upload", files=files, headers=headers)
    assert res_upload.status_code == 200
    json_upload = res_upload.json()
    assert json_upload["status"] == "success"
    assert len(json_upload["symbols"]) == 3
    print(f"-> SUCCESS: Uploaded Excel. Synced symbols: {json_upload['symbols']}")

    # Check watchlist in DB
    db_symbols = AceWatchlistDao.get_all_symbols()
    assert len(db_symbols) == 3
    assert "2330.TW" in db_symbols
    print(f"-> SUCCESS: Database updated with symbols: {db_symbols}")

    # 5. Clear Watchlist & Files
    print("\n[Test 5] Clearing Ace watchlist and cached files...")
    res_clear = client.delete("/api/admin/ace/clear", headers=headers)
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "success"
    
    # Check DB is cleared
    db_symbols_cleared = AceWatchlistDao.get_all_symbols()
    assert len(db_symbols_cleared) == 0
    
    # Reset config in database back to empty so it doesn't break background job runs
    SystemConfigDao.set_config("wearn_excel_url", "")
    SystemConfigDao.set_config("wearn_cookies", "")
    print("-> SUCCESS: Watchlist cleared.")

    # 6. Unauthorized access check
    print("\n[Test 6] Verifying non-admin access is blocked...")
    res_unauth = client.get("/api/admin/ace/config")
    assert res_unauth.status_code == 401 # Missing token
    
    # Login as regular user (checking unauthorized directly)
    login_user_resp = client.post("/api/auth/login", json={
        "username": "user",
        "password": "user123"
    })
    if login_user_resp.status_code == 200:
        user_token = login_user_resp.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        res_forbidden = client.get("/api/admin/ace/config", headers=user_headers)
        assert res_forbidden.status_code == 403 # Forbidden for non-admin
        print("-> SUCCESS: Regular user forbidden as expected.")
    else:
        print("-> INFO: Default user not seeded or login failed, skipping.")

    print("\n==================================================")
    print(" ALL ADMIN ACE API TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_admin_ace_features()
