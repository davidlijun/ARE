from ib_insync import *
import pandas as pd

ib = IB()
# Using 4002 for Gateway
ib.connect('127.0.0.1', 4002, clientId=2)

def show_my_account():
    # CRITICAL: Wait for a moment to ensure API and TWS are synchronized
    # This helps capture the status change of child orders after a parent fill.
    ib.waitOnUpdate(timeout=0.5)

    # --- 1. CHECK HOLDINGS ---
    print("\n" + "="*60)
    print(f"{'SYMBOL':<10} | {'QTY':<6} | {'AVG COST':<10} | {'MARKET VAL':<10}")
    print("-" * 60)
    pos = ib.positions()
    if pos:
        for p in pos:
            # Note: positions don't have 'marketPrice' easily, 
            # so we focus on Symbol and Size.
            print(f"{p.contract.localSymbol:<10} | {p.position:<6} | {p.avgCost:<10.2f}")
    else:
        print("No open positions.")

    # --- 2. CHECK PENDING ORDERS (TP / SL) ---
    print("\n" + "="*60)
    print(f"{'ID (PRNT)':<12} | {'SYMBOL':<10} | {'SIDE':<5} | {'TYPE':<8} | {'LMT/STP':<8} | {'STATUS'}")
    print("-" * 60)
    trades = ib.openTrades()
    if trades:
        for t in trades:
            # Parent ID will be 0 for the main order, or the ID of the entry for TP/SL
            parent_str = f"{t.order.orderId} ({t.order.parentId})"
            
            # Identify if it's LMT or STP
            price = t.order.lmtPrice if t.order.orderType == 'LMT' else t.order.auxPrice
            
            print(f"{parent_str:<12} | {t.contract.symbol:<10} | {t.order.action:<5} | "
                  f"{t.order.orderType:<8} | {price:<8.2f} | {t.orderStatus.status}")
    else:
        print("No active orders.")

    # --- 3. CHECK RECENT FILLS ---
    print("\n" + "="*60)
    print(f"{'SYMBOL':<10} | {'SIDE':<5} | {'PRICE':<8} | {'TIME'}")
    print("-" * 60)
    fills = ib.fills()
    if fills:
        # Show last 5 fills to keep it clean
        for f in fills[-5:]:
            print(f"{f.contract.symbol:<10} | {f.execution.side:<5} | "
                  f"{f.execution.avgPrice:<8.2f} | {f.execution.time.strftime('%H:%M:%S')}")
    else:
        print("No fills found in this session.")
    print("="*60 + "\n")

# RUN IT
show_my_account()
ib.disconnect()