import os
from dotenv import load_dotenv

# Dynamically resolve backend base directory to make DB_FILE path location-independent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file if present (checks host root and docker app root)
env_paths = [
    os.path.join(os.path.dirname(BASE_DIR), ".env"), # Host root
    os.path.join(BASE_DIR, ".env")                  # Docker mount root
]
for path in env_paths:
    if os.path.exists(path):
        load_dotenv(path)
        break

# Database connection variables
# DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_TYPE = os.getenv("DB_TYPE", "postgres")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespassword")
DB_NAME = os.getenv("DB_NAME", "trading_platform")
DB_FILE = os.getenv("DB_FILE", os.path.join(BASE_DIR, "trading_platform.db"))

# JWT configurations
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_trading_platform_key_12345")

# API token configurations
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidXNucDIwMDEiLCJlbWFpbCI6InVzbnAyMDAxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.Vc5ppWVBZqusn0DXwjM0Ut4ZLnCBFWGusRnBJ9zI00A")
