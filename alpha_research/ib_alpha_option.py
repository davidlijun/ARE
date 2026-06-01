from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 7497 is for Paper Trading. ClientID can be any number.
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
ib.reqGlobalCancel()  # Cancel any existing orders to avoid conflicts


def get_atm_call(symbol):
    # 1. Find Stock and Price
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    [ticker] = ib.reqTickers(stock)
    bid_price = ticker.bid
    
    # Fallback: Sometimes bid is NaN (if there are no buyers)
    # If bid is missing, use marketPrice (midpoint) as a backup
    entry_price = bid_price if not pd.isna(bid_price) and bid_price > 0 else ticker.marketPrice()
    print(f"Current Mid: {ticker.marketPrice()} | My Bid Limit: {entry_price}")
    
    # 2. Get Option Chain
    chains = ib.reqSecDefOptParams(
        stock.symbol, '', stock.secType, stock.conId)
    chain = next(c for c in chains if c.exchange == 'SMART')

    # 3. Filter for 30-45 Days Out
    # We pick the 3rd or 4th expiration in the list (usually ~1 month)
    expiry = chain.expirations[3]

    # 4. Find the Strike closest to current price
    strike = min(chain.strikes, key=lambda x: abs(x - ticker.marketPrice()))

    contract = Option(symbol, expiry, strike, 'C', 'SMART')
    ib.qualifyContracts(contract)
    return contract


def run_option_strategy():
    # We still use the STOCK data to generate the signal (9/21 Cross)
    stock = Stock('SPY', 'SMART', 'USD')
    ib.qualifyContracts(stock)
    bars = ib.reqHistoricalData(stock, '', '2 D', '1 min', 'MIDPOINT', False)
    df = util.df(bars)

    df['ma9'] = df['close'].rolling(window=9).mean()
    df['ma21'] = df['close'].rolling(window=21).mean()

    if df['ma9'].iloc[-1] > df['ma21'].iloc[-1] and df['ma9'].iloc[-2] <= df['ma21'].iloc[-2]:
        print(">>> 9/21 Signal! Finding the best Option...")

        call_contract = get_atm_call('SPY')
        print(f"Buying Call: {call_contract.localSymbol}")

        # Get the Option price to set the bracket
        [opt_ticker] = ib.reqTickers(call_contract)
        opt_price = opt_ticker.marketPrice()

        # CREATE THE BRACKET
        # Note: We set Profit Target at +20% and Stop at -10%
        bracket = ib.bracketOrder(
            'BUY', 1,
            limitPrice=opt_price,
            takeProfitPrice=opt_price * 1.20,
            stopLossPrice=opt_price * 0.90
        )

        # CRITICAL: Apply OutsideRth to ALL THREE orders
        for o in bracket:
            o.outsideRth = True
            ib.placeOrder(call_contract, o)

        print("Option Trade Placed with full protection.")


# Loop it
while True:
    run_option_strategy()
    ib.sleep(30)  # Check every 30 seconds
