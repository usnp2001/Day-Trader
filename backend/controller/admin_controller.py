import os
import glob
import datetime
import shutil
import sys
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from controller.dependencies import get_current_admin
from dal.system_config_dao import SystemConfigDao
from dal.ace_watchlist_dao import AceWatchlistDao
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin")

class ConfigUpdateRequest(BaseModel):
    wearn_excel_url: str
    wearn_cookies: str

@router.get("/ace/config")
async def get_ace_config(current_admin: str = Depends(get_current_admin)):
    try:
        url = SystemConfigDao.get_config("wearn_excel_url")
        cookies = SystemConfigDao.get_config("wearn_cookies")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    # Check if today's file exists
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    # Resolve jobs/downloads path
    if os.path.exists("/app/jobs"):
        downloads_dir = "/app/jobs/downloads"
    else:
        downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "downloads"))
        
    file_path = os.path.join(downloads_dir, f"ace_selection_{today_str}.xlsx")
    today_file_exists = os.path.exists(file_path)
    
    return {
        "status": "success",
        "wearn_excel_url": url or "",
        "wearn_cookies": cookies or "",
        "today_file_exists": today_file_exists,
        "today_file_name": f"ace_selection_{today_str}.xlsx" if today_file_exists else None
    }

@router.post("/ace/config")
async def update_ace_config(req: ConfigUpdateRequest, current_admin: str = Depends(get_current_admin)):
    try:
        SystemConfigDao.set_config("wearn_excel_url", req.wearn_excel_url)
        SystemConfigDao.set_config("wearn_cookies", req.wearn_cookies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return {"status": "success", "message": "Configuration updated successfully"}

@router.post("/ace/upload")
async def upload_ace_excel(file: UploadFile = File(...), current_admin: str = Depends(get_current_admin)):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx Excel files are supported")
        
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists("/app/jobs"):
        downloads_dir = "/app/jobs/downloads"
    else:
        downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "downloads"))
        
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, f"ace_selection_{today_str}.xlsx")
    
    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Dynamically append jobs to path to load process_excel_file
        if os.path.exists("/app/jobs"):
            jobs_dir = "/app/jobs"
        else:
            jobs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs"))
        if jobs_dir not in sys.path:
            sys.path.insert(0, jobs_dir)
            
        from sync_ace_selection import process_excel_file
        db_symbols = process_excel_file(file_path)
        
    except Exception as e:
        # Clean up file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded Excel: {e}")
        
    return {
        "status": "success",
        "message": f"Excel uploaded and parsed successfully. Synced {len(db_symbols)} stocks.",
        "symbols": db_symbols
    }

@router.delete("/ace/clear")
async def clear_ace_data(current_admin: str = Depends(get_current_admin)):
    # 1. Clear database ace_watchlist
    try:
        AceWatchlistDao.clear_watchlist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {e}")
        
    # 2. Delete all downloads
    if os.path.exists("/app/jobs"):
        downloads_dir = "/app/jobs/downloads"
    else:
        downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "downloads"))
        
    deleted_files_count = 0
    if os.path.exists(downloads_dir):
        xlsx_files = glob.glob(os.path.join(downloads_dir, "*.xlsx"))
        for f in xlsx_files:
            try:
                os.remove(f)
                deleted_files_count += 1
            except Exception as e:
                # Log but continue
                print(f"Failed to delete file {f}: {e}")
                
    return {
        "status": "success",
        "message": f"Successfully cleared watchlist data and deleted {deleted_files_count} local files."
    }
