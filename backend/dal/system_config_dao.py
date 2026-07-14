from typing import Optional
from common.base_dao import BaseDAO

class SystemConfigDao(BaseDAO):
    @classmethod
    def get_config(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetches the configuration value for the given key."""
        conn = cls.get_connection()
        row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row:
            return row["value"]
        return default

    @classmethod
    def set_config(cls, key: str, value: str):
        """Sets or updates the configuration value for the given key."""
        conn = cls.get_connection()
        conn.execute("""
            INSERT INTO system_config (key, value)
            VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, value))
        conn.commit()
        conn.close()
