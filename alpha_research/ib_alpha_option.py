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

def get_actual_option_position(symbol):
    """
    Checks the account specifically for OPTION positions 
    on the underlying symbol, ignoring Stock (STK) positions.
    """
    positions = ib.positions()
    for p in positions:
        # Match symbol (SPY) AND security type (OPT)
        if p.contract.symbol == symbol and p.contract.secType == 'OPT':
            if p.position != 0:
                print(f"Active Option Position found: {p.contract.localSymbol} ({p.position} qty)")
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

def get_atm_call(symbol):
    """Finds the 0DTE ATM Call Option."""
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    tickers = ib.reqTickers(stock)
    ib.sleep(1)
    market_price = tickers[0].marketPrice()

    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    # Filter for SMART exchange chain
    chain = next(c for c in chains if c.exchange == 'SMART')
    
    # 0DTE is the first available expiration
    expiry = chain.expirations[0]
    # Find strike closest to current market price
    strike = min(chain.strikes, key=lambda x: abs(x - market_price))
    
    contract = Option(symbol, expiry, strike, 'C', 'SMART')
    ib.qualifyContracts(contract)
    return contract

def run_strategy():
    connect()
    
    symbol = 'SPY'
    
    # Check if we already have a position
    if get_actual_option_position(symbol) != 0:
        # print(f"Already holding {symbol}. Skipping entry scan...")
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
    
    print(f"Price: {last.close:.2f} | EMA9: {last.ema9:.2f} | EMA21: {last.ema21:.2f} | VWAP: {last.vwap:.2f}")

    # 4. SIGNAL LOGIC
    # Condition 1: 9 EMA crosses ABOVE 21 EMA
    crossover = prev.ema9 <= prev.ema21 and last.ema9 > last.ema21
    # Condition 2: Price is above VWAP (Bullish Filter)
    above_vwap = last.close > last.vwap
    
    if crossover and above_vwap:
        print(">>> LONG SIGNAL DETECTED (EMA Cross + Price > VWAP)")
        
        try:
            call_contract = get_atm_call(symbol)
            
            # Get current option price
            opt_ticker = ib.reqTickers(call_contract)[0]
            ib.sleep(1)
            opt_price = opt_ticker.marketPrice()
            
            if np.isnan(opt_price) or opt_price <= 0:
                print("Could not get valid option price. Aborting.")
                return

            # 5. EXECUTION (Bracket Order)
            # 20% Profit Target / 10% Stop Loss
            bracket = ib.bracketOrder(
                'BUY', 1,
                limitPrice=round(opt_price, 2),
                takeProfitPrice=round(opt_price * 1.20, 2),
                stopLossPrice=round(opt_price * 0.90, 2)
            )

            for o in bracket:
                ib.placeOrder(call_contract, o)
            
            print(f"✓ Bracket Order Placed for {call_contract.localSymbol} @ {opt_price}")

        except Exception as e:
            print(f"Order error: {e}")

# 6. LOOP
print("Bot started. Scanning every 60 seconds...")
while True:
    try:
        run_strategy()
    except Exception as e:
        print(f"Error in main loop: {e}")
    ib.sleep(60)