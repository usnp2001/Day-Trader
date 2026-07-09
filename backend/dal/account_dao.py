from typing import Optional
from common.base_dao import BaseDAO

class AccountDao(BaseDAO):
    @classmethod
    def get_cash(cls, username: str) -> float:
        conn = cls.get_connection()
        row = conn.execute("SELECT cash FROM account WHERE username = ?", (username,)).fetchone()
        conn.close()
        return row["cash"] if row else 10000000.0

    @classmethod
    def update_cash(cls, username: str, new_cash: float):
        conn = cls.get_connection()
        conn.execute("UPDATE account SET cash = ? WHERE username = ?", (new_cash, username))
        conn.commit()
        conn.close()
