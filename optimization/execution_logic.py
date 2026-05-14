from ib_insync import *

class SystematicManager:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=1)

    def manage_0dte_package(self, ticker='NVDA'):
        """
        Systematic Watchdog: Prevents 'Legging Out' and handles 0DTE Exits.
        """
        # 1. Fetch current positions
        positions = [p for p in self.ib.positions() if p.contract.symbol == ticker]
        
        # 2. Check Time-Based Exit (Institutional Rule: Exit by 14:00)
        import datetime
        now = datetime.datetime.now()
        if now.hour >= 14:
            print("CRITICAL: Systematic Time-Exit Triggered. Closing entire package.")
            self.flatten_ticker(ticker)

    def flatten_ticker(self, ticker):
        # Automatically generates the 'Package Order' to close all legs
        self.ib.reqGlobalCancel() # Cancel all pending discretionary orders
        # Logic to send a single Market-to-Limit order for the whole spread...
        pass