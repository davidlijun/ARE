from ib_insync import *
import pandas as pd
from datetime import datetime

# 1. CONNECT
ib = IB()
try:
    # clientId=2 is fine, but we will call reqAllOpenOrders() to see everything
    ib.connect('127.0.0.1', 4002, clientId=2)
except Exception as e:
    print(f"Connection failed: {e}")
    exit()

def show_my_account():
    # --- CRITICAL FIX 1: SYNC ALL ORDERS ---
    # This pulls orders from TWS, Mobile, and other API clients
    ib.reqAllOpenOrders() 
    ib.waitOnUpdate(timeout=0.5)

    # --- 1. CHECK HOLDINGS ---
    print("\n" + "="*70)
    print(f"{'SYMBOL':<12} | {'SEC':<4} | {'QTY':<6} | {'AVG COST':<10}")
    print("-" * 70)
    pos = ib.positions()
    if pos:
        for p in pos:
            # Show localSymbol (e.g., 'SPY 260603C00530000') for options
            print(f"{p.contract.localSymbol:<12} | {p.contract.secType:<4} | {p.position:<6} | {p.avgCost:<10.2f}")
    else:
        print("No open positions.")

    # --- 2. CHECK ALL OPEN ORDERS (Including TP/SL) ---
    print("\n" + "="*70)
    print(f"{'ID (PRNT)':<12} | {'SYMBOL':<10} | {'ACTION':<6} | {'LMT/STP':<8} | {'STATUS'}")
    print("-" * 70)
    trades = ib.openTrades()
    if trades:
        for t in trades:
            # Handle price: TP uses lmtPrice, SL uses auxPrice
            price = t.order.lmtPrice if t.order.orderType == 'LMT' else t.order.auxPrice
            parent = f"{t.order.orderId}({t.order.parentId})"
            
            print(f"{parent:<12} | {t.contract.symbol:<10} | {t.order.action:<6} | {price:<8.2f} | {t.orderStatus.status}")
    else:
        print("No active orders found. (Try placing one in TWS to test)")

    # --- 3. CHECK RECENT FILLS (Timezone Fixed) ---
    print("\n" + "="*70)
    print(f"{'SYMBOL':<12} | {'SIDE':<6} | {'PRICE':<8} | {'LOCAL TIME'}")
    print("-" * 70)
    fills = ib.fills()
    if fills:
        for f in fills:
            # --- CRITICAL FIX 2: TIMEZONE CONVERSION ---
            # astimezone() converts UTC to your local system time
            local_fill_time = f.execution.time.astimezone().strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"{f.contract.symbol:<12} | {f.execution.side:<6} | {f.execution.avgPrice:<8.2f} | {local_fill_time}")
    else:
        print("No trades filled this session.")
    print("="*70 + "\n")

show_my_account()
ib.disconnect()