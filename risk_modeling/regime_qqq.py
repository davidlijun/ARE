from ib_insync import *
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

# 1. SETUP & CONNECT
# IB Gateway Paper Trading usually uses 4002. Live uses 4001.
ib = IB()


def connect():
    if not ib.isConnected():
        try:
            ib.connect('127.0.0.1', 4001, clientId=1) # Connect to live data for real-time trading
            print("✓ Connected to IB Gateway")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            exit(1)


def execute_bearish_mandelbrot():

    # --- 2. SELECT ATM PUT ---
    qqq = Stock('QQQ', 'SMART', 'USD')
    ib.qualifyContracts(qqq)
    ticker = ib.reqTickers(qqq)[0]

    # Dynamic Strike Selection
    curr_price = ticker.marketPrice()
    strike = round(curr_price)
    today = datetime.datetime.now().strftime('%Y%m%d')

    contract = Option('QQQ', today, strike, 'P', 'SMART')
    ib.qualifyContracts(contract)

    # --- 3. PRICING & SLIPPAGE CONTROL ---
    opt_ticker = ib.reqTickers(contract)[0]
    ib.sleep(2)  # Wait for valid bid/ask

    # Use the MIDPOINT to save money on the entry
    mid_price = round((opt_ticker.bid + opt_ticker.ask) / 2, 2)

    if mid_price <= 0:
        print("Data Error: Check your market data subscriptions.")
        return

    # --- 4. QUANTITY ($1000 Total, $500 Max Risk) ---
    qty = 1  # At $700 QQQ, 1 contract is enough for a $1k account

    # --- 5. BRACKET SETUP ---
    tp_price = round(mid_price * 1.50, 2)  # +50% Profit Target
    sl_price = round(mid_price * 0.60, 2)  # -40% Stop Loss

    bracket = ib.bracketOrder(
        'BUY', qty,
        limitPrice=mid_price,
        takeProfitPrice=tp_price,
        stopLossPrice=sl_price
    )

    print(f"PPI REGIME 4 ENTRY: QQQ {strike} PUT at ${mid_price}")
    for order in bracket:
        ib.placeOrder(contract, order)

    # --- 6. TIME-BASED EXIT (3:00 PM AT) ---
    at_tz = pytz.timezone('Canada/Atlantic')
    while True:
        ib.waitOnUpdate(timeout=30)

        # Auto-exit if trade is finished
        pos = [p for p in ib.positions() if p.contract.conId == contract.conId]
        if not pos or pos[0].position == 0:
            print("Trade complete.")
            break

        # Hard Exit at 3:00 PM AT (2:00 PM ET)
        if datetime.datetime.now(at_tz).hour >= 15:
            print("Mandelbrot Time-Exit Triggered.")
            ib.placeOrder(contract, MarketOrder('SELL', qty))
            break


# START
if __name__ == "__main__":
    connect()
    # WAIT UNTIL 10:30 AM YOUR TIME TO RUN THIS
    execute_bearish_mandelbrot()
