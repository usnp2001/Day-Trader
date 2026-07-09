from dal.account_dao import AccountDao
from broker import MockBroker

class AccountService:
    @classmethod
    def adjust_cash(cls, username: str, cash: float):
        AccountDao.update_cash(username, cash)
        return {"status": "success", "message": "Cash balance adjusted successfully", "cash": cash}

    @classmethod
    def get_inventory_summary(cls, username: str):
        # Retrieve hold inventory from MockBroker
        user_broker = MockBroker(username=username)
        inventory = user_broker.get_inventory()
        summary = user_broker.get_account_summary()
        return {
            "status": "success",
            "summary": summary,
            "positions": inventory
        }
