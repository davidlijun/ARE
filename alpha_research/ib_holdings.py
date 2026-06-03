from ib_insync import *
import pandas as pd
from datetime import datetime

ib = IB()
try:
    # clientId=2 (Monitoring Client)
    ib.connect('127.0.0.1', 4002, clientId=2)
except Exception as e:
    print(f"Connection failed: {e}")
    exit()

def show_my_account():
    # Sync everything
    ib.reqAllOpenOrders()
    ib.waitOnUpdate(timeout=0.5)

    # --- 1. HOLDINGS ---
    print("\n" + "="*85)
    print(f"{'SYMBOL':<15} | {'SEC':<4} | {'QTY':<6} | {'AVG COST':<10}")
    print("-" * 85)
    pos = ib.positions()
    if pos:
        for p in pos:
            print(f"{p.contract.localSymbol:<15} | {p.contract.secType:<4} | {p.position:<6} | {p.avgCost:<10.2f}")
    else:
        print("No open positions.")

    # --- 2. OPEN ORDERS + LIVE MARKET PRICE ---
    print("\n" + "="*85)
    print(f"{'ID (PRNT)':<12} | {'SYMBOL':<15} | {'ACTION':<6} | {'ORDER PX':<10} | {'MKT PRICE':<10} | {'STATUS'}")
    print("-" * 85)
    
    trades = ib.openTrades()
    if trades:
        # Get unique contracts from open orders to request prices
        unique_contracts = list({t.contract for t in trades})
        # Batch request market data (more efficient than requesting one by one)
        tickers = ib.reqTickers(*unique_contracts)
        # Create a lookup dictionary: {contractID: ticker_object}
        price_map = {ticker.contract.conId: ticker for ticker in tickers}

        for t in trades:
            # Order Price: TP uses lmtPrice, SL uses auxPrice
            order_px = t.order.lmtPrice if t.order.orderType == 'LMT' else t.order.auxPrice
            parent = f"{t.order.orderId}({t.order.parentId})"
            
            # Look up live market price from our price_map
            ticker = price_map.get(t.contract.conId)
            mkt_px = ticker.marketPrice() if ticker else 0.0
            
            # Handling NaN market prices (common if data hasn't arrived yet)
            mkt_px_str = f"{mkt_px:10.2f}" if mkt_px and not pd.isna(mkt_px) else "  Loading..."

            print(f"{parent:<12} | {t.contract.localSymbol:<15} | {t.order.action:<6} | "
                  f"{order_px:<10.2f} | {mkt_px_str:<10} | {t.orderStatus.status}")
    else:
        print("No active orders found.")

    # --- 3. RECENT FILLS (Timezone Fixed) ---
    print("\n" + "="*85)
    print(f"{'SYMBOL':<15} | {'SIDE':<6} | {'FILL PRICE':<10} | {'LOCAL TIME'}")
    print("-" * 85)
    fills = ib.fills()
    if fills:
        for f in fills[-5:]: # Show last 5 fills
            local_time = f.execution.time.astimezone().strftime('%H:%M:%S')
            print(f"{f.contract.localSymbol:<15} | {f.execution.side:<6} | {f.execution.avgPrice:<10.2f} | {local_time}")
    else:
        print("No trades filled this session.")
    print("="*85 + "\n")

show_my_account()
ib.disconnect()