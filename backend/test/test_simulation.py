import sys
import os
import unittest

# Force SQLite for local unit testing
os.environ["DB_TYPE"] = "sqlite"

# Setup sys.path to resolve backend package imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dal.database_init import init_db
from dal.day_trading_dao import DayTradingDao
from service.day_trading_service import DayTradingService

class TestDayTradingSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize database tables
        init_db()

    def test_01_import_ticks(self):
        print("\n--- Testing Tick Import (Top 50 Volume) ---")
        res = DayTradingService.import_top_50_ticks()
        self.assertEqual(res["status"], "success")
        print(res["message"])
        
        # Verify that ticks are in DB
        ticks = DayTradingDao.get_all_ticks()
        self.assertGreater(len(ticks), 0)
        print(f"Total ticks in database: {len(ticks)}")

    def test_02_run_simulation_lots_and_costs(self):
        print("\n--- Testing Simulation Execution ---")
        # Run with limit NT$ 500,000
        res = DayTradingService.run_simulation("admin", 500000.0)
        self.assertEqual(res["status"], "success")
        print(res["message"])
        
        # Get results
        results = DayTradingService.get_simulation_results("admin")
        self.assertIn("summaries", results)
        self.assertIn("metrics", results)
        
        metrics = results["metrics"]
        print("Simulation Metrics:")
        print(f"  Total PnL: NT$ {metrics['total_pnl']}")
        print(f"  Win Rate: {metrics['win_rate']}%")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Total Fee: NT$ {metrics['total_fee']}")
        print(f"  Total Tax: NT$ {metrics['total_tax']}")
        print(f"  Traded/Total Stocks: {metrics['traded_stocks']}/{metrics['total_stocks']}")

        # Ensure trade quantities are multiples of 1,000
        summaries = results["summaries"]
        has_trades = False
        for s in summaries:
            trades = DayTradingService.get_trades_for_stock("admin", s["symbol"])
            if trades:
                has_trades = True
                for t in trades:
                    self.assertEqual(t["qty"] % 1000, 0)
                    self.assertGreaterEqual(t["qty"], 1000)
                    # Verify fee calculation
                    expected_fee = round(t["price"] * t["qty"] * 0.001425 * 0.2)
                    self.assertEqual(t["fee"], expected_fee)
                    # Verify tax calculation (only on sell actions)
                    if t["action"] == "SELL":
                        expected_tax = round(t["price"] * t["qty"] * 0.0015)
                        self.assertEqual(t["tax"], expected_tax)
                    else:
                        self.assertEqual(t["tax"], 0.0)

        self.assertTrue(has_trades, "At least one stock should have executed trades")

    def test_03_budget_skipping(self):
        print("\n--- Testing Budget Allocation Skipping ---")
        # Run with a very low limit (NT$ 20,000)
        # Any stock with price > 20 should be skipped (not traded)
        res = DayTradingService.run_simulation("admin", 20000.0)
        self.assertEqual(res["status"], "success")
        
        results = DayTradingService.get_simulation_results("admin")
        summaries = results["summaries"]
        
        skipped_count = 0
        traded_count = 0
        for s in summaries:
            if s["status"] == "NOT_TRADED":
                skipped_count += 1
                # The open price must be greater than limit / 1000 = 20.0
                self.assertGreater(s["open_price"], 20.0)
            else:
                traded_count += 1
                # The open price must be <= 20.0
                self.assertLessEqual(s["open_price"], 20.0)
                
        print(f"At NT$ 20,000 budget: Traded: {traded_count}, Skipped: {skipped_count}")
        self.assertGreater(skipped_count, 0)

    def test_04_tick_rules_and_exit_times(self):
        print("\n--- Testing Tick Rules Seeding & 13:10 Force Close ---")
        
        # 1. Verify tick rules are seeded and retrieved
        rules = DayTradingService.get_tick_rules()
        self.assertEqual(len(rules), 6) # 6 price intervals standard
        for r in rules:
            self.assertIn("price_min", r)
            self.assertIn("price_max", r)
            self.assertIn("tick_size", r)
            self.assertIn("breakeven_30", r)
            self.assertIn("breakeven_20", r)
            self.assertIn("breakeven_10", r)
            
            # Verify breakeven ordering: 3折 (highest commission) >= 2折 >= 1折 (lowest commission)
            self.assertGreaterEqual(r["breakeven_30"], r["breakeven_20"])
            self.assertGreaterEqual(r["breakeven_20"], r["breakeven_10"])
            
        print(f"Seeded tick rules retrieved successfully: {len(rules)} rules.")
        
        # 2. Run simulation and check trade timestamps (must be <= 13:10:00)
        res = DayTradingService.run_simulation("admin", 500000.0)
        self.assertEqual(res["status"], "success")
        
        results = DayTradingService.get_simulation_results("admin")
        summaries = results["summaries"]
        
        trade_count_after_1310 = 0
        total_checked_trades = 0
        
        for s in summaries:
            trades = DayTradingService.get_trades_for_stock("admin", s["symbol"])
            for t in trades:
                total_checked_trades += 1
                if t["timestamp"] > "13:10:00":
                    trade_count_after_1310 += 1
                    
        print(f"Checked {total_checked_trades} trades. Trades after 13:10: {trade_count_after_1310}")
        self.assertEqual(trade_count_after_1310, 0, "No trades should be executed after 13:10:00 due to force-close and stop-trading rule")

    def test_05_run_simulation_open_base(self):
        print("\n--- Testing Open Price Base Simulation ---")
        # Run with limit NT$ 500,000
        res = DayTradingService.run_simulation_open_base("admin", 500000.0)
        self.assertEqual(res["status"], "success")
        print(res["message"])
        
        # Get results
        results = DayTradingService.get_simulation_results("admin")
        self.assertIn("summaries", results)
        self.assertIn("metrics", results)
        
        metrics = results["metrics"]
        print("Open Price Base Simulation Metrics:")
        print(f"  Total PnL: NT$ {metrics['total_pnl']}")
        print(f"  Win Rate: {metrics['win_rate']}%")
        print(f"  Total Trades: {metrics['total_trades']}")
        
        # Verify that we have at least one trade and no trades after 13:10:00
        self.assertGreater(metrics["total_trades"], 0)
        
        summaries = results["summaries"]
        trade_count_after_1310 = 0
        for s in summaries:
            trades = DayTradingService.get_trades_for_stock("admin", s["symbol"])
            for t in trades:
                if t["timestamp"] > "13:10:00":
                    trade_count_after_1310 += 1
        self.assertEqual(trade_count_after_1310, 0, "No trades should be executed after 13:10:00 in Open Price Base strategy")

if __name__ == "__main__":
    unittest.main()
