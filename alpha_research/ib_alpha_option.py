from ib_insync import *
import pandas as pd
import numpy as np
from datetime import datetime

# 1. SETUP & CONNECT
# IB Gateway Paper Trading usually uses 4002. Live uses 4001.
ib = IB()


def connect():
    if not ib.isConnected():
        try:
            ib.connect('127.0.0.1', 4002, clientId=1)
            print("✓ Connected to IB Gateway")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            exit(1)


def get_active_option_qty(symbol, right):
    """Checks for existing 'C' (Call) or 'P' (Put) positions for a symbol."""
    positions = ib.positions()
    for p in positions:
        # Check symbol, check it's an option, and check if it's the right (C or P)
        if p.contract.symbol == symbol and p.contract.secType == 'OPT' and p.contract.right == right:
            if p.position != 0:
                return p.position
    return 0


def calculate_vwap(df):
    """Calculates the Volume Weighted Average Price (VWAP) for the current day."""
    # Ensure we are only calculating VWAP for the current trading session
    df['date'] = pd.to_datetime(df['date'])
    current_day = df['date'].dt.date.iloc[-1]
    day_df = df[df['date'].dt.date == current_day].copy()

    tp = (day_df['high'] + day_df['low'] + day_df['close']) / 3
    return (tp * day_df['volume']).cumsum() / day_df['volume'].cumsum()


def get_atm_option(symbol, right):
    """Finds the 0DTE ATM Option (C or P)."""
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    tickers = ib.reqTickers(stock)
    ib.sleep(1)
    market_price = tickers[0].marketPrice()

    chains = ib.reqSecDefOptParams(
        stock.symbol, '', stock.secType, stock.conId)
    chain = next(c for c in chains if c.exchange == 'SMART')

    expiry = chain.expirations[0]  # 0DTE
    strike = min(chain.strikes, key=lambda x: abs(x - market_price))

    contract = Option(symbol, expiry, strike, right, 'SMART')
    ib.qualifyContracts(contract)
    return contract


def place_bracket_order(contract, action='BUY'):
    """Calculates entry and places bracket: 20% Profit / 10% Stop."""
    # 1. Get the price
    opt_ticker = ib.reqTickers(contract)[0]
    ib.sleep(1)
    price = opt_ticker.marketPrice()

    if np.isnan(price) or price <= 0:
        print(f"Invalid price for {contract.localSymbol}. Aborting.")
        return

    # 2. DEFINE right_full HERE so the print statement works
    # This checks if the contract is a Call ('C') or Put ('P')
    right_full = "CALL" if contract.right == 'C' else "PUT"

    # 3. Create the Bracket
    bracket = ib.bracketOrder(
        action, 1,
        limitPrice=round(price, 2),
        takeProfitPrice=round(price * 1.20, 2),
        stopLossPrice=round(price * 0.90, 2)
    )

    # 4. Place the orders
    for o in bracket:
        ib.placeOrder(contract, o)

    # Now right_full will correctly print "CALL" or "PUT"
    print(f"✓ {right_full} Bracket Placed: {contract.localSymbol} @ {price}")


def run_strategy():
    connect()

    symbol = 'SPY'

    # Check if we are already in ANY SPY option position (to avoid double-hedging)
    if get_active_option_qty(symbol, 'C') != 0 or get_active_option_qty(symbol, 'P') != 0:
        return

    # 2. DATA ACQUISITION (5-minute bars)
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    # Requesting 2 days to ensure enough data for the indicators
    bars = ib.reqHistoricalData(
        stock, endDateTime='', durationStr='2 D',
        barSizeSetting='5 mins', whatToShow='TRADES', useRTH=True
    )

    if not bars:
        print("Waiting for data...")
        return

    df = util.df(bars)

    # 3. INDICATORS
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['vwap'] = calculate_vwap(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    print(
        f"Price: {last.close:.2f} | EMA9: {last.ema9:.2f} | EMA21: {last.ema21:.2f} | VWAP: {last.vwap:.2f}")

    # 4. SIGNAL LOGIC
    bullish_cross = prev.ema9 <= prev.ema21 and last.ema9 > last.ema21
    bearish_cross = prev.ema9 >= prev.ema21 and last.ema9 < last.ema21

    # --- CALL LOGIC ---
    if bullish_cross and last.close > last.vwap:
        print(
            f">>> CALL SIGNAL: Price({last.close:.2f}) > VWAP({last.vwap:.2f})")
        contract = get_atm_option(symbol, 'C')
        place_bracket_order(contract)

    # --- PUT LOGIC ---
    elif bearish_cross and last.close < last.vwap:
        print(
            f">>> PUT SIGNAL: Price({last.close:.2f}) < VWAP({last.vwap:.2f})")
        contract = get_atm_option(symbol, 'P')
        place_bracket_order(contract)


# 6. LOOP
print("Bot started. Scanning every 60 seconds...")
while True:
    try:
        run_strategy()
    except Exception as e:
        print(f"Error in main loop: {e}")
    ib.sleep(60)
