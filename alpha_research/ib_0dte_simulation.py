from ib_insync import *
import pandas as pd
from datetime import datetime, time, timedelta
# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=10)
ib.reqGlobalCancel()  # Cancel any existing orders to avoid conflicts


def simulate_340_lotto(symbol='SPY', date='20260529'):
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    # 1. Get 1-minute bars for the very end of a specific day
    # Example: Looking at the end of yesterday (change the date to test others)
    bars = ib.reqHistoricalData(
        stock, 
        endDateTime=f'{date} 16:00:00 US/Eastern', 
        durationStr='1 D',
        barSizeSetting='1 min', 
        whatToShow='TRADES', 
        useRTH=True
    )
    if not bars:
        print("No data received. Retrying...")
        return
    df = util.df(bars)
    print(df[['date', 'open', 'high', 'low', 'close']].tail(5))  # Show last 5 bars to verify we have the right data
    # 2. Extract the price at exactly 3:40 PM (15:40)
    # Note: IBKR timestamps are often the 'end' of the bar.
    entry_row = df[df['date'].dt.strftime('%H:%M') == '15:40']
    exit_row = df[df['date'].dt.strftime('%H:%M') == '15:59']
    print("\n--- Price at 3:40 PM ---")
    if not entry_row.empty:
        print(entry_row[['date', 'open', 'high', 'low', 'close']])
    else:
        print("No bar found for 3:40 PM. Check the timestamps and time zone.")
        return
    if not exit_row.empty:
        print("\n--- Price at 4:00 PM ---")
        print(exit_row[['date', 'open', 'high', 'low', 'close']])
    else:
        print("No bar found for 4:00 PM. Check the timestamps and time zone.")
        return
    if not entry_row.empty and not exit_row.empty:
        entry_price = entry_row.iloc[0]['close']
        exit_price = exit_row.iloc[0]['close']
        move = exit_price - entry_price
        pct_change = (move / entry_price) * 100
        
        print(f"--- Simulation for {symbol} ---")
        print(f"Price at 3:40 PM: {entry_price:.2f}")
        print(f"Price at 4:00 PM: {exit_price:.2f}")
        print(f"Total Move: {move:.2f} ({pct_change:.2f}%)")
        
        # 3. Estimate 0DTE Option Gain
        # 0DTE options at 3:40 PM have a Delta near 0.50 and Gamma is huge.
        # A $1.00 move in SPY usually results in a 100% - 300% gain at this time.
        if abs(move) > 0.50:
            print(">>> Result: High probability of 100%+ gain on an ATM Option.")
        else:
            print(">>> Result: Option likely expired worthless due to Theta decay.")


# Run simulations from 2026-01-01 until today (inclusive)
start = datetime(2026, 1, 1)
end = datetime.today()
cur = start
while cur.date() <= end.date():
    test_date = cur.strftime('%Y%m%d')
    print(f"\n\n=== Simulating for Date: {test_date} ===")
    simulate_340_lotto(date=test_date)
    cur += timedelta(days=1)