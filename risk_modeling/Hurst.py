import datetime
import pytz
import numpy as np
import pandas as pd
from ib_insync import *
from risk_alert import calculate_tail_index, calculate_hurst


class MandelbrotRecoveryBot:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', PORT, clientId=1)
        self.ib.reqMarketDataType(3)  # Switch to delayed-frozen data if live not available
        self.contract = Stock(TICKER, 'NASDAQ', 'USD')
        self.ib.qualifyContracts(self.contract)
        self.initial_equity = self.get_total_equity()
        print(f"Bot Initialized. Starting Balance: ${self.initial_equity}")

    def get_total_equity(self):
        account = self.ib.accountSummary()
        return float([v.value for v in account if v.tag == 'NetLiquidation'][0])

    def check_kill_switch(self):
        """If account drops 15%, close everything and stop."""
        current_equity = self.get_total_equity()
        drawdown = (self.initial_equity - current_equity) / self.initial_equity
        if drawdown >= MAX_ACCOUNT_DRAWDOWN:
            print(f"!!! KILL SWITCH TRIGGERED: DRAWDOWN {drawdown:.1%} !!!")
            self.ib.reqGlobalCancel()
            self.ib.placeOrder(self.contract, MarketOrder(
                'SELL', self.get_position_size()))
            self.ib.disconnect()
            exit()

    def get_position_size(self):
        pos = [p for p in self.ib.positions() if p.contract.symbol == TICKER]
        return pos[0].position if pos else 0

    def run_strategy(self):
        at_tz = pytz.timezone('Canada/Atlantic')

        while True:
            self.ib.waitOnUpdate(timeout=30)
            now_at = datetime.datetime.now(at_tz)

            # 1. TIME EXIT CHECK (3:00 PM AT)
            if now_at.strftime("%H:%M") >= TIME_EXIT_AT:
                qty = self.get_position_size()
                if qty != 0:
                    print("Time Exit Reached. Liquidating.")
                    self.ib.placeOrder(self.contract, MarketOrder(
                        'SELL' if qty > 0 else 'BUY', abs(qty)))
                break

            # 2. EMERGENCY KILL SWITCH CHECK
            self.check_kill_switch()

            # 3. DATA ACQUISITION
            bars = self.ib.reqHistoricalData(
                self.contract, '', durationStr='1 D', barSizeSetting='1 min', whatToShow='MIDPOINT', useRTH=True)
            prices = np.array([b.close for b in bars])
            print(f"Fetched {len(prices)} price bars for analysis.")
            volumes = np.array([b.volume for b in bars])
            returns = np.diff(prices) / prices[:-1]

            # 4. CALCULATE MANDELBROT INDICATORS
            # Volume weighting can be added if desired
            hurst = calculate_hurst(prices, volumes)
            alpha = calculate_tail_index(returns)
            current_price = prices[-1]

            print(
                f"[{now_at.strftime('%H:%M:%S')}] Price: {current_price:.2f} | Hurst: {hurst:.3f} | Alpha: {alpha:.2f}")

            # 5. TRADE LOGIC (RECOVERY MODE)
            qty = self.get_position_size()

            # ENTRY: If Hurst > 0.55 (Stable Trend) and not in a position
            if qty == 0 and hurst > HURST_THRESHOLD and alpha > 1.6:
                # Calculate fractional shares for $50
                # Note: IBKR accounts must be enabled for fractional trading
                target_qty = round(RECOVERY_CASH / current_price, 4)
                print(
                    f"REGIME 1 DETECTED. Buying ${RECOVERY_CASH} of {TICKER} ({target_qty} shares)")
                self.ib.placeOrder(
                    self.contract, MarketOrder('BUY', target_qty))

            # EXIT: If Hurst drops below 0.45 (Trend Failure / Noise)
            elif qty > 0 and hurst < 0.45:
                print(
                    f"REGIME 4 DETECTED. Hurst {hurst:.3f} is too low. Exiting to Cash.")
                self.ib.placeOrder(self.contract, MarketOrder('SELL', qty))


# --- EXECUTION ---
if __name__ == "__main__":
    PORT = 4001
    TICKER = 'QQQ'
    RECOVERY_CASH = 50.0  # Your current balance
    MAX_ACCOUNT_DRAWDOWN = 0.15  # 15% Total Stop Loss
    HURST_THRESHOLD = 0.55       # Minimum persistence to enter
    TIME_EXIT_AT = "17:00"       # 3:00 PM Atlantic Time

    bot = MandelbrotRecoveryBot()
    try:
        bot.run_strategy()
    except KeyboardInterrupt:
        bot.ib.disconnect()
