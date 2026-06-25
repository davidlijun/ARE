import datetime
import time
import pytz
import numpy as np
import pandas as pd
from ib_insync import *
from risk_modeling.mandelbrot import calculate_tail_index, calculate_hurst


class MandelbrotRecoveryBot:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', PORT, clientId=1)
        self.ib.reqMarketDataType(4)  # Switch to delayed-frozen data if live not available
        self.contract = Stock(TICKER, 'SMART', 'USD', primaryExchange='NASDAQ')
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
                self.contract, '', durationStr='1 D', barSizeSetting='1 min', whatToShow='TRADES', useRTH=False)
            if not bars:
                print(f"[{now_at.strftime('%H:%M:%S')}] No data received. Checking connection...")
                if not self.ib.isConnected():
                    self.ib.reconnect()
                self.ib.sleep(5) # Wait before retry
                continue
            prices = np.array([b.close for b in bars])
            print(f"=====Fetched {len(prices)} price bars for analysis.")
            volumes = np.array([b.volume for b in bars])
            returns = np.diff(prices) / prices[:-1]

            # 4. CALCULATE MANDELBROT INDICATORS
            # Volume weighting can be added if desired
            hurst = calculate_hurst(prices, volumes)
            alpha = calculate_tail_index(returns)
            current_price = prices[-1]

            print(
                f"=====[{now_at.strftime('%H:%M:%S')}] Price: {current_price:.2f}, Volume: {volumes[-1]} | Hurst: {hurst:.3f} | Alpha: {alpha:.2f}")

            # 5. TRADE LOGIC (RECOVERY MODE)
            qty = self.get_position_size()

            # ENTRY: If Hurst > 0.55 (Stable Trend) and not in a position
            if qty == 0 and hurst > HURST_THRESHOLD and alpha > 1.6:
                print(f"REGIME 1 DETECTED. Buying ${RECOVERY_CASH} of {TICKER}")
                
                # Create a Market Order but use cashQty instead of quantity
                # Calculate the share quantity
                calculated_shares = RECOVERY_CASH / current_price 
                order = MarketOrder('BUY', calculated_shares)  # Quantity is 0 because we use cashQty
                
                trade = self.ib.placeOrder(self.contract, order)
                print(f"Order placed: {trade.orderStatus.status}")
                time.sleep(10)  # Wait for order to process
            # EXIT Logic (Selling fractionals)
            elif qty > 0 and hurst < HURST_UNSTABLE_MAX:
                print(f"REGIME 4 DETECTED. Liquidating fractional position: {qty}")
                time.sleep(10)  # Wait for order to process
                # For selling, you MUST use the exact quantity (fractional) 
                # but use a Market Order. IBKR allows fractional SELL orders 
                # for positions you already hold.
                self.ib.placeOrder(self.contract, MarketOrder('SELL', qty))


# --- EXECUTION ---
if __name__ == "__main__":
    PORT = 4001
    TICKER = 'MRVL'
    RECOVERY_CASH = 43  # Your current balance
    MAX_ACCOUNT_DRAWDOWN = 0.15  # 15% Total Stop Loss
    HURST_THRESHOLD = 0.55       # Minimum persistence to enter
    HURST_UNSTABLE_MAX = 0.40    # Max Hurst for unstable regime
    TIME_EXIT_AT = "17:00"       # 3:00 PM Atlantic Time

    bot = MandelbrotRecoveryBot()
    try:
        bot.run_strategy()
    except KeyboardInterrupt:
        bot.ib.disconnect()
