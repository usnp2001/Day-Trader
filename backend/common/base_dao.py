import sqlite3
from common.config import DB_FILE

class BaseDAO:
    @staticmethod
    def get_connection():
        """Establishes connection to the SQLite database."""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn
