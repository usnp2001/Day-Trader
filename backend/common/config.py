import os

DB_FILE = os.getenv("DB_FILE", "trading_platform.db")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_trading_platform_key_12345")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidXNucDIwMDEiLCJlbWFpbCI6InVzbnAyMDAxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.Vc5ppWVBZqusn0DXwjM0Ut4ZLnCBFWGusRnBJ9zI00A")
