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
    
    # 1. Position Check
    if get_active_option_qty(symbol, 'C') != 0 or get_active_option_qty(symbol, 'P') != 0:
        return

    # 2. Get Data (5-minute bars)
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    bars = ib.reqHistoricalData(
        stock, endDateTime='', durationStr='2 D',
        barSizeSetting='5 mins', whatToShow='TRADES', useRTH=True
    )
    if not bars: return
    df = util.df(bars)
    
    # 3. Indicators
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['vwap'] = calculate_vwap(df)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # --- 4. DEFINE STATES (The "Alignment" Logic) ---
    # Setup is True only when BOTH EMA and VWAP conditions are met
    last_is_bullish = (last.ema9 > last.ema21) and (last.close > last.vwap)
    prev_was_bullish = (prev.ema9 > prev.ema21) and (prev.close > prev.vwap)

    last_is_bearish = (last.ema9 < last.ema21) and (last.close < last.vwap)
    prev_was_bearish = (prev.ema9 < prev.ema21) and (prev.close < prev.vwap)

    # Trigger only when the state switches from False to True
    bullish_signal = last_is_bullish and not prev_was_bullish
    bearish_signal = last_is_bearish and not prev_was_bearish

    # --- 5. OPTIONAL EXTENSION FILTER ---
    # If price is > 0.1% away from EMA21, it's considered "chasing"
    # For SPY at $530, 0.1% is about $0.53. 
    max_extension = 0.0010 
    
    def is_overextended(current_price, ema_ref):
        extension = abs(current_price - ema_ref) / ema_ref
        return extension > max_extension

    # --- 6. EXECUTION ---
    if bullish_signal:
        if is_overextended(last.close, last.ema21):
            print(f"(!) Bullish Signal Ignored: Price is overextended from EMA21.")
            return
            
        print(f">>> CALL SIGNAL: Setup Aligned. Price: {last.close:.2f}")
        contract = get_atm_option(symbol, 'C')
        place_bracket_order(contract)

    elif bearish_signal:
        if is_overextended(last.close, last.ema21):
            print(f"(!) Bearish Signal Ignored: Price is overextended from EMA21.")
            return

        print(f">>> PUT SIGNAL: Setup Aligned. Price: {last.close:.2f}")
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
