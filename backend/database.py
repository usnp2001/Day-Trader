import sqlite3
import os
from typing import Dict, List, Any, Optional

DB_FILE = "trading_platform.db"

def get_db_connection():
    """Establishes connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Account table (stores cash balance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            cash REAL NOT NULL
        )
    """)
    
    # Check if cash exists, if not, insert default $10,000,000 NTD
    cursor.execute("SELECT COUNT(*) FROM account")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO account (id, cash) VALUES (1, 10000000.0)")
        
    # 2. Positions table (portfolio inventory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            buy_price REAL NOT NULL
        )
    """)
    
    # Seed default positions if database is empty
    cursor.execute("SELECT COUNT(*) FROM positions")
    if cursor.fetchone()[0] == 0:
        default_positions = [
            ("2330.TW", "台積電", 2000, 890.0),
            ("2317.TW", "鴻海", 5000, 180.0),
            ("2454.TW", "聯發科", 1000, 1200.0),
            ("AAPL", "AAPL", 100, 205.0)
        ]
        for symbol, name, qty, buy_price in default_positions:
            cursor.execute(
                "INSERT INTO positions (symbol, name, qty, buy_price) VALUES (?, ?, ?, ?)",
                (symbol, name, qty, buy_price)
            )

    # 3. Orders table (transaction history)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            qty INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            status TEXT NOT NULL,
            exec_price REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # 4. Stock Metadata Cache Table (For fast screening and autocomplete searching)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_metadata (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            change REAL NOT NULL,
            change_percent REAL NOT NULL,
            volume INTEGER NOT NULL,
            pe_ratio REAL,
            ma5 REAL,
            ma20 REAL
        )
    """)
    
    # Seed default stock list with realistic stats for offline fallback
    cursor.execute("SELECT COUNT(*) FROM stock_metadata")
    if cursor.fetchone()[0] == 0:
        default_stocks = [
            # Taiwan Stocks (Rise = Red, Fall = Green)
            ("2330.TW", "台積電", 900.0, 5.0, 0.56, 35000, 28.5, 895.0, 880.0),
            ("2317.TW", "鴻海", 180.0, -2.0, -1.10, 85000, 16.2, 182.0, 175.0),
            ("2454.TW", "聯發科", 1200.0, 15.0, 1.27, 4500, 22.1, 1190.0, 1180.0),
            ("2603.TW", "長榮", 160.0, 3.0, 1.91, 25000, 8.5, 158.0, 162.0),
            ("2609.TW", "陽明", 70.0, -0.5, -0.71, 40000, 7.2, 71.0, 73.0),
            ("3231.TW", "緯創", 115.0, 1.0, 0.88, 60000, 18.0, 113.0, 112.0),
            ("2382.TW", "廣達", 280.0, 4.0, 1.45, 32000, 20.5, 275.0, 270.0),
            ("2618.TW", "華航", 23.0, -0.2, -0.86, 95000, 12.1, 23.2, 22.8),
            ("2002.TW", "中鋼", 24.5, 0.1, 0.41, 15000, 25.0, 24.4, 24.6),
            ("2881.TW", "富邦金", 75.0, 0.8, 1.08, 18000, 11.3, 74.2, 73.5),
            ("2882.TW", "國泰金", 56.0, 0.5, 0.90, 22000, 12.5, 55.5, 54.8),
            ("2303.TW", "聯電", 52.0, -0.3, -0.57, 38000, 11.8, 52.2, 51.5),
            ("2308.TW", "台達電", 340.0, 6.0, 1.80, 8000, 26.4, 335.0, 330.0),
            ("2891.TW", "中信金", 35.0, 0.2, 0.57, 45000, 10.2, 34.6, 34.0),
            ("2610.TW", "長榮航", 36.0, -0.4, -1.10, 70000, 11.5, 36.2, 35.5),
            # US Stocks
            ("AAPL", "Apple", 210.0, 2.5, 1.20, 450000, 31.2, 208.0, 205.0),
            ("NVDA", "NVIDIA", 120.0, -4.2, -3.38, 2500000, 65.4, 122.0, 118.0),
            ("TSLA", "Tesla", 180.0, -1.5, -0.83, 850000, 50.2, 182.0, 185.0),
            ("MSFT", "Microsoft", 420.0, 3.0, 0.72, 210000, 35.5, 418.0, 415.0),
            ("AMD", "AMD", 160.0, 1.8, 1.14, 350000, 42.1, 158.0, 161.0),
            ("AMZN", "Amazon", 185.0, 2.0, 1.09, 280000, 40.5, 183.0, 180.0),
            ("GOOGL", "Alphabet", 175.0, 1.2, 0.69, 190000, 24.8, 173.0, 171.0),
            ("META", "Meta", 490.0, 8.5, 1.77, 150000, 27.2, 482.0, 475.0),
            ("NFLX", "Netflix", 640.0, 5.0, 0.79, 40000, 38.4, 632.0, 620.0),
            ("INTEL", "Intel", 30.0, -0.5, -1.64, 500000, 32.0, 30.5, 31.2)
        ]
        cursor.executemany("""
            INSERT INTO stock_metadata (symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_stocks)
    
    conn.commit()
    conn.close()
    print("[Database] Schema initialized successfully.")


class DBStore:
    """Helper class to query and write details to SQLite."""
    
    @staticmethod
    def get_cash() -> float:
        conn = get_db_connection()
        row = conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        conn.close()
        return row["cash"] if row else 10000000.0

    @staticmethod
    def update_cash(new_cash: float):
        conn = get_db_connection()
        conn.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_positions() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        rows = conn.execute("SELECT symbol, name, qty, buy_price FROM positions WHERE qty != 0").fetchall()
        conn.close()
        
        positions = []
        for r in rows:
            positions.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "qty": r["qty"],
                "buy_price": r["buy_price"],
                "current_price": r["buy_price"], # Default current price to buy price initially
                "market_value": r["qty"] * r["buy_price"],
                "unrealized_pnl": 0.0,
                "pnl_percent": 0.0
            })
        return positions

    @staticmethod
    def update_position(symbol: str, name: str, qty: int, buy_price: float):
        conn = get_db_connection()
        if qty == 0:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO positions (symbol, name, qty, buy_price)
                VALUES (?, ?, ?, ?)
            """, (symbol, name, qty, buy_price))
        conn.commit()
        conn.close()

    @staticmethod
    def add_order(order: Dict[str, Any]):
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO orders (order_id, symbol, action, price, qty, order_type, status, exec_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["order_id"],
            order["symbol"],
            order["action"],
            order["price"],
            order["qty"],
            order["order_type"],
            order["status"],
            order["exec_price"],
            order["timestamp"]
        ))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_orders() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        rows = conn.execute("SELECT order_id, symbol, action, price, qty, order_type, status, exec_price, timestamp FROM orders ORDER BY rowid DESC").fetchall()
        conn.close()
        
        orders = []
        for r in rows:
            orders.append({
                "order_id": r["order_id"],
                "symbol": r["symbol"],
                "action": r["action"],
                "price": r["price"],
                "qty": r["qty"],
                "order_type": r["order_type"],
                "status": r["status"],
                "exec_price": r["exec_price"],
                "timestamp": r["timestamp"]
            })
        return orders

    # ==========================================
    # METADATA SCREENING & SEARCH QUERIES
    # ==========================================

    @staticmethod
    def search_stocks(query: str) -> List[Dict[str, Any]]:
        """Returns fuzzy matches (max 10) by symbol or name for autocomplete suggestions."""
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT symbol, name FROM stock_metadata
            WHERE symbol LIKE ? OR name LIKE ?
            LIMIT 10
        """, (f"%{query}%", f"%{query}%")).fetchall()
        conn.close()
        return [{"symbol": r["symbol"], "name": r["name"]} for r in rows]

    @staticmethod
    def filter_stocks(
        price_min: float = 0.0,
        price_max: float = 999999.0,
        min_volume: int = 0,
        pe_max: float = 999999.0,
        ma_bullish: bool = False,
        exclude_us: bool = False
    ) -> List[Dict[str, Any]]:
        """Query and filter stocks based on technical and fundamental criteria."""
        conn = get_db_connection()
        query = """
            SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20
            FROM stock_metadata
            WHERE price >= ? AND price <= ? AND volume >= ? AND (pe_ratio IS NULL OR pe_ratio <= ?)
        """
        params = [price_min, price_max, min_volume, pe_max]
        
        if ma_bullish:
            query += " AND ma5 > ma20"
            
        if exclude_us:
            query += " AND symbol LIKE '%.TW'"
            
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "price": r["price"],
                "change": r["change"],
                "change_percent": r["change_percent"],
                "volume": r["volume"],
                "pe_ratio": r["pe_ratio"],
                "ma5": r["ma5"],
                "ma20": r["ma20"]
            })
        return stocks

    @staticmethod
    def update_stock_metadata(stocks_list: List[Dict[str, Any]]):
        """Updates or inserts stock details in bulk (used by backend crawlers)."""
        conn = get_db_connection()
        cursor = conn.cursor()
        for s in stocks_list:
            cursor.execute("""
                INSERT INTO stock_metadata (symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    price=excluded.price,
                    change=excluded.change,
                    change_percent=excluded.change_percent,
                    volume=excluded.volume,
                    pe_ratio=COALESCE(excluded.pe_ratio, pe_ratio),
                    ma5=COALESCE(excluded.ma5, ma5),
                    ma20=COALESCE(excluded.ma20, ma20)
            """, (
                s["symbol"], s["name"], s.get("price", 0.0), s.get("change", 0.0), s.get("change_percent", 0.0),
                s.get("volume", 0), s.get("pe_ratio"), s.get("ma5"), s.get("ma20")
            ))
        conn.commit()
        conn.close()

# Initialize database on module import
init_db()
