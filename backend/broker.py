import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

class BrokerGateway(ABC):
    """
    Abstract interface defining methods required by the Web Trading Platform backend.
    Any broker integration (E.Sun, Hua Nan, Mock) must inherit this class.
    """
    @abstractmethod
    def login(self, user_id: str, password: str, cert_path: Optional[str] = None, cert_pass: Optional[str] = None) -> bool:
        """Authenticate with the broker's API and load electronic certificates."""
        pass

    @abstractmethod
    def get_inventory(self) -> List[Dict[str, Any]]:
        """Fetch the user's active holdings / portfolio inventory."""
        pass

    @abstractmethod
    def get_account_summary(self) -> Dict[str, Any]:
        """Fetch general account info: cash balance, total assets, profit/loss."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, action: str, price: float, qty: int, order_type: str) -> Dict[str, Any]:
        """
        Submit a new buy/sell order.
        action: 'BUY' or 'SELL'
        price: target price (limit order) or 0 (market order)
        qty: number of shares (or lots, standard 1 lot = 1000 shares in Taiwan)
        order_type: 'LIMIT' or 'MARKET'
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order by ID."""
        pass

    @abstractmethod
    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Fetch all currently open (unfilled/partially filled) orders."""
        pass


from database import DBStore

class MockBroker(BrokerGateway):
    """
    High-fidelity Mock Broker that simulates accounts, order executions,
    and real-time market data ticks/orderbook for development.
    """
    def __init__(self):
        # Sync with database
        self.cash = DBStore.get_cash()
        
        # Load positions from database
        self.positions: Dict[str, Dict[str, Any]] = {}
        for pos in DBStore.get_positions():
            self.positions[pos["symbol"]] = pos

        self.orders: List[Dict[str, Any]] = DBStore.get_all_orders()
        self.order_counter = 1000 + len(self.orders)
        self.is_logged_in = False

    def login(self, user_id: str, password: str, cert_path: Optional[str] = None, cert_pass: Optional[str] = None) -> bool:
        self.is_logged_in = True
        print(f"[MockBroker] Logged in user: {user_id}")
        return True

    def get_inventory(self) -> List[Dict[str, Any]]:
        # Update current values and PnL based on mocked prices
        inventory_list = []
        for symbol, pos in self.positions.items():
            if pos["qty"] != 0:
                mv = pos["qty"] * pos["current_price"]
                pnl = mv - (pos["qty"] * pos["buy_price"])
                pnl_pct = (pnl / (pos["qty"] * pos["buy_price"])) * 100 if pos["buy_price"] > 0 else 0.0
                
                pos["market_value"] = round(mv, 2)
                pos["unrealized_pnl"] = round(pnl, 2)
                pos["pnl_percent"] = round(pnl_pct, 2)
                inventory_list.append(pos)
        return inventory_list

    def get_account_summary(self) -> Dict[str, Any]:
        inventory = self.get_inventory()
        # Sum up PnL and Market Value for positive holding quantities
        total_pnl = sum(item["unrealized_pnl"] for item in inventory)
        market_val = sum(item["market_value"] for item in inventory)
        total_assets = self.cash + market_val
        return {
            "cash": round(self.cash, 2),
            "market_value": round(market_val, 2),
            "total_assets": round(total_assets, 2),
            "total_pnl": round(total_pnl, 2)
        }

    def place_order(self, symbol: str, action: str, price: float, qty: int, order_type: str) -> Dict[str, Any]:
        self.order_counter += 1
        order_id = f"MOCK-{self.order_counter}"
        
        # Handle market price resolution
        exec_price = price
        if order_type.upper() == "MARKET" or price <= 0:
            if symbol in self.positions:
                exec_price = self.positions[symbol]["current_price"]
            else:
                # Fallback to some defaults
                exec_price = 100.0 if "TW" not in symbol else 500.0

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action.upper(),
            "price": round(price, 2) if order_type.upper() == "LIMIT" else 0.0,
            "qty": qty,
            "order_type": order_type.upper(),
            "status": "FILLED", # Auto-fill in mock for instant day trading UI feedback
            "exec_price": round(exec_price, 2),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        # Save order to database
        DBStore.add_order(order)
        self.orders.insert(0, order) # Prepend to history
        self._process_execution(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order["order_id"] == order_id and order["status"] == "PENDING":
                order["status"] = "CANCELLED"
                return True
        return False

    def get_active_orders(self) -> List[Dict[str, Any]]:
        return [o for o in self.orders if o["status"] == "PENDING"]

    def _process_execution(self, order: Dict[str, Any]):
        """Adjusts cash and inventory when an order fills, updating database."""
        symbol = order["symbol"]
        action = order["action"]
        qty = order["qty"]
        price = order["exec_price"]
        total_cost = price * qty

        # Get name mapping
        name = symbol
        if symbol == "2330.TW": name = "台積電"
        elif symbol == "2317.TW": name = "鴻海"
        elif symbol == "2454.TW": name = "聯發科"
        elif symbol == "2603.TW": name = "長榮"
        elif symbol == "2609.TW": name = "陽明"

        if action == "BUY":
            self.cash -= total_cost
            if symbol in self.positions:
                # Average down/up price
                old_qty = self.positions[symbol]["qty"]
                old_price = self.positions[symbol]["buy_price"]
                new_qty = old_qty + qty
                new_price = ((old_price * old_qty) + total_cost) / new_qty
                
                self.positions[symbol]["qty"] = new_qty
                self.positions[symbol]["buy_price"] = round(new_price, 2)
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "qty": qty,
                    "buy_price": round(price, 2),
                    "current_price": price,
                    "market_value": total_cost,
                    "unrealized_pnl": 0.0,
                    "pnl_percent": 0.0
                }
        elif action == "SELL":
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos["qty"] -= qty
                self.cash += total_cost
                
                if pos["qty"] <= 0:
                    self.positions.pop(symbol, None)
                    # DB update will handle removal when qty=0
            else:
                self.cash += total_cost
                self.positions[symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "qty": -qty,
                    "buy_price": round(price, 2),
                    "current_price": price,
                    "market_value": -total_cost,
                    "unrealized_pnl": 0.0,
                    "pnl_percent": 0.0
                }

        # Update database with new values
        DBStore.update_cash(self.cash)
        if symbol in self.positions:
            pos = self.positions[symbol]
            DBStore.update_position(symbol, name, pos["qty"], pos["buy_price"])
        else:
            DBStore.update_position(symbol, name, 0, 0.0)

    def generate_live_market_data(self, symbol: str, base_price: float) -> Dict[str, Any]:
        """
        Simulates live stock changes, price ticks, and 5-Level orderbook.
        Used to feed the WebSocket connections.
        """
        # Save simulated base price in positions if exists, to keep portfolio synced
        if symbol in self.positions:
            current = self.positions[symbol]["current_price"]
        else:
            current = base_price

        # Micro-fluctuation (-0.1% to +0.1%)
        pct = random.uniform(-0.0015, 0.0015)
        new_price = current * (1 + pct)
        new_price = max(0.1, round(new_price, 2))

        # Sync back to position tracker
        if symbol in self.positions:
            self.positions[symbol]["current_price"] = new_price

        # Dynamic bid-ask spread calculation (Taiwan tick rules or generic US)
        # Taiwan tick size is generally: 
        # < 10: 0.01; 10-50: 0.05; 50-100: 0.1; 100-500: 0.5; 500-1000: 1.0; > 1000: 5.0
        tick_size = 0.01
        if "TW" in symbol:
            if new_price < 10: tick_size = 0.01
            elif new_price < 50: tick_size = 0.05
            elif new_price < 100: tick_size = 0.1
            elif new_price < 500: tick_size = 0.5
            elif new_price < 1000: tick_size = 1.0
            else: tick_size = 5.0
        else:
            tick_size = 0.01

        # Generate 5 levels of bids (below current) and asks (above current)
        bids = []
        asks = []
        for i in range(1, 6):
            bid_price = round(new_price - (i * tick_size), 2)
            bid_qty = random.randint(5, 120) * (1000 if "TW" in symbol else 1) # Lots vs shares
            bids.append({"price": bid_price, "volume": bid_qty})

            ask_price = round(new_price + (i * tick_size), 2)
            ask_qty = random.randint(5, 120) * (1000 if "TW" in symbol else 1)
            asks.append({"price": ask_price, "volume": ask_qty})

        # Tick detail (single trade)
        tick_qty = random.choice([1, 2, 5, 10, 20, 50, 100]) * (1000 if "TW" in symbol else 1)
        tick_direction = random.choice(["BUY", "SELL", "NEUTRAL"])

        return {
            "symbol": symbol,
            "price": new_price,
            "time": datetime.now().strftime("%H:%M:%S"),
            "tick": {
                "price": new_price,
                "volume": tick_qty,
                "direction": tick_direction,
            },
            "depth": {
                "bids": bids, # Sorted high to low automatically
                "asks": asks  # Sorted low to high automatically
            }
        }


