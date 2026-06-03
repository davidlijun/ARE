from ib_insync import *
import pandas as pd

# 1. CONNECT
# Port 4002 = Live Trading | Port 7497 = Paper Trading
ib = IB()
try:
    ib.connect('127.0.0.1', 4002, clientId=1)
    print("✓ Connected to IB TWS successfully")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print("Make sure TWS is running on this machine with API enabled")
    exit(1)

ib.reqGlobalCancel()  # Cancel any existing orders to avoid conflicts

# Position tracking
active_position = False


def get_atm_call(symbol):
    # 1. Find Stock and Price - Now using subscribed market data
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    
    try:
        tickers = ib.reqTickers(stock)
        if not tickers or len(tickers) == 0:
            raise ValueError(f"No ticker data received for {symbol}")
        ticker = tickers[0]
    except Exception as e:
        raise Exception(f"Error getting ticker for {symbol}: {e}")
    
    bid_price = ticker.bid
    print(f"Stock Ticker Data: bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}, marketPrice={ticker.marketPrice()}")
    
    breakpoint()  # Debug: Check ticker data before proceeding
    # Fallback: Sometimes bid is NaN (if there are no buyers)
    # If bid is missing, use marketPrice (midpoint) as a backup
    entry_price = bid_price if not pd.isna(bid_price) and bid_price > 0 else ticker.marketPrice()
    
    print(f"Current Mid: {ticker.marketPrice()} | My Bid Limit: {entry_price}")
    
    # 2. Get Option Chain
    chains = ib.reqSecDefOptParams(
        stock.symbol, '', stock.secType, stock.conId)
    chain = next(c for c in chains if c.exchange == 'SMART')

    # 3. Filter for 0DTE (Today's expiration)
    # We pick the first expiration (index 0) which is same-day
    if len(chain.expirations) == 0:
        raise ValueError("No option expirations available")
    expiry = chain.expirations[0]  # 0DTE - same day expiration
    print(f"Using 0DTE expiry: {expiry}")

    # 4. Find the Strike closest to current price (ATM)
    strike = min(chain.strikes, key=lambda x: abs(x - ticker.marketPrice()))
    print(f"ATM Strike: {strike}")

    contract = Option(symbol, expiry, strike, 'C', 'SMART', 'USD')
    ib.qualifyContracts(contract)
    
    # Validate contract was properly qualified
    if not contract.conId or contract.conId == 0:
        raise ValueError(f"Contract qualification failed for {symbol} {expiry} {strike}C")
    
    return contract


def run_option_strategy():
    global active_position
    
    try:
        # Historical data from IB
        stock = Stock('SPY', 'SMART', 'USD')
        ib.qualifyContracts(stock)
        
        try:
            # Request historical data - wait for completion
            bars = ib.reqHistoricalData(
                stock, 
                endDateTime='', 
                durationStr='1 D',  # Reduced from 2D to ensure data exists
                barSizeSetting='1 min', 
                whatToShow='MIDPOINT',  # Changed to MIDPOINT (more widely available)
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )
            
            # Block until data arrives or timeout
            ib.sleep(2)  # Give it time to receive data
            
            if not bars or len(bars) == 0:
                print(f"⚠ No historical data received. Market may be closed. Retrying...")
                ib.sleep(10)
                return
                
            df = util.df(bars)
            print(f"✓ Retrieved {len(df)} bars of historical data")
            
        except Exception as e:
            print(f"✗ Error fetching historical data: {e}")
            return

        df['ma9'] = df['close'].rolling(window=9).mean()
        df['ma21'] = df['close'].rolling(window=21).mean()
        
        # Print current MAs for debugging
        print(f"MA9: {df['ma9'].iloc[-1]:.2f}, MA21: {df['ma21'].iloc[-1]:.2f}")

        # Check for 9/21 crossover signal: MA9 > MA21 AND was previously MA9 <= MA21
        signal = (df['ma9'].iloc[-1] > df['ma21'].iloc[-1] and 
                  df['ma9'].iloc[-2] <= df['ma21'].iloc[-2])
        
        if True:
            # Check if we already have an active position
            if active_position:
                print(">>> Position already active. Skipping signal.")
                return
            
            print(">>> 9/21 Signal! Finding the best Option...")

            try:
                call_contract = get_atm_call('SPY')
                print(f"!!!!!!!!!!Buying Call: {call_contract.localSymbol}")

                # Get the Option price using subscribed market data
                try:
                    opt_tickers = ib.reqTickers(call_contract)
                    if not opt_tickers or len(opt_tickers) == 0:
                        raise ValueError("No ticker data received for option contract")
                    opt_ticker = opt_tickers[0]
                    
                    # Debug: print available data
                    print(f"Option Ticker Data: bid={opt_ticker.bid}, ask={opt_ticker.ask}, last={opt_ticker.last}, marketPrice={opt_ticker.marketPrice()}")
                    
                except Exception as e:
                    print(f"ERROR getting option ticker: {e}")
                    return
                
                # Use ask price (safest for entry), fallback to bid, then marketPrice
                if not pd.isna(opt_ticker.ask) and opt_ticker.ask > 0:
                    opt_price = opt_ticker.ask
                elif not pd.isna(opt_ticker.bid) and opt_ticker.bid > 0:
                    opt_price = opt_ticker.bid
                else:
                    mid = opt_ticker.marketPrice()
                    if pd.isna(mid) or mid <= 0:
                        print("WARNING: No valid option price found - using minimum tick")
                        opt_price = 0.01
                    else:
                        opt_price = mid
                
                print(f"Option Mid Price: {opt_ticker.marketPrice()} | My Entry Limit: {opt_price}")
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
                    # o.outsideRth = True  # Allow orders outside regular trading hours
                    ib.placeOrder(call_contract, o)

                active_position = True
                print("Option Trade Placed with full protection.")
            except Exception as e:
                print(f"ERROR placing order: {e}")
    
    except Exception as e:
        print(f"ERROR in run_option_strategy: {e}")


# Loop it
while True:
    try:
        run_option_strategy()
        ib.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("Script stopped by user.")
        break
    except Exception as e:
        print(f"FATAL ERROR in main loop: {e}")
        ib.sleep(30)  # Wait before retrying
