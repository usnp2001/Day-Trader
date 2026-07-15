from pydantic import BaseModel

class ConfigUpdateRequest(BaseModel):
    wearn_excel_url: str
    wearn_cookies: str
