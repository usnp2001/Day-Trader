import os
import sqlite3
from common.config import (
    DB_TYPE, DB_FILE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
)

# Export standard DB-API exception classes dynamically
if DB_TYPE == "postgres":
    import psycopg2
    import psycopg2.extras
    from psycopg2 import IntegrityError, OperationalError, DatabaseError
else:
    from sqlite3 import IntegrityError, OperationalError, DatabaseError

class CaseInsensitiveRow:
    def __init__(self, row):
        self._row = row

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return self._row[key]
            except KeyError:
                try:
                    return self._row[key.lower()]
                except KeyError:
                    # Fallback lookup: find column matching case-insensitively
                    for k in self._row.keys():
                        if k.lower() == key.lower():
                            return self._row[k]
                    raise KeyError(key)
        return self._row[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self._row.keys()

    def __getattr__(self, name):
        return getattr(self._row, name)

class PGCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def _translate_sql(self, sql):
        # 1. Temporarily protect SQLite placeholders (?)
        sql = sql.replace("?", "__PARAM_PLACEHOLDER__")
        # 2. Escape literal % to %% for PostgreSQL formatting compatibility
        sql = sql.replace("%", "%%")
        # 3. Convert protected placeholders to PostgreSQL format (%s)
        sql = sql.replace("__PARAM_PLACEHOLDER__", "%s")
        
        # Translate SQLite specific UPSERT (INSERT OR REPLACE / REPLACE INTO) to PostgreSQL compatible syntax
        if "INSERT OR REPLACE INTO positions" in sql or "REPLACE INTO positions" in sql:
            sql = """
                INSERT INTO positions (username, symbol, name, qty, buy_price)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (username, symbol)
                DO UPDATE SET name = EXCLUDED.name, qty = EXCLUDED.qty, buy_price = EXCLUDED.buy_price
            """
        elif "INSERT OR REPLACE INTO account" in sql or "REPLACE INTO account" in sql:
            sql = """
                INSERT INTO account (username, cash)
                VALUES (%s, %s)
                ON CONFLICT (username)
                DO UPDATE SET cash = EXCLUDED.cash
            """
        return sql

    def execute(self, sql, params=None):
        sql = self._translate_sql(sql)
        self._cursor.execute(sql, params)
        return self

    def executemany(self, sql, seq_of_params):
        sql = self._translate_sql(sql)
        self._cursor.executemany(sql, seq_of_params)
        return self

    def fetchone(self):
        r = self._cursor.fetchone()
        if r is not None:
            return CaseInsensitiveRow(r)
        return None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [CaseInsensitiveRow(r) for r in rows]

    def close(self):
        self._cursor.close()

    def __iter__(self):
        for r in self._cursor:
            yield CaseInsensitiveRow(r)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class PGConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        if 'cursor_factory' not in kwargs:
            kwargs['cursor_factory'] = psycopg2.extras.DictCursor
        return PGCursorWrapper(self._conn.cursor(*args, **kwargs))

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)

class BaseDAO:
    # Class-level exports for exceptions
    IntegrityError = IntegrityError
    OperationalError = OperationalError
    DatabaseError = DatabaseError

    @staticmethod
    def get_connection():
        """Establishes connection to either SQLite or PostgreSQL database."""
        if DB_TYPE == "postgres":
            import psycopg2
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                dbname=DB_NAME
            )
            return PGConnectionWrapper(conn)
        else:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            return conn
