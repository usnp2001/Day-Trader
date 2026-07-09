import base64
import json
import hmac
import hashlib
import time
import uuid
from typing import Optional

def base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def base64url_decode(data: str) -> bytes:
    """Decode base64url string back to bytes, adding padding if necessary."""
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def create_jwt(payload: dict, secret: str, expires_in_seconds: int = 86400) -> str:
    """Creates a signed JWT token with an expiration timestamp."""
    current_time = int(time.time())
    payload = payload.copy()
    if "exp" not in payload:
        payload["exp"] = current_time + expires_in_seconds
    if "iat" not in payload:
        payload["iat"] = current_time

    header = {"alg": "HS256", "typ": "JWT"}
    
    header_json = json.dumps(header, separators=(',', ':'))
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    header_b64 = base64url_encode(header_json.encode('utf-8'))
    payload_b64 = base64url_encode(payload_json.encode('utf-8'))
    
    signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), signature_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_jwt(token: str, secret: str) -> Optional[dict]:
    """Verifies a signed JWT token. Returns payload if valid, otherwise None."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_signature = hmac.new(secret.encode('utf-8'), signature_input, hashlib.sha256).digest()
        expected_signature_b64 = base64url_encode(expected_signature)
        
        if not hmac.compare_digest(signature_b64.encode('utf-8'), expected_signature_b64.encode('utf-8')):
            return None
            
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        current_time = time.time()
        if "exp" in payload and payload["exp"] < current_time:
            return None
            
        return payload
    except Exception:
        return None

def generate_salt() -> str:
    """Generates a random salt string."""
    return uuid.uuid4().hex

def hash_password(password: str, salt: str) -> str:
    """Hashes a password with a salt using SHA-256."""
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
