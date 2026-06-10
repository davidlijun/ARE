from datetime import datetime, time
from zoneinfo import ZoneInfo
import logging

from ib_insync import IB, Stock, Option, MarketOrder

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

IB_HOST = '127.0.0.1'
IB_PORT = 4002  # Paper trading default
CLIENT_ID = 3
ET_ZONE = ZoneInfo('America/New_York')

ib = IB()


def connect_ib(host=IB_HOST, port=IB_PORT, client_id=CLIENT_ID, cancel_existing=False):
    if not ib.isConnected():
        logger.info('Connecting to IB at %s:%s with clientId=%s', host, port, client_id)
        ib.connect(host, port, clientId=client_id)

    if cancel_existing:
        logger.warning('Canceling any existing open orders before the trade.')
        ib.reqGlobalCancel()

    return ib


def is_market_open(now=None):
    now = now or datetime.now(ET_ZONE)
    if now.weekday() >= 5:
        return False
    return time(9, 30) <= now.time() < time(16, 0)


def get_atm_option(symbol='QQQ', expiry=None, right='C'):
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    ticker = ib.reqTickers(stock)[0]
    if ticker.bid is None or ticker.ask is None:
        raise RuntimeError(f'Underlying market data unavailable for {symbol}')

    atm_strike = round(ticker.marketPrice())
    expiry = expiry or datetime.now(ET_ZONE).strftime('%Y%m%d')

    contract = Option(symbol, expiry, atm_strike, right, 'SMART', 'USD')
    ib.qualifyContracts(contract)
    return contract


def trade_with_time_exit(quantity=1, tp_multiplier=1.5, sl_multiplier=0.6, exit_hour=14, cancel_existing=False):
    connect_ib(cancel_existing=cancel_existing)

    try:
        if not is_market_open():
            raise RuntimeError('Market is not open. Run this during US market hours.')

        contract = get_atm_option('QQQ')
        option_ticker = ib.reqTickers(contract)[0]
        ib.sleep(1)

        if option_ticker.bid is None or option_ticker.ask is None:
            raise RuntimeError('Option bid/ask data unavailable for %s' % contract.symbol)

        entry_price = (option_ticker.ask + option_ticker.bid) / 2
        tp_price = round(entry_price * tp_multiplier, 2)
        sl_price = round(entry_price * sl_multiplier, 2)

        logger.info(
            'Entry price for %s %s %s %s is %.2f; TP=%.2f, SL=%.2f',
            contract.symbol,
            contract.lastTradeDateOrContractMonth,
            contract.strike,
            contract.right,
            entry_price,
            tp_price,
            sl_price,
        )

        bracket = ib.bracketOrder(
            'BUY', quantity,
            limitPrice=entry_price,
            takeProfitPrice=tp_price,
            stopLossPrice=sl_price,
        )

        for order in bracket:
            ib.placeOrder(contract, order)

        logger.info('Bracket order placed. Monitoring for TP, SL, or exit at %02d:00 ET.', exit_hour)

        while True:
            ib.waitOnUpdate(timeout=10)
            now_et = datetime.now(ET_ZONE)
            positions = [p for p in ib.positions() if p.contract.conId == contract.conId]
            position = positions[0].position if positions else 0

            if position == 0 and now_et.hour < exit_hour:
                logger.info('Position closed before exit hour (TP or SL hit).')
                break

            if now_et.hour >= exit_hour:
                if position == 0:
                    logger.info('No filled position by exit hour. Canceling open orders if any.')
                else:
                    logger.info('Exit hour reached with open position %s. Closing position now.', position)

                for open_trade in ib.openTrades():
                    if open_trade.contract.conId == contract.conId:
                        ib.cancelOrder(open_trade.order)

                if position != 0:
                    close_order = MarketOrder('SELL', position)
                    ib.placeOrder(contract, close_order)
                    ib.waitOnUpdate(timeout=10)

                break

        logger.info('Strategy finished for the day.')

    finally:
        if ib.isConnected():
            ib.disconnect()


if __name__ == '__main__':
    trade_with_time_exit(quantity=1)
