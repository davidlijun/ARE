from ib_insync import *
import pandas as pd
from datetime import datetime, time
# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
ib.reqGlobalCancel()  # Cancel any existing orders to avoid conflicts


def get_0dte_call(symbol):
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    # Get today's date for 0DTE
    today = datetime.now().strftime('%Y%m%d')
    # Request chains
    chains = ib.reqSecDefOptParams(
        stock.symbol, '', stock.secType, stock.conId)
    chain = next(c for c in chains if c.exchange == 'SMART')

    # Verify today is an expiration day
    if today not in chain.expirations:
        print(
            f"Warning: {today} is not a 0DTE day for {symbol}. Picking next available.")
        expiry = chain.expirations[0]
    else:
        expiry = today

    ticker = ib.reqTickers(stock)[0]
    strike = min(chain.strikes, key=lambda x: abs(x - ticker.marketPrice()))

    contract = Option(symbol, expiry, strike, 'C', 'SMART')
    ib.qualifyContracts(contract)
    return contract


def exit_all():
    print(f"[{datetime.now()}] 3:59 PM REACHED. EXECUTING HARD EXIT.")
    # 1. Cancel the Take Profit order so it doesn't conflict
    ib.reqGlobalCancel()
    ib.sleep(1)

    # 2. Close any open position
    for p in ib.positions():
        if p.contract.symbol == 'SPY':
            order = MarketOrder('SELL', p.position)
            ib.placeOrder(p.contract, order)
            print(
                f"Closed {p.position} shares/contracts of {p.contract.symbol}")


def enter_trade():
    print(f"[{datetime.now()}] 3:40 PM REACHED. ENTERING 0DTE LOTTO.")
    contract = get_0dte_call('SPY')

    # Get current midpoint for entry
    [ticker] = ib.reqTickers(contract)
    entry_price = ticker.marketPrice()

    # 20% Take Profit, no Stop Loss (The 3:59 PM exit IS the stop loss)
    # We use a Limit order for entry and a Limit for profit
    parent = MarketOrder('BUY', 1)
    take_profit = LimitOrder('SELL', 1, lmtPrice=round(entry_price * 1.30, 2))

    # Manually attach them (simpler than bracket for this specific case)
    take_profit.parentId = parent.orderId

    ib.placeOrder(contract, parent)
    ib.placeOrder(contract, take_profit)
    print(
        f"Entered @ {entry_price}. Take Profit set at {take_profit.lmtPrice}")


# --- SCHEDULER ---
# Use ib.schedule to trigger functions at specific times
print("Bot Active. Waiting for 3:40 PM and 3:59 PM triggers...")

ib.schedule(time(15, 40), enter_trade)
ib.schedule(time(15, 59), exit_all)

ib.run()  # Keeps the script alive and waiting
