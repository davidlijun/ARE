from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
ib.reqGlobalCancel()  # Cancel any existing orders to avoid conflicts


def trade_logic():
    contract = Stock('SPY', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    # 1. GET DATA
    bars = ib.reqHistoricalData(contract, endDateTime='', durationStr='2 D',
                                barSizeSetting='1 min', whatToShow='MIDPOINT'
                                , useRTH=False) # Get 2 days of 1-minute bars, including pre/post-market
    df = util.df(bars)

    # 2. CALCULATE INDICATORS
    df['sma9'] = df['close'].rolling(window=9).mean()
    df['sma21'] = df['close'].rolling(window=21).mean()

    curr_price = df['close'].iloc[-1]
    curr_9 = df['sma9'].iloc[-1]
    curr_21 = df['sma21'].iloc[-1]
    prev_9 = df['sma9'].iloc[-2]
    prev_21 = df['sma21'].iloc[-2]

    # 3. SET YOUR OFFSETS (Change these to your liking)
    profit_offset = 0.50  # Take profit $0.50 above entry
    stop_offset = 0.25    # Stop loss $0.25 below entry

    target_price = curr_price + profit_offset
    stop_price = curr_price - stop_offset

    # 4. PRINT THE DASHBOARD (For you to watch)
    print("\n" + "="*30)
    print(f"LIVE MARKET DATA")
    print(f"Current Price: {curr_price:.2f}")
    print(f"SMA 9: {curr_9:.2f} | SMA 21: {curr_21:.2f}")
    print("-" * 30)
    print(f"IF SIGNAL TRIGGERS:")
    print(f" >> Entry (Limit): {curr_price:.2f}")
    print(f" >> Profit Target: {target_price:.2f}")
    print(f" >> Stop Loss:     {stop_price:.2f}")
    print("="*30)

    # 5. EXECUTION LOGIC
    is_crossover = prev_9 <= prev_21 and curr_9 > curr_21

    # Check for existing positions or pending orders
    has_pos = any(p.contract.symbol == 'SPY' for p in ib.positions())
    has_ord = any(t.contract.symbol == 'SPY' for t in ib.openTrades())

    if is_crossover and not has_pos and not has_ord:
        print("!!! SIGNAL MATCHED !!! Sending Bracket Order...")

        bracket = ib.bracketOrder(
            'BUY',
            10,
            limitPrice=curr_price,
            takeProfitPrice=target_price,
            stopLossPrice=stop_price
        )
        for ord in bracket:
            ord.outsideRth = True  # Allow orders outside regular trading hours
            
        for ord in bracket:
            ib.placeOrder(contract, ord)
    elif has_ord:
        print("Status: Waiting for existing order to fill...")
    elif has_pos:
        print("Status: Position active. Watching for exit...")
    else:
        print("Status: Searching for crossover...")


# Loop it
while True:
    trade_logic()
    ib.sleep(30)  # Check every 30 seconds
