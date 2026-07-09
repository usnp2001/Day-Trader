import sqlite3
import os
from typing import Dict, List, Any, Optional
from logger import logger

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
    
    # Check if database needs migration from single-user to multi-user
    # We do this by checking if the 'account' table has a 'username' column
    needs_migration = False
    try:
        # Check if table exists
        cursor.execute("SELECT * FROM sqlite_master WHERE type='table' AND name='account'")
        table_exists = cursor.fetchone()
        if table_exists:
            cursor.execute("SELECT username FROM account LIMIT 1")
    except sqlite3.OperationalError:
        needs_migration = True

    if needs_migration:
        logger.warning("[Database] Old single-user schema detected. Migrating to multi-user schema...")
        cursor.execute("DROP TABLE IF EXISTS account")
        cursor.execute("DROP TABLE IF EXISTS positions")
        cursor.execute("DROP TABLE IF EXISTS orders")

    # 1. Users table (stores user accounts and credentials)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            email TEXT,
            name TEXT,
            phone TEXT,
            address TEXT,
            profile_pic TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # Run database migration to add new columns if they do not exist
    for col, col_type in [
        ("email", "TEXT"), 
        ("name", "TEXT"), 
        ("phone", "TEXT"), 
        ("address", "TEXT"), 
        ("profile_pic", "TEXT"), 
        ("is_active", "INTEGER DEFAULT 1")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists

    # 2. Account table (stores cash balance per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account (
            username TEXT PRIMARY KEY,
            cash REAL NOT NULL
        )
    """)
    
    # 3. Positions table (portfolio inventory per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            username TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            PRIMARY KEY (username, symbol)
        )
    """)

    # 4. Orders table (transaction history per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
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

    # 5. Stock Metadata Cache Table (For fast screening and autocomplete searching)
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
            ma20 REAL,
            stockId INTEGER DEFAULT 0
        )
    """)
    
    # Try to add stockId column if it doesn't exist (migration for existing databases)
    try:
        cursor.execute("ALTER TABLE stock_metadata ADD COLUMN stockId INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Run database migration to add new stock_metadata columns if they do not exist
    for col, col_type in [
        ("pb_ratio", "REAL"),
        ("dividend_yield", "REAL"),
        ("foreign_net_buy", "INTEGER"),
        ("trust_net_buy", "INTEGER"),
        ("dealer_net_buy", "INTEGER"),
        ("margin_balance", "INTEGER"),
        ("short_balance", "INTEGER"),
        ("revenue_yoy", "REAL")
    ]:
        try:
            cursor.execute(f"ALTER TABLE stock_metadata ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists
    
    # Remove old 'INTEL' symbol if it exists to clean up
    cursor.execute("DELETE FROM stock_metadata WHERE symbol = 'INTEL'")

    # Seed default user if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import hashlib
        import uuid
        
        # 1. Create admin user (admin / admin123)
        admin_username = "admin"
        admin_password = "admin123"
        admin_salt = uuid.uuid4().hex
        admin_hashed = hashlib.sha256((admin_password + admin_salt).encode('utf-8')).hexdigest()
        
        cursor.execute("""
            INSERT INTO users (username, hashed_password, salt, role)
            VALUES (?, ?, ?, 'admin')
        """, (admin_username, admin_hashed, admin_salt))
        
        # 2. Initialize admin account cash
        cursor.execute("INSERT INTO account (username, cash) VALUES (?, 10000000.0)", (admin_username,))
        
        # 3. Seed default positions for admin
        default_positions = [
            ("2330.TW", "台積電", 2000, 890.0),
            ("2317.TW", "鴻海", 5000, 180.0),
            ("2454.TW", "聯發科", 1000, 1200.0),
            ("AAPL", "AAPL", 100, 205.0)
        ]
        for symbol, name, qty, buy_price in default_positions:
            cursor.execute("""
                INSERT INTO positions (username, symbol, name, qty, buy_price)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_username, symbol, name, qty, buy_price))
    
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
            ("INTC", "Intel", 30.0, -0.5, -1.64, 500000, 32.0, 30.5, 31.2)
        ]
        
        # Add stockId values dynamically
        default_stocks_with_id = []
        for row in default_stocks:
            sym = row[0]
            if sym.endswith(".TW") or sym.endswith(".TWO"):
                try:
                    s_id = int(sym.split(".")[0])
                except ValueError:
                    s_id = 0
            else:
                s_id = 0
            default_stocks_with_id.append(row + (s_id,))

        cursor.executemany("""
            INSERT INTO stock_metadata (symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_stocks_with_id)
    
    conn.commit()
    conn.close()
    logger.info("[Database] Schema initialized successfully.")


class DBStore:
    """Helper class to query and write details to SQLite."""
    
    @staticmethod
    def get_user(username: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active 
            FROM users 
            WHERE username = ?
        """, (username,)).fetchone()
        conn.close()
        if row:
            return {
                "username": row["username"],
                "hashed_password": row["hashed_password"],
                "salt": row["salt"],
                "role": row["role"],
                "email": row["email"],
                "name": row["name"],
                "phone": row["phone"],
                "address": row["address"],
                "profile_pic": row["profile_pic"],
                "is_active": row["is_active"]
            }
        return None

    @staticmethod
    def create_user(
        username: str, 
        hashed_password: str, 
        salt: str, 
        role: str = "user",
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: int = 1
    ) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, hashed_password, salt, role, email, name, phone, address, profile_pic, is_active))
            cursor.execute("""
                INSERT INTO account (username, cash)
                VALUES (?, 10000000.0)
            """, (username,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def update_user_profile(
        username: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        hashed_password: Optional[str] = None,
        salt: Optional[str] = None
    ) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            query = "UPDATE users SET email = ?, name = ?, phone = ?, address = ?, profile_pic = ?"
            params = [email, name, phone, address, profile_pic]
            if hashed_password and salt:
                query += ", hashed_password = ?, salt = ?"
                params.extend([hashed_password, salt])
            query += " WHERE username = ?"
            params.append(username)
            cursor.execute(query, params)
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def admin_update_user(
        username: str,
        role: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: int = 1,
        cash: float = 10000000.0
    ) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users 
                SET role = ?, email = ?, name = ?, phone = ?, address = ?, profile_pic = ?, is_active = ?
                WHERE username = ?
            """, (role, email, name, phone, address, profile_pic, is_active, username))
            cursor.execute("""
                INSERT OR REPLACE INTO account (username, cash)
                VALUES (?, ?)
            """, (username, cash))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def get_all_users() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT u.username, u.role, u.email, u.name, u.phone, u.address, u.profile_pic, u.is_active, COALESCE(a.cash, 0.0) as cash
            FROM users u
            LEFT JOIN account a ON u.username = a.username
        """).fetchall()
        conn.close()
        return [{
            "username": r["username"],
            "role": r["role"],
            "email": r["email"],
            "name": r["name"],
            "phone": r["phone"],
            "address": r["address"],
            "profile_pic": r["profile_pic"],
            "is_active": r["is_active"],
            "cash": r["cash"]
        } for r in rows]

    @staticmethod
    def delete_user(username: str) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            cursor.execute("DELETE FROM account WHERE username = ?", (username,))
            cursor.execute("DELETE FROM positions WHERE username = ?", (username,))
            cursor.execute("DELETE FROM orders WHERE username = ?", (username,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def get_cash(username: str) -> float:
        conn = get_db_connection()
        row = conn.execute("SELECT cash FROM account WHERE username = ?", (username,)).fetchone()
        conn.close()
        return row["cash"] if row else 10000000.0

    @staticmethod
    def update_cash(username: str, new_cash: float):
        conn = get_db_connection()
        conn.execute("UPDATE account SET cash = ? WHERE username = ?", (new_cash, username))
        conn.commit()
        conn.close()

    @staticmethod
    def get_positions(username: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        rows = conn.execute("SELECT symbol, name, qty, buy_price FROM positions WHERE username = ? AND qty != 0", (username,)).fetchall()
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
    def update_position(username: str, symbol: str, name: str, qty: int, buy_price: float):
        conn = get_db_connection()
        if qty == 0:
            conn.execute("DELETE FROM positions WHERE username = ? AND symbol = ?", (username, symbol))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO positions (username, symbol, name, qty, buy_price)
                VALUES (?, ?, ?, ?, ?)
            """, (username, symbol, name, qty, buy_price))
        conn.commit()
        conn.close()

    @staticmethod
    def add_order(username: str, order: Dict[str, Any]):
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO orders (order_id, username, symbol, action, price, qty, order_type, status, exec_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["order_id"],
            username,
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
    def get_all_orders(username: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        rows = conn.execute("SELECT order_id, symbol, action, price, qty, order_type, status, exec_price, timestamp FROM orders WHERE username = ? ORDER BY rowid DESC", (username,)).fetchall()
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
            SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                   pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
            FROM stock_metadata
            WHERE price >= ? AND price <= ? AND volume >= ? AND (pe_ratio IS NULL OR pe_ratio <= ?)
        """
        params = [price_min, price_max, min_volume, pe_max]
        
        if ma_bullish:
            query += " AND ma5 > ma20"
            
        if exclude_us:
            query += " AND (symbol LIKE '%.TW' OR symbol LIKE '%.TWO')"
            
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
                "ma20": r["ma20"],
                "stockId": r["stockId"],
                "pb_ratio": r["pb_ratio"],
                "dividend_yield": r["dividend_yield"],
                "foreign_net_buy": r["foreign_net_buy"],
                "trust_net_buy": r["trust_net_buy"],
                "dealer_net_buy": r["dealer_net_buy"],
                "margin_balance": r["margin_balance"],
                "short_balance": r["short_balance"],
                "revenue_yoy": r["revenue_yoy"]
            })
        return stocks

    @staticmethod
    def get_stocks_by_symbols(symbols: List[str]) -> List[Dict[str, Any]]:
        """Query and return metadata for a specific list of stock symbols."""
        if not symbols:
            return []
        conn = get_db_connection()
        placeholders = ",".join(["?"] * len(symbols))
        query = f"""
            SELECT symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                   pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
            FROM stock_metadata
            WHERE symbol IN ({placeholders})
        """
        rows = conn.execute(query, symbols).fetchall()
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
                "ma20": r["ma20"],
                "stockId": r["stockId"],
                "pb_ratio": r["pb_ratio"],
                "dividend_yield": r["dividend_yield"],
                "foreign_net_buy": r["foreign_net_buy"],
                "trust_net_buy": r["trust_net_buy"],
                "dealer_net_buy": r["dealer_net_buy"],
                "margin_balance": r["margin_balance"],
                "short_balance": r["short_balance"],
                "revenue_yoy": r["revenue_yoy"]
            })
        return stocks

    @staticmethod
    def update_stock_metadata(stocks_list: List[Dict[str, Any]]):
        """Updates or inserts stock details in bulk (used by backend crawlers)."""
        conn = get_db_connection()
        cursor = conn.cursor()
        for s in stocks_list:
            symbol = s["symbol"]
            # Dynamically compute stockId if not provided
            if "stockId" in s:
                stock_id = s["stockId"]
            else:
                if symbol.endswith(".TW") or symbol.endswith(".TWO"):
                    try:
                        stock_id = int(symbol.split(".")[0])
                    except ValueError:
                        stock_id = 0
                else:
                    stock_id = 0

            cursor.execute("""
                INSERT INTO stock_metadata (
                    symbol, name, price, change, change_percent, volume, pe_ratio, ma5, ma20, stockId,
                    pb_ratio, dividend_yield, foreign_net_buy, trust_net_buy, dealer_net_buy, margin_balance, short_balance, revenue_yoy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    price=excluded.price,
                    change=excluded.change,
                    change_percent=excluded.change_percent,
                    volume=excluded.volume,
                    pe_ratio=COALESCE(excluded.pe_ratio, pe_ratio),
                    ma5=COALESCE(excluded.ma5, ma5),
                    ma20=COALESCE(excluded.ma20, ma20),
                    stockId=excluded.stockId,
                    pb_ratio=COALESCE(excluded.pb_ratio, pb_ratio),
                    dividend_yield=COALESCE(excluded.dividend_yield, dividend_yield),
                    foreign_net_buy=COALESCE(excluded.foreign_net_buy, foreign_net_buy),
                    trust_net_buy=COALESCE(excluded.trust_net_buy, trust_net_buy),
                    dealer_net_buy=COALESCE(excluded.dealer_net_buy, dealer_net_buy),
                    margin_balance=COALESCE(excluded.margin_balance, margin_balance),
                    short_balance=COALESCE(excluded.short_balance, short_balance),
                    revenue_yoy=COALESCE(excluded.revenue_yoy, revenue_yoy)
            """, (
                s["symbol"], s["name"], s.get("price", 0.0), s.get("change", 0.0), s.get("change_percent", 0.0),
                s.get("volume", 0), s.get("pe_ratio"), s.get("ma5"), s.get("ma20"), stock_id,
                s.get("pb_ratio"), s.get("dividend_yield"), s.get("foreign_net_buy"), s.get("trust_net_buy"),
                s.get("dealer_net_buy"), s.get("margin_balance"), s.get("short_balance"), s.get("revenue_yoy")
            ))
        conn.commit()
        conn.close()

# Initialize database on module import
init_db()
