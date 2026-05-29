from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)


def show_my_account():
    # --- 1. CHECK HOLDINGS ---
    print("\n" + "="*40)
    print("MY CURRENT HOLDINGS (Positions)")
    print("-" * 40)
    pos = ib.positions()
    if pos:
        for p in pos:
            print(
                f"{p.contract.symbol:6} | Size: {p.position:4} | Cost: {p.avgCost:.2f}")
    else:
        print("Account is empty (Flat).")

    # --- 2. CHECK PENDING ORDERS ---
    print("\n" + "="*40)
    print("ACTIVE ORDERS (Waiting to fill)")
    print("-" * 40)
    trades = ib.openTrades()
    if trades:
        for t in trades:
            print(
                f"{t.contract.symbol:6} | {t.order.action:4} | {t.order.orderType} @ {t.order.lmtPrice}")
    else:
        print("No active orders.")

    # --- 3. CHECK RECENT FILLS ---
    print("\n" + "="*40)
    print("SESSION HISTORY (Fills)")
    print("-" * 40)
    fills = ib.fills()
    if fills:
        for f in fills:
            print(f"{f.contract.symbol:6} | {f.execution.side:4} | Price: {f.execution.avgPrice:.2f} | Time: {f.execution.time}")
    else:
        print("No trades filled this session.")
    print("="*40 + "\n")


show_my_account()
ib.disconnect()
