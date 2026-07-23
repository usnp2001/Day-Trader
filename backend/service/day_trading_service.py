import uuid
import random
import datetime
from typing import List, Dict, Any, Optional
import yfinance as yf
from dal.stock_metadata_dao import StockMetadataDao
from dal.day_trading_dao import DayTradingDao
from common.logger import logger

class DayTradingService:

    @classmethod
    def import_top_50_ticks(cls) -> Dict[str, Any]:
        """
        Gets the top 50 volume stocks from stock_metadata.
        Downloads their 1-minute daily tick data via yfinance, or generates
        high-fidelity mock ticks if yfinance is empty or rate-limited.
        """
        logger.info("[Simulation] Fetching top 50 volume stocks for tick import...")
        
        # 1. Fetch top 50 volume stocks from database
        conn = StockMetadataDao.get_connection()
        rows = conn.execute("""
            SELECT symbol, name, price, volume FROM stock_metadata
            ORDER BY volume DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        
        if not rows:
            return {"status": "error", "message": "No stocks found in database. Please sync first."}
            
        DayTradingDao.clear_ticks()
        imported_count = 0
        mocked_count = 0
        all_ticks = []

        # Determine last trading date/time context
        today = datetime.date.today()
        # default to 1d period
        
        for r in rows:
            symbol = r["symbol"]
            name = r["name"]
            base_price = r["price"]
            volume = r["volume"] or 100000
            
            logger.info(f"[Simulation] Loading ticks for {symbol} ({name})...")
            ticks = []
            
            # Try fetching real yfinance 1m data
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="1d", interval="1m")
                if not df.empty and len(df) >= 30:
                    prev_p = None
                    prev_t = "OUTER"
                    for idx, row in df.iterrows():
                        time_str = idx.strftime("%H:%M:%S")
                        close_p = round(float(row["Close"]), 2)
                        
                        if prev_p is None:
                            curr_type = "OUTER"
                        elif close_p > prev_p:
                            curr_type = "OUTER"
                            prev_t = "OUTER"
                        elif close_p < prev_p:
                            curr_type = "INNER"
                            prev_t = "INNER"
                        else:
                            curr_type = prev_t
                            
                        ticks.append({
                            "symbol": symbol,
                            "timestamp": time_str,
                            "price": close_p,
                            "volume": int(row["Volume"]),
                            "tick_type": curr_type
                        })
                        prev_p = close_p
                    imported_count += 1
                    logger.info(f"[Simulation] Successfully imported {len(ticks)} real ticks for {symbol}.")
            except Exception as e:
                logger.warning(f"[Simulation] Failed to get yfinance data for {symbol}: {e}. Falling back to mock data.")

            # Fallback to high-fidelity mock ticks
            if not ticks:
                ticks = cls._generate_mock_ticks(symbol, base_price, volume)
                mocked_count += 1
                logger.info(f"[Simulation] Generated {len(ticks)} simulated ticks for {symbol}.")
                
            all_ticks.extend(ticks)

        # Bulk insert
        DayTradingDao.insert_ticks(all_ticks)
        logger.info(f"[Simulation] Tick import completed. Real: {imported_count}, Mocked: {mocked_count}, Total Ticks: {len(all_ticks)}.")
        return {
            "status": "success",
            "message": f"Successfully loaded ticks for 50 stocks (Real: {imported_count}, Simulated: {mocked_count})."
        }

    @classmethod
    def import_watchlist_ticks(cls, username: str) -> Dict[str, Any]:
        """
        Gets the user's custom watchlist symbols.
        Downloads their 1-minute daily tick data via yfinance, or generates
        high-fidelity mock ticks if yfinance is empty or rate-limited.
        """
        logger.info(f"[Simulation] Fetching watchlist stocks for tick import for user: {username}...")
        
        from dal.user_watchlist_dao import UserWatchlistDao
        watchlist = UserWatchlistDao.get_watchlist(username)
        if not watchlist:
            return {"status": "error", "message": "自選清單中無股票。請先將股票加入自選清單！"}
            
        # Get metadata for these symbols
        symbols = [w["symbol"] for w in watchlist]
        conn = StockMetadataDao.get_connection()
        placeholders = ",".join(["?"] * len(symbols))
        rows = conn.execute(f"""
            SELECT symbol, name, price, volume FROM stock_metadata
            WHERE symbol IN ({placeholders})
        """, symbols).fetchall()
        conn.close()
        
        if not rows:
            return {"status": "error", "message": "自選股在資料庫中找不到對應元數據，請先執行同步！"}
            
        DayTradingDao.clear_ticks()
        imported_count = 0
        mocked_count = 0
        all_ticks = []

        for r in rows:
            symbol = r["symbol"]
            name = r["name"]
            base_price = r["price"]
            volume = r["volume"] or 100000
            
            logger.info(f"[Simulation] Loading ticks for {symbol} ({name})...")
            ticks = []
            
            # Try fetching real yfinance 1m data
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="1d", interval="1m")
                if not df.empty and len(df) >= 30:
                    prev_p = None
                    prev_t = "OUTER"
                    for idx, row in df.iterrows():
                        time_str = idx.strftime("%H:%M:%S")
                        close_p = round(float(row["Close"]), 2)
                        
                        if prev_p is None:
                            curr_type = "OUTER"
                        elif close_p > prev_p:
                            curr_type = "OUTER"
                            prev_t = "OUTER"
                        elif close_p < prev_p:
                            curr_type = "INNER"
                            prev_t = "INNER"
                        else:
                            curr_type = prev_t
                            
                        ticks.append({
                            "symbol": symbol,
                            "timestamp": time_str,
                            "price": close_p,
                            "volume": int(row["Volume"]),
                            "tick_type": curr_type
                        })
                        prev_p = close_p
                    imported_count += 1
                    logger.info(f"[Simulation] Successfully imported {len(ticks)} real ticks for {symbol}.")
            except Exception as e:
                logger.warning(f"[Simulation] Failed to get yfinance data for {symbol}: {e}. Falling back to mock data.")

            # Fallback to high-fidelity mock ticks
            if not ticks:
                ticks = cls._generate_mock_ticks(symbol, base_price, volume)
                mocked_count += 1
                logger.info(f"[Simulation] Generated {len(ticks)} simulated ticks for {symbol}.")
                
            all_ticks.extend(ticks)

        # Bulk insert
        DayTradingDao.insert_ticks(all_ticks)
        logger.info(f"[Simulation] Watchlist tick import completed. Real: {imported_count}, Mocked: {mocked_count}, Total Ticks: {len(all_ticks)}.")
        return {
            "status": "success",
            "message": f"自選股 Ticks 匯入成功！共 {len(rows)} 檔 (實體: {imported_count}, 模擬: {mocked_count})。"
        }

    @classmethod
    def _generate_mock_ticks(cls, symbol: str, base_price: float, volume: int) -> List[Dict[str, Any]]:
        """Generates realistic 1-minute interval ticks from 09:00:00 to 13:30:00 (271 ticks)."""
        ticks = []
        # Simulate a trading day
        start_time = datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        current_price = base_price
        
        # Decide stock drift direction to simulate bullish/bearish patterns
        # 40% chance bullish, 40% chance bearish, 20% flat
        drift_choice = random.choice([0.0003, -0.0003, 0.0])
        
        prev_p = None
        prev_t = "OUTER"
        # 271 minutes (09:00 to 13:30)
        for m in range(271):
            time_str = (start_time + datetime.timedelta(minutes=m)).strftime("%H:%M:%S")
            # Random shock
            shock = current_price * random.normalvariate(drift_choice, 0.0018)
            current_price = max(1.0, current_price + shock)
            close_p = round(current_price, 2)
            
            # Volume distribution: higher at open and close
            if m < 30: # Open
                multiplier = random.uniform(1.5, 3.0)
            elif m > 240: # Close
                multiplier = random.uniform(2.0, 4.0)
            else: # Midday
                multiplier = random.uniform(0.5, 1.2)
                
            tick_vol = int(random.uniform(volume / 500, volume / 200) * multiplier)
            
            if prev_p is None:
                curr_type = "OUTER"
            elif close_p > prev_p:
                curr_type = "OUTER"
                prev_t = "OUTER"
            elif close_p < prev_p:
                curr_type = "INNER"
                prev_t = "INNER"
            else:
                curr_type = prev_t
                
            ticks.append({
                "symbol": symbol,
                "timestamp": time_str,
                "price": close_p,
                "volume": max(100, tick_vol),
                "tick_type": curr_type
            })
            prev_p = close_p
        return ticks

    @classmethod
    def run_simulation(cls, username: str, allocated_limit: float, symbols_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Runs the Day Trading Simulation for the given user.
        Uses Peak/Trough algorithm, stop-loss (-1%) & take-profit (+4%) rules,
        and Taiwan-specific transaction costs.
        """
        logger.info(f"[Simulation] Running simulation for user '{username}' with budget NT$ {allocated_limit} per stock (Filter: {symbols_filter})...")
        
        # 1. Clear previous simulation data
        DayTradingDao.clear_user_simulation_data(username)
        
        # 2. Get unique symbols in ticks
        conn = DayTradingDao.get_connection()
        symbols_rows = conn.execute("SELECT DISTINCT symbol FROM day_trading_ticks").fetchall()
        conn.close()
        symbols = [r["symbol"] for r in symbols_rows]
        
        if symbols_filter is not None:
            symbols = [s for s in symbols if s in symbols_filter]
            
        if not symbols and symbols_filter is None:
            # If no ticks imported, auto-import first!
            cls.import_top_50_ticks()
            conn = DayTradingDao.get_connection()
            symbols_rows = conn.execute("SELECT DISTINCT symbol FROM day_trading_ticks").fetchall()
            conn.close()
            symbols = [r["symbol"] for r in symbols_rows]
            
        if not symbols:
            return {"status": "error", "message": "無可用 Tick 資料以執行模擬。請先匯入 Tick 資料！"}
            
        # Get stock metadata for names
        db_stocks = StockMetadataDao.get_stocks_by_symbols(symbols)
        names_map = {s["symbol"]: s["name"] for s in db_stocks}
        
        simulated_summaries = []
        simulated_trades = []
        
        for symbol in symbols:
            name = names_map.get(symbol, symbol)
            ticks = DayTradingDao.get_ticks_by_symbol(symbol)
            if len(ticks) < 40: # Needs sufficient ticks
                continue
                
            # Determine Open Price
            open_price = ticks[0]["price"]
            
            # Position Sizing: floor(allocated_limit / (open_price * 1000))
            lots = int(allocated_limit // (open_price * 1000))
            qty = lots * 1000
            
            if lots < 1:
                # If budget is not enough for 1 lot (1000 shares), skip trading!
                simulated_summaries.append({
                    "username": username,
                    "symbol": symbol,
                    "name": name,
                    "volume": sum(t["volume"] for t in ticks),
                    "open_price": open_price,
                    "close_price": ticks[-1]["price"],
                    "high_price": max(t["price"] for t in ticks),
                    "low_price": min(t["price"] for t in ticks),
                    "pnl": 0.0,
                    "trend": "NONE",
                    "status": "NOT_TRADED" # Budget insufficient
                })
                continue
                
            # Calculate limit up price for the stock
            # limit up is open_price * 1.10, rounded down to tick size
            import math
            limit_up = open_price * 1.10
            limit_up_tick = cls.get_tick_size(limit_up)
            limit_up = round(math.floor(limit_up / limit_up_tick) * limit_up_tick, 2)
            limit_up_prev = round(limit_up - cls.get_tick_size(limit_up), 2)

            # Split ticks: Trend Judgment (first 30 minutes: index 0 to 30)
            # Trend is based on price at 09:30 compared to open price (09:00)
            price_30m = ticks[min(30, len(ticks)-1)]["price"]
            trend = "BULLISH" if price_30m >= open_price else "BEARISH"
            
            # Trading simulation starts from 09:30 onwards (index 30 onwards)
            trading_ticks = ticks[30:]
            
            position = 0 # 0: none, 1: long, -1: short
            entry_price = 0.0
            take_profit_price = 0.0
            open_commission = 0.0
            open_tax = 0.0
            
            status = "ACTIVE"
            stock_pnl = 0.0
            
            # Track daily high/low/close
            high_price = max(t["price"] for t in ticks)
            low_price = min(t["price"] for t in ticks)
            close_price = ticks[-1]["price"]
            total_vol = sum(t["volume"] for t in ticks)
            
            # Loop for trading decisions
            for idx in range(2, len(trading_ticks)):
                tick = trading_ticks[idx]
                price_prev2 = trading_ticks[idx-2]["price"]
                price_prev1 = trading_ticks[idx-1]["price"]
                price_curr = tick["price"]
                timestamp = tick["timestamp"]
                
                # Check for 13:10 force close rule
                if timestamp >= "13:10:00":
                    if position != 0:
                        # Force close position at current price
                        if position == 1:
                            close_commission = round(price_curr * qty * 0.001425 * 0.2)
                            close_tax = round(price_curr * qty * 0.0015)
                            pnl = (price_curr * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "SELL",
                                "trade_type": "LONG_CLOSE",
                                "price": price_curr,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": close_tax,
                                "pnl": pnl,
                                "timestamp": "13:10:00",
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                        elif position == -1:
                            close_commission = round(price_curr * qty * 0.001425 * 0.2)
                            pnl = (entry_price * qty) - (price_curr * qty) - open_commission - open_tax - close_commission
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "BUY",
                                "trade_type": "SHORT_CLOSE",
                                "price": price_curr,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": 0.0,
                                "pnl": pnl,
                                "timestamp": "13:10:00",
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                        position = 0
                    if status == "ACTIVE":
                        status = "SUCCESS"
                    break # Stop trading for the day
                
                if position == 1: # Long position
                    # Stop-loss at -1% (per-position)
                    if price_curr <= entry_price * 0.99:
                        exit_price = round(entry_price * 0.99, 2)
                        close_commission = round(exit_price * qty * 0.001425 * 0.2)
                        close_tax = round(exit_price * qty * 0.0015)
                        pnl = (exit_price * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                        
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "SELL",
                            "trade_type": "LONG_CLOSE",
                            "price": exit_price,
                            "qty": qty,
                            "fee": close_commission,
                            "tax": close_tax,
                            "pnl": pnl,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        stock_pnl += pnl
                        position = 0
                        status = "STOP_LOSS"
                        break # Stop trading for the day
                        
                    # Take-profit check (cumulative >= 4% or limit-up rule)
                    else:
                        close_commission = round(price_curr * qty * 0.001425 * 0.2)
                        close_tax = round(price_curr * qty * 0.0015)
                        floating_pnl = (price_curr * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                        
                        is_cumulative_tp = (stock_pnl + floating_pnl) >= (allocated_limit * 0.04)
                        is_limit_up_tp = (entry_price * 1.04 > limit_up) and (price_curr >= limit_up_prev)
                        
                        if is_cumulative_tp or is_limit_up_tp:
                            exit_price = price_curr
                            pnl = floating_pnl
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "SELL",
                                "trade_type": "LONG_CLOSE",
                                "price": exit_price,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": close_tax,
                                "pnl": pnl,
                                "timestamp": timestamp,
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                            position = 0
                            status = "TAKE_PROFIT"
                            break # Stop trading for the day
                        
                elif position == -1: # Short position
                    # Stop-loss at +1% price rise (short losses when price rises)
                    if price_curr >= entry_price * 1.01:
                        exit_price = round(entry_price * 1.01, 2)
                        close_commission = round(exit_price * qty * 0.001425 * 0.2)
                        pnl = (entry_price * qty) - (exit_price * qty) - open_commission - open_tax - close_commission
                        
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "BUY",
                            "trade_type": "SHORT_CLOSE",
                            "price": exit_price,
                            "qty": qty,
                            "fee": close_commission,
                            "tax": 0.0,
                            "pnl": pnl,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        stock_pnl += pnl
                        position = 0
                        status = "STOP_LOSS"
                        break
                        
                    # Take-profit check (cumulative >= 4% or short -4% drop target)
                    else:
                        close_commission = round(price_curr * qty * 0.001425 * 0.2)
                        floating_pnl = (entry_price * qty) - (price_curr * qty) - open_commission - open_tax - close_commission
                        
                        is_cumulative_tp = (stock_pnl + floating_pnl) >= (allocated_limit * 0.04)
                        is_short_tp = (price_curr <= entry_price * 0.96)
                        
                        if is_cumulative_tp or is_short_tp:
                            exit_price = price_curr
                            pnl = floating_pnl
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "BUY",
                                "trade_type": "SHORT_CLOSE",
                                "price": exit_price,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": 0.0,
                                "pnl": pnl,
                                "timestamp": timestamp,
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                            position = 0
                            status = "TAKE_PROFIT"
                            break
                
                # Check Peak / Trough for signals
                is_peak = (price_prev1 > price_prev2) and (price_prev1 > price_curr)
                is_trough = (price_prev1 < price_prev2) and (price_prev1 < price_curr)
                
                if position == 0 and status == "ACTIVE":
                    if trend == "BULLISH" and is_trough:
                        # Buy Long
                        position = 1
                        entry_price = price_curr
                        open_commission = round(entry_price * qty * 0.001425 * 0.2)
                        
                        # Determine take-profit target: if price gap to limit up is < 4%, sell at 1 tick below limit up
                        take_profit_price = entry_price * 1.04
                        if entry_price * 1.04 > limit_up:
                            take_profit_price = limit_up_prev
                            
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "BUY",
                            "trade_type": "LONG_OPEN",
                            "price": entry_price,
                            "qty": qty,
                            "fee": open_commission,
                            "tax": 0.0,
                            "pnl": 0.0,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        
                    elif trend == "BEARISH" and is_peak:
                        # Short Sell Open
                        position = -1
                        entry_price = price_curr
                        open_commission = round(entry_price * qty * 0.001425 * 0.2)
                        open_tax = round(entry_price * qty * 0.0015)
                        
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "SELL",
                            "trade_type": "SHORT_OPEN",
                            "price": entry_price,
                            "qty": qty,
                            "fee": open_commission,
                            "tax": open_tax,
                            "pnl": 0.0,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        
                elif position == 1 and is_peak:
                    # Sell Close Long
                    close_commission = round(price_curr * qty * 0.001425 * 0.2)
                    close_tax = round(price_curr * qty * 0.0015)
                    pnl = (price_curr * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "SELL",
                        "trade_type": "LONG_CLOSE",
                        "price": price_curr,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": close_tax,
                        "pnl": pnl,
                        "timestamp": timestamp,
                        "tick_type": tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                    position = 0
                    if stock_pnl >= allocated_limit * 0.04:
                        status = "TAKE_PROFIT"
                        break
                    
                elif position == -1 and is_trough:
                    # Buy Cover Short
                    close_commission = round(price_curr * qty * 0.001425 * 0.2)
                    pnl = (entry_price * qty) - (price_curr * qty) - open_commission - open_tax - close_commission
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "BUY",
                        "trade_type": "SHORT_CLOSE",
                        "price": price_curr,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": 0.0,
                        "pnl": pnl,
                        "timestamp": timestamp,
                        "tick_type": tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                    position = 0
                    if stock_pnl >= allocated_limit * 0.04:
                        status = "TAKE_PROFIT"
                        break
            
            # Force Close at 13:30 (last tick) if still open
            if position != 0:
                final_tick = trading_ticks[-1]
                final_price = final_tick["price"]
                final_timestamp = final_tick["timestamp"]
                
                if position == 1:
                    close_commission = round(final_price * qty * 0.001425 * 0.2)
                    close_tax = round(final_price * qty * 0.0015)
                    pnl = (final_price * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "SELL",
                        "trade_type": "LONG_CLOSE",
                        "price": final_price,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": close_tax,
                        "pnl": pnl,
                        "timestamp": final_timestamp,
                        "tick_type": final_tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                elif position == -1:
                    close_commission = round(final_price * qty * 0.001425 * 0.2)
                    pnl = (entry_price * qty) - (final_price * qty) - open_commission - open_tax - close_commission
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "BUY",
                        "trade_type": "SHORT_CLOSE",
                        "price": final_price,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": 0.0,
                        "pnl": pnl,
                        "timestamp": final_timestamp,
                        "tick_type": final_tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                position = 0
            
            if status == "ACTIVE":
                status = "SUCCESS"
                
            simulated_summaries.append({
                "username": username,
                "symbol": symbol,
                "name": name,
                "volume": total_vol,
                "open_price": open_price,
                "close_price": close_price,
                "high_price": high_price,
                "low_price": low_price,
                "pnl": round(stock_pnl, 2),
                "trend": trend,
                "status": status
            })

        # Insert records into DB
        DayTradingDao.insert_trades(simulated_trades)
        DayTradingDao.insert_summaries(simulated_summaries)
        
        logger.info(f"[Simulation] Finished running simulation for '{username}'. Total trades recorded: {len(simulated_trades)}.")
        return {
            "status": "success",
            "message": f"Simulation completed. Simulated trades: {len(simulated_trades)}."
        }

    @classmethod
    def run_simulation_open_base(cls, username: str, allocated_limit: float, symbols_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Runs the Second Day Trading Simulation strategy for the given user.
        Uses Open Price relative to Flat Price (Yesterday's Close) to build positions:
        - If Open Price > Flat Price -> BUY Long Open at opening price
        - If Open Price <= Flat Price -> SELL Short Open at opening price
        """
        logger.info(f"[Simulation] Running Open Price Base simulation for user '{username}' with budget NT$ {allocated_limit} per stock (Filter: {symbols_filter})...")
        
        # 1. Clear previous simulation data
        DayTradingDao.clear_user_simulation_data(username)
        
        # 2. Get unique symbols in ticks
        conn = DayTradingDao.get_connection()
        symbols_rows = conn.execute("SELECT DISTINCT symbol FROM day_trading_ticks").fetchall()
        conn.close()
        symbols = [r["symbol"] for r in symbols_rows]
        
        if symbols_filter is not None:
            symbols = [s for s in symbols if s in symbols_filter]
            
        if not symbols and symbols_filter is None:
            # If no ticks imported, auto-import first!
            cls.import_top_50_ticks()
            conn = DayTradingDao.get_connection()
            symbols_rows = conn.execute("SELECT DISTINCT symbol FROM day_trading_ticks").fetchall()
            conn.close()
            symbols = [r["symbol"] for r in symbols_rows]
            
        if not symbols:
            return {"status": "error", "message": "無可用 Tick 資料以執行模擬。請先匯入 Tick 資料！"}
            
        # Get stock metadata for names and yesterday's close (flat price = price - change)
        db_stocks = StockMetadataDao.get_stocks_by_symbols(symbols)
        names_map = {s["symbol"]: s["name"] for s in db_stocks}
        # Flat price reference map
        flat_price_map = {}
        for s in db_stocks:
            close_price = s["price"]
            change = s["change"] or 0.0
            flat_price_map[s["symbol"]] = round(close_price - change, 2)
        
        simulated_summaries = []
        simulated_trades = []
        
        for symbol in symbols:
            name = names_map.get(symbol, symbol)
            ticks = DayTradingDao.get_ticks_by_symbol(symbol)
            if len(ticks) < 10: # Needs sufficient ticks
                continue
                
            # Determine Open Price
            open_tick = ticks[0]
            open_price = open_tick["price"]
            open_timestamp = open_tick["timestamp"]
            
            # Position Sizing: floor(allocated_limit / (open_price * 1000))
            lots = int(allocated_limit // (open_price * 1000))
            qty = lots * 1000
            
            if lots < 1:
                # If budget is not enough for 1 lot (1000 shares), skip trading!
                simulated_summaries.append({
                    "username": username,
                    "symbol": symbol,
                    "name": name,
                    "volume": sum(t["volume"] for t in ticks),
                    "open_price": open_price,
                    "close_price": ticks[-1]["price"],
                    "high_price": max(t["price"] for t in ticks),
                    "low_price": min(t["price"] for t in ticks),
                    "pnl": 0.0,
                    "trend": "NONE",
                    "status": "NOT_TRADED" # Budget insufficient
                })
                continue
                
            # Flat price (平盤價)
            flat_price = flat_price_map.get(symbol, open_price) # Default to open_price (flat) if metadata missing
            
            # Determine Trend: if open_price > flat_price -> Long (BULLISH); else -> Short (BEARISH)
            if open_price > flat_price:
                trend = "BULLISH"
                position = 1
            else:
                trend = "BEARISH"
                position = -1
                
            # Open position at first tick (index 0)
            entry_price = open_price
            open_commission = round(entry_price * qty * 0.001425 * 0.2)
            open_tax = 0.0
            
            # Record Opening Trade
            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
            if position == 1:
                # Long Open
                simulated_trades.append({
                    "trade_id": trade_id,
                    "username": username,
                    "symbol": symbol,
                    "action": "BUY",
                    "trade_type": "LONG_OPEN",
                    "price": entry_price,
                    "qty": qty,
                    "fee": open_commission,
                    "tax": 0.0,
                    "pnl": 0.0,
                    "timestamp": open_timestamp,
                    "tick_type": open_tick.get("tick_type", "OUTER")
                })
            else:
                # Short Open
                open_tax = round(entry_price * qty * 0.0015)
                simulated_trades.append({
                    "trade_id": trade_id,
                    "username": username,
                    "symbol": symbol,
                    "action": "SELL",
                    "trade_type": "SHORT_OPEN",
                    "price": entry_price,
                    "qty": qty,
                    "fee": open_commission,
                    "tax": open_tax,
                    "pnl": 0.0,
                    "timestamp": open_timestamp,
                    "tick_type": open_tick.get("tick_type", "OUTER")
                })
                
            # Calculate limit up price for Long limit-up check
            import math
            limit_up = open_price * 1.10
            limit_up_tick = cls.get_tick_size(limit_up)
            limit_up = round(math.floor(limit_up / limit_up_tick) * limit_up_tick, 2)
            limit_up_prev = round(limit_up - cls.get_tick_size(limit_up), 2)
            
            status = "ACTIVE"
            stock_pnl = 0.0
            
            # Track daily high/low/close
            high_price = max(t["price"] for t in ticks)
            low_price = min(t["price"] for t in ticks)
            close_price = ticks[-1]["price"]
            total_vol = sum(t["volume"] for t in ticks)
            
            # Loop for trading decisions (monitoring exit) starting from index 1
            for idx in range(1, len(ticks)):
                tick = ticks[idx]
                price_curr = tick["price"]
                timestamp = tick["timestamp"]
                
                # Check for 13:10 force close rule
                if timestamp >= "13:10:00":
                    if position != 0:
                        # Force close position at current price
                        if position == 1:
                            close_commission = round(price_curr * qty * 0.001425 * 0.2)
                            close_tax = round(price_curr * qty * 0.0015)
                            pnl = (price_curr * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "SELL",
                                "trade_type": "LONG_CLOSE",
                                "price": price_curr,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": close_tax,
                                "pnl": pnl,
                                "timestamp": "13:10:00",
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                        elif position == -1:
                            close_commission = round(price_curr * qty * 0.001425 * 0.2)
                            pnl = (entry_price * qty) - (price_curr * qty) - open_commission - open_tax - close_commission
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "BUY",
                                "trade_type": "SHORT_CLOSE",
                                "price": price_curr,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": 0.0,
                                "pnl": pnl,
                                "timestamp": "13:10:00",
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                        position = 0
                    if status == "ACTIVE":
                        status = "SUCCESS"
                    break # Stop trading for the day
                    
                # Monitor stop-loss and take-profit
                if position == 1: # Long
                    # Stop-loss at -1% (per-position)
                    if price_curr <= entry_price * 0.99:
                        exit_price = round(entry_price * 0.99, 2)
                        close_commission = round(exit_price * qty * 0.001425 * 0.2)
                        close_tax = round(exit_price * qty * 0.0015)
                        pnl = (exit_price * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                        
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "SELL",
                            "trade_type": "LONG_CLOSE",
                            "price": exit_price,
                            "qty": qty,
                            "fee": close_commission,
                            "tax": close_tax,
                            "pnl": pnl,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        stock_pnl += pnl
                        position = 0
                        status = "STOP_LOSS"
                        break
                        
                    # Take-profit check (cumulative >= 4% or limit-up rule)
                    else:
                        close_commission = round(price_curr * qty * 0.001425 * 0.2)
                        close_tax = round(price_curr * qty * 0.0015)
                        floating_pnl = (price_curr * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                        
                        is_cumulative_tp = (stock_pnl + floating_pnl) >= (allocated_limit * 0.04)
                        is_limit_up_tp = (entry_price * 1.04 > limit_up) and (price_curr >= limit_up_prev)
                        
                        if is_cumulative_tp or is_limit_up_tp:
                            exit_price = price_curr
                            pnl = floating_pnl
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "SELL",
                                "trade_type": "LONG_CLOSE",
                                "price": exit_price,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": close_tax,
                                "pnl": pnl,
                                "timestamp": timestamp,
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                            position = 0
                            status = "TAKE_PROFIT"
                            break
                            
                elif position == -1: # Short
                    # Stop-loss at +1% price rise (per-position)
                    if price_curr >= entry_price * 1.01:
                        exit_price = round(entry_price * 1.01, 2)
                        close_commission = round(exit_price * qty * 0.001425 * 0.2)
                        pnl = (entry_price * qty) - (exit_price * qty) - open_commission - open_tax - close_commission
                        
                        trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                        simulated_trades.append({
                            "trade_id": trade_id,
                            "username": username,
                            "symbol": symbol,
                            "action": "BUY",
                            "trade_type": "SHORT_CLOSE",
                            "price": exit_price,
                            "qty": qty,
                            "fee": close_commission,
                            "tax": 0.0,
                            "pnl": pnl,
                            "timestamp": timestamp,
                            "tick_type": tick.get("tick_type", "OUTER")
                        })
                        stock_pnl += pnl
                        position = 0
                        status = "STOP_LOSS"
                        break
                        
                    # Take-profit check (cumulative >= 4% or short -4% drop target)
                    else:
                        close_commission = round(price_curr * qty * 0.001425 * 0.2)
                        floating_pnl = (entry_price * qty) - (price_curr * qty) - open_commission - open_tax - close_commission
                        
                        is_cumulative_tp = (stock_pnl + floating_pnl) >= (allocated_limit * 0.04)
                        is_short_tp = (price_curr <= entry_price * 0.96)
                        
                        if is_cumulative_tp or is_short_tp:
                            exit_price = price_curr
                            pnl = floating_pnl
                            
                            trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                            simulated_trades.append({
                                "trade_id": trade_id,
                                "username": username,
                                "symbol": symbol,
                                "action": "BUY",
                                "trade_type": "SHORT_CLOSE",
                                "price": exit_price,
                                "qty": qty,
                                "fee": close_commission,
                                "tax": 0.0,
                                "pnl": pnl,
                                "timestamp": timestamp,
                                "tick_type": tick.get("tick_type", "OUTER")
                            })
                            stock_pnl += pnl
                            position = 0
                            status = "TAKE_PROFIT"
                            break
                            
            # Force Close at 13:30 (last tick) if still open (normally this is handled at 13:10, but keep as fallback)
            if position != 0:
                final_tick = ticks[-1]
                final_price = final_tick["price"]
                final_timestamp = final_tick["timestamp"]
                
                if position == 1:
                    close_commission = round(final_price * qty * 0.001425 * 0.2)
                    close_tax = round(final_price * qty * 0.0015)
                    pnl = (final_price * qty) - (entry_price * qty) - open_commission - close_commission - close_tax
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "SELL",
                        "trade_type": "LONG_CLOSE",
                        "price": final_price,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": close_tax,
                        "pnl": pnl,
                        "timestamp": final_timestamp,
                        "tick_type": final_tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                elif position == -1:
                    close_commission = round(final_price * qty * 0.001425 * 0.2)
                    pnl = (entry_price * qty) - (final_price * qty) - open_commission - open_tax - close_commission
                    
                    trade_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    simulated_trades.append({
                        "trade_id": trade_id,
                        "username": username,
                        "symbol": symbol,
                        "action": "BUY",
                        "trade_type": "SHORT_CLOSE",
                        "price": final_price,
                        "qty": qty,
                        "fee": close_commission,
                        "tax": 0.0,
                        "pnl": pnl,
                        "timestamp": final_timestamp,
                        "tick_type": final_tick.get("tick_type", "OUTER")
                    })
                    stock_pnl += pnl
                position = 0
            
            if status == "ACTIVE":
                status = "SUCCESS"
                
            simulated_summaries.append({
                "username": username,
                "symbol": symbol,
                "name": name,
                "volume": total_vol,
                "open_price": open_price,
                "close_price": close_price,
                "high_price": high_price,
                "low_price": low_price,
                "pnl": round(stock_pnl, 2),
                "trend": trend,
                "status": status
            })
            
        # Insert records into DB
        DayTradingDao.insert_trades(simulated_trades)
        DayTradingDao.insert_summaries(simulated_summaries)
        
        logger.info(f"[Simulation] Finished running Open Price Base simulation for '{username}'. Total trades recorded: {len(simulated_trades)}.")
        return {
            "status": "success",
            "message": f"Simulation completed. Simulated trades: {len(simulated_trades)}."
        }

    @classmethod
    def get_simulation_results(cls, username: str) -> Dict[str, Any]:
        """Retrieves simulation summaries and overall metrics for a user."""
        summaries = DayTradingDao.get_simulation_summary(username)
        total_pnl = 0.0
        win_count = 0
        loss_count = 0
        total_trades = 0
        total_fee = 0.0
        total_tax = 0.0
        traded_stocks_count = 0
        
        # Calculate overall metrics
        for s in summaries:
            total_pnl += s["pnl"]
            if s["status"] != "NOT_TRADED":
                traded_stocks_count += 1
                if s["pnl"] > 0:
                    win_count += 1
                elif s["pnl"] < 0:
                    loss_count += 1
                    
            # Get trades to sum up fee and tax
            trades = DayTradingDao.get_trades_by_symbol(username, s["symbol"])
            total_trades += len(trades)
            for t in trades:
                total_fee += t["fee"]
                total_tax += t["tax"]
                
        win_rate = 0.0
        if (win_count + loss_count) > 0:
            win_rate = round((win_count / (win_count + loss_count)) * 100, 2)
            
        return {
            "summaries": summaries,
            "metrics": {
                "total_pnl": round(total_pnl, 2),
                "win_rate": win_rate,
                "win_count": win_count,
                "loss_count": loss_count,
                "total_trades": total_trades,
                "total_fee": round(total_fee, 2),
                "total_tax": round(total_tax, 2),
                "total_stocks": len(summaries),
                "traded_stocks": traded_stocks_count
            }
        }

    @classmethod
    def get_trades_for_stock(cls, username: str, symbol: str) -> List[Dict[str, Any]]:
        """Retrieves individual trade details for a stock."""
        return DayTradingDao.get_trades_by_symbol(username, symbol)

    @staticmethod
    def get_tick_size(price: float) -> float:
        if price < 10:
            return 0.01
        elif price < 50:
            return 0.05
        elif price < 100:
            return 0.10
        elif price < 500:
            return 0.50
        elif price < 1000:
            return 1.00
        else:
            return 5.00

    @classmethod
    def get_tick_rules(cls) -> List[Dict[str, Any]]:
        """Retrieves tick size and breakeven rules from the database."""
        return DayTradingDao.get_tick_rules()
