from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)


def trade_logic():
    # Define Contract
    contract = Stock('SPY', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    # Get Data
    bars = ib.reqHistoricalData(contract, endDateTime='', durationStr='2 D',
                                barSizeSetting='1 min', whatToShow='MIDPOINT', useRTH=True)
    df = util.df(bars)

    # Simple Math (9-period Moving Average)
    df['ma'] = df['close'].rolling(window=9).mean()
    current_price = df['close'].iloc[-1]
    current_ma = df['ma'].iloc[-1]

    print(f"Checking SPY: Price {current_price} | MA {current_ma:.2f}")

    # 2. THE RULE (Buy when price crosses above MA)
    # Check if we are already in a trade
    positions = ib.positions()
    has_position = any(p.contract.symbol == 'SPY' for p in positions)

    if current_price > current_ma and not has_position:
        print(">>> SIGNAL DETECTED. Executing Bracket Order...")

        # 3. THE BRACKET (The Anti-Emotion Tool)
        # Entry: Market Price
        # Take Profit: +$2.00
        # Stop Loss: -$1.00
        bracket = ib.bracketOrder(
            'BUY',
            10,                   # Quantity
            limitPrice=current_price,
            takeProfitPrice=current_price + 2.00,
            stopLossPrice=current_price - 1.00
        )

        for ord in bracket:
            ib.placeOrder(contract, ord)
        print(">>> Strategy active. Stop-loss and Take-profit are SET.")


# 4. THE INFINITE LOOP
while True:
    trade_logic()
    # print("Sleeping for 60 seconds...")
    ib.sleep(60)  # ib.sleep is better than time.sleep for connection stability
