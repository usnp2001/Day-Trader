import os
import glob
import datetime
import shutil
import sys
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from controller.dependencies import get_current_admin
from dal.system_config_dao import SystemConfigDao
from dal.ace_watchlist_dao import AceWatchlistDao
from models.input.update_ace_config_Input import ConfigUpdateRequest
from models.output import ApiResponse

router = APIRouter(prefix="/api/admin")

@router.get("/ace/config")
async def get_ace_config(current_admin: str = Depends(get_current_admin)):
    try:
        url = SystemConfigDao.get_config("wearn_excel_url")
        cookies = SystemConfigDao.get_config("wearn_cookies")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    # Check if today's file exists (.xlsx or .xls)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists("/app/jobs"):
        downloads_dir = "/app/jobs/downloads"
    else:
        downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "downloads"))
        
    file_path_xlsx = os.path.join(downloads_dir, f"ace_selection_{today_str}.xlsx")
    file_path_xls = os.path.join(downloads_dir, f"ace_selection_{today_str}.xls")
    
    file_name = None
    if os.path.exists(file_path_xlsx):
        file_name = f"ace_selection_{today_str}.xlsx"
    elif os.path.exists(file_path_xls):
        file_name = f"ace_selection_{today_str}.xls"
        
    return ApiResponse.create(result={
        "wearn_excel_url": url or "",
        "wearn_cookies": cookies or "",
        "today_file_exists": file_name is not None,
        "today_file_name": file_name
    })

@router.post("/ace/config")
async def update_ace_config(req: ConfigUpdateRequest, current_admin: str = Depends(get_current_admin)):
    try:
        SystemConfigDao.set_config("wearn_excel_url", req.wearn_excel_url)
        SystemConfigDao.set_config("wearn_cookies", req.wearn_cookies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return ApiResponse.create(message="Configuration updated successfully")

@router.post("/ace/upload")
async def upload_ace_excel(file: UploadFile = File(...), current_admin: str = Depends(get_current_admin)):
    ext = None
    if file.filename.endswith(".xlsx"):
        ext = ".xlsx"
    elif file.filename.endswith(".xls"):
        ext = ".xls"
    else:
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls Excel files are supported")
        
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists("/app/jobs"):
        downloads_dir = "/app/jobs/downloads"
    else:
        downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "downloads"))
        
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, f"ace_selection_{today_str}{ext}")
    
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
        
    return ApiResponse.create(result={
        "message": f"Excel uploaded and parsed successfully. Synced {len(db_symbols)} stocks.",
        "symbols": db_symbols
    })

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
        excel_files = glob.glob(os.path.join(downloads_dir, "*.xlsx")) + glob.glob(os.path.join(downloads_dir, "*.xls"))
        for f in excel_files:
            try:
                os.remove(f)
                deleted_files_count += 1
            except Exception as e:
                # Log but continue
                print(f"Failed to delete file {f}: {e}")
                
    return ApiResponse.create(message=f"Successfully cleared watchlist data and deleted {deleted_files_count} local files.")