# =====================================================================
#  PRODUCTION BROKER INTEGRATION BLUEPRINTS (E.Sun & Hua Nan)
# =====================================================================

"""
### 玉山證券 (E.Sun Securities) / 富果 (Fugle) API 串接指南:
1. 安裝套件: pip install fugle-trade
2. 初始化及登入邏輯:

from fugle_trade.sdk import SDK
from fugle_trade.api import TaiwanStockAPI

class EsunFugleBroker(BrokerGateway):
    def __init__(self):
        self.sdk = None
        self.api = None

    def login(self, user_id, password, cert_path=None, cert_pass=None):
        try:
            self.sdk = SDK({
                "cert_path": cert_path,         # 憑證檔案路徑 (.p12)
                "key_password": cert_pass,      # 憑證密碼
                "api_key": "YOUR_API_KEY",      # 富果申請的 API Key
                "api_secret": "YOUR_SECRET"     # 富果 API Secret
            })
            self.sdk.login(user_id, password)
            self.api = TaiwanStockAPI(self.sdk)
            return True
        except Exception as e:
            print(f"玉山富果登入失敗: {e}")
            return False

    def get_inventory(self):
        # 呼叫富果 API 查詢庫存
        res = self.api.get_inventories()
        # 轉換成平台通用的格式
        positions = []
        for item in res:
            positions.append({
                "symbol": f"{item['stock_no']}.TW",
                "name": item['stock_name'],
                "qty": int(item['qty']),
                "buy_price": float(item['cost_price']),
                "current_price": float(item['last_price']),
                "market_value": float(item['market_value']),
                "unrealized_pnl": float(item['profit']),
                "pnl_percent": float(item['profit_rate']) * 100
            })
        return positions

    def place_order(self, symbol, action, price, qty, order_type):
        # 台灣股市股票代號需要去除後綴 (.TW)
        stock_no = symbol.split(".")[0]
        
        # 建立 Fugle 委託物件
        # Action: 'Buy' / 'Sell'
        # Price: 限價金額, OrderType: LIMIT (限價) / MARKET (市價)
        # ApCode: 委託種類 (現股, 當沖等，例如 'Common' 現股, 'DayTrading' 當沖)
        order_params = {
            "buy_sell": "B" if action.upper() == "BUY" else "S",
            "stock_no": stock_no,
            "quantity": qty,                # 張數
            "price": price if order_type.upper() == "LIMIT" else None,
            "ap_code": "DayTrading",        # 預設支援當沖交易
            "price_flag": "L" if order_type.upper() == "LIMIT" else "M"
        }
        res = self.api.place_order(**order_params)
        return {
            "order_id": res["order_no"],
            "status": "PENDING",
            "symbol": symbol,
            "action": action,
            "exec_price": price
        }

    # 同理實作 cancel_order 與 get_active_orders...


### 華南證券 (Hua Nan) API 串接指南:
華南證券主要透過「華南永昌智慧交易系統」或與外部合作的 API 模組進行自動下單，
其 Python SDK（通常為內部專用 SDK）與永豐 (Shioaji) 類似，以下為典型架構：

class HuaNanBroker(BrokerGateway):
    def __init__(self):
        # 載入華南 SDK 物件
        # import huanan_api
        self.api = None

    def login(self, user_id, password, cert_path=None, cert_pass=None):
        try:
            # self.api = huanan_api.Trader()
            # self.api.login(user_id=user_id, password=password, cert_path=cert_path, cert_password=cert_pass)
            return True
        except Exception as e:
            print(f"華南證券登入失敗: {e}")
            return False

    def get_inventory(self):
        # positions = self.api.query_positions()
        # return format_to_standard(positions)
        pass

    def place_order(self, symbol, action, price, qty, order_type):
        # order = self.api.Order(
        #     code=symbol.split(".")[0],
        #     action=action, # BUY/SELL
        #     price=price,
        #     qty=qty,
        #     price_type="LMT" if order_type == "LIMIT" else "MKT"
        # )
        # res = self.api.place_order(order)
        # return res
        pass
"""
