import os
import hashlib
import uuid
from common.logger import logger
from common.base_dao import BaseDAO, OperationalError, DatabaseError

def init_db():
    """Initializes the database schema and seeds default data if tables are empty."""
    conn = BaseDAO.get_connection()
    cursor = conn.cursor()
    
    # Check if migration is needed from old single-user schema
    needs_migration = False
    try:
        # Check if old table structure exists
        cursor.execute("SELECT 1 FROM account LIMIT 1")
        table_exists = True
    except DatabaseError:
        table_exists = False
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        if table_exists:
            cursor.execute("SELECT username FROM account LIMIT 1")
    except DatabaseError:
        needs_migration = True
        try:
            conn.rollback()
        except Exception:
            pass

    if needs_migration:
        logger.warning("[Database] Old single-user schema detected. Migrating to multi-user schema...")
        cursor.execute("DROP TABLE IF EXISTS account")
        cursor.execute("DROP TABLE IF EXISTS positions")
        cursor.execute("DROP TABLE IF EXISTS orders")

    # 1. Users table
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
    conn.commit()
    
    # Run user migrations
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
            conn.commit()
        except DatabaseError:
            try:
                conn.rollback()
            except Exception:
                pass

    # 2. Account table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account (
            username TEXT PRIMARY KEY,
            cash REAL NOT NULL
        )
    """)
    conn.commit()
    
    # 3. Positions table
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
    conn.commit()

    # 4. Orders table
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
    conn.commit()

    # 5. Stock Metadata cache table
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
            stockId INTEGER DEFAULT 0,
            updateDate TEXT
        )
    """)
    conn.commit()

    # 6. Ace Watchlist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ace_watchlist (
            symbol TEXT PRIMARY KEY,
            update_date TEXT NOT NULL,
            strength_dna TEXT,
            hint_double TEXT,
            magic_band TEXT,
            short_sniper TEXT,
            rebound_sprint TEXT,
            create_date TIMESTAMP
        )
    """)
    conn.commit()

    # 7. System Config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    
    # stockId migration
    try:
        cursor.execute("ALTER TABLE stock_metadata ADD COLUMN stockId INTEGER DEFAULT 0")
        conn.commit()
    except DatabaseError as e:
        logger.debug(f"[Database] Migration note for stockId: {e}")
        try:
            conn.rollback()
        except Exception:
            pass

    # Run stock metadata migrations for the 11 new columns
    for col, col_type in [
        ("pb_ratio", "REAL"),
        ("dividend_yield", "REAL"),
        ("foreign_net_buy", "INTEGER"),
        ("trust_net_buy", "INTEGER"),
        ("dealer_net_buy", "INTEGER"),
        ("margin_balance", "INTEGER"),
        ("short_balance", "INTEGER"),
        ("revenue_yoy", "REAL"),
        ("roe", "REAL"),
        ("revenue_growth", "REAL"),
        ("updateDate", "TEXT")
    ]:
        try:
            cursor.execute(f"ALTER TABLE stock_metadata ADD COLUMN {col} {col_type}")
            conn.commit()
        except DatabaseError as e:
            logger.warning(f"[Database] Migration failed for column {col}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
    
    # Run ace watchlist migrations for the 5 new strategy characteristics columns
    for col, col_type in [
        ("strength_dna", "TEXT"),
        ("hint_double", "TEXT"),
        ("magic_band", "TEXT"),
        ("short_sniper", "TEXT"),
        ("rebound_sprint", "TEXT"),
        ("create_date", "TIMESTAMP")
    ]:
        try:
            cursor.execute(f"ALTER TABLE ace_watchlist ADD COLUMN {col} {col_type}")
            conn.commit()
        except DatabaseError as e:
            logger.debug(f"[Database] Migration note for ace_watchlist.{col}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    # Drop obsolete columns from ace_watchlist
    for col in ["strength", "level_val", "chips", "volume_score", "eat_score"]:
        try:
            cursor.execute(f"ALTER TABLE ace_watchlist DROP COLUMN IF EXISTS {col}")
            conn.commit()
        except DatabaseError as e:
            logger.debug(f"[Database] Skip dropping column {col}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
                
    # Remove old 'INTEL' symbol
    cursor.execute("DELETE FROM stock_metadata WHERE symbol = 'INTEL'")

    # Seed default user if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_username = "admin"
        admin_password = "admin123"
        admin_salt = uuid.uuid4().hex
        admin_hashed = hashlib.sha256((admin_password + admin_salt).encode('utf-8')).hexdigest()
        
        cursor.execute("""
            INSERT INTO users (username, hashed_password, salt, role)
            VALUES (?, ?, ?, 'admin')
        """, (admin_username, admin_hashed, admin_salt))
        
        cursor.execute("INSERT INTO account (username, cash) VALUES (?, 10000000.0)", (admin_username,))
        
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
    
    # Seed default stock list
    cursor.execute("SELECT COUNT(*) FROM stock_metadata")
    if cursor.fetchone()[0] == 0:
        default_stocks = [
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
