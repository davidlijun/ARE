from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

def run_strategy():
    print("Requesting market data...")
    
    # 2. DEFINE THE ASSET (The "Broad Market")
    contract = Stock('SPY', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    # 3. REQUEST DATA (The "Bars")
    # We ask for 5 days of 1-hour bars
    bars = ib.reqHistoricalData(
        contract, endDateTime='', durationStr='5 D',
        barSizeSetting='1 hour', whatToShow='MIDPOINT', useRTH=True)

    # Convert bars to a Dataframe (Spreadsheet format)
    df = util.df(bars)
    
    # 4. THE LOGIC (The "Signal")
    # Calculate a Short Moving Average (9 periods) and Long (21 periods)
    df['SMA_9'] = df['close'].rolling(window=9).mean()
    df['SMA_21'] = df['close'].rolling(window=21).mean()

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    print(f"Current Price: {last_row['close']}")
    print(f"SMA 9: {last_row['SMA_9']:.2f} | SMA 21: {last_row['SMA_21']:.2f}")

    # 5. THE DECISION (Crossover Logic)
    # If the 9-period average crosses ABOVE the 21-period average: BUY
    if last_row['SMA_9'] > last_row['SMA_21'] and prev_row['SMA_9'] <= prev_row['SMA_21']:
        print(">>> SIGNAL: BULLISH CROSSOVER. Place Buy Order.")
        # To actually buy, uncomment the line below:
        # order = MarketOrder('BUY', 10)
        # ib.placeOrder(contract, order)
    
    elif last_row['SMA_9'] < last_row['SMA_21'] and prev_row['SMA_9'] >= prev_row['SMA_21']:
        print(">>> SIGNAL: BEARISH CROSSOVER. Place Sell Order.")
    
    else:
        print(">>> SIGNAL: No crossover detected. Holding.")

# Run the strategy
run_strategy()

# Disconnect
ib.disconnect()