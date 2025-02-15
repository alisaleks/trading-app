import time
import math
import logging
from configparser import ConfigParser
from pybit.unified_trading import HTTP

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
config = ConfigParser()
config.read('config.ini')

API_KEY = config.get('API', 'api_key')
API_SECRET = config.get('API', 'api_secret')
TEST_MODE = config.getboolean('Settings', 'test_mode')
MANUAL_PERCENTAGE = float(config.get('Settings', 'manual_percentage')) / 100  # e.g., 0.02 for 2%
INTERVAL = int(config.get('Settings', 'interval'))
SYMBOL = config.get('Settings', 'symbol')
MODE = config.get('Settings', 'mode')
BASE_PRICE = float(config.get('Settings', 'base_price'))  # e.g., 1500 USDT

STEP_INCREMENTS = [
    1, 1, 1, 1,
    1.3333, 1.3333, 1.3333, 1.3333,
    1.6666, 1.6666, 1.6666, 1.6666,
    2, 2, 2, 2
]

# Bybit session
session = HTTP(
    testnet=TEST_MODE,
    api_key=API_KEY,
    api_secret=API_SECRET
)

def retry_api_call(func, retries=3, *args, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"API call failed on attempt {attempt + 1}/{retries}: {e}")
            time.sleep(2 ** attempt)
    logging.error("Max retries reached. API call failed.")
    return None

def get_symbol_info(symbol):
    response = retry_api_call(session.get_instruments_info, category="linear")
    if response and 'result' in response:
        for item in response['result']['list']:
            if item['symbol'] == symbol:
                qty_step = float(item['lotSizeFilter']['qtyStep'])
                precision = int(round(-math.log10(qty_step)))
                return {
                    'min_qty': float(item['lotSizeFilter']['minOrderQty']),
                    'qty_step': qty_step,
                    'precision': precision,
                }
    logging.error(f"Failed to retrieve symbol info for {symbol}.")
    return None

def adjust_qty(qty, step_size, precision):
    adjusted_qty = math.floor(qty / step_size) * step_size
    return round(adjusted_qty, precision)

def execute_trade(action, total_trade_value, price):
    symbol_info = get_symbol_info(SYMBOL)
    if not symbol_info:
        logging.error("Failed to retrieve symbol information.")
        return

    qty = total_trade_value / price
    qty = adjust_qty(qty, symbol_info['qty_step'], symbol_info['precision'])

    if qty < symbol_info['min_qty']:
        logging.error(f"Quantity {qty} is below the minimum allowed {symbol_info['min_qty']}.")
        return

    logging.info(f"Placing {action.capitalize()} Order: qty={qty}, price={price}")
    try:
        response = retry_api_call(
            session.place_order,
            symbol=SYMBOL,
            category="linear",
            side="Buy" if action == 'buy' else "Sell",
            orderType="Limit",
            qty=str(qty),
            price=str(round(price, 1)),
            timeInForce="GTC"
        )
        logging.info(f"Trade Response: {response}")
    except Exception as e:
        logging.error(f"Failed to execute trade: {e}")

def get_current_price():
    ticker = retry_api_call(session.get_tickers, category="linear", symbol=SYMBOL)
    if ticker and 'result' in ticker and 'list' in ticker['result'] and len(ticker['result']['list']) > 0:
        return float(ticker['result']['list'][0]['lastPrice'])
    logging.error("Failed to fetch current price. Falling back to BASE_PRICE.")
    return BASE_PRICE

def trading_logic():
    trade_amounts = [BASE_PRICE * multiplier for multiplier in STEP_INCREMENTS]
    step_index = 0
    last_trade_price = None
    last_action = None
    total_holdings = 0  # Track total accumulated coins

    logging.info("Trading bot initialized. Monitoring price movements...")

    try:
        while True:
            current_price = get_current_price()
            logging.info(f"Current Market Price: {current_price}")

            if last_trade_price is None:
                trade_amount = trade_amounts[step_index]
                execute_trade('buy' if MODE == 'long' else 'sell', trade_amount, current_price)
                last_trade_price = current_price
                last_action = 'buy' if MODE == 'long' else 'sell'
                total_holdings = trade_amount / current_price  # Track purchased qty
            else:
                if MODE == 'long' and current_price <= last_trade_price * (1 - MANUAL_PERCENTAGE):
                    step_index = min(step_index + 1, len(trade_amounts) - 1)
                    trade_amount = trade_amounts[step_index]
                    execute_trade('buy', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings += trade_amount / current_price  # Accumulate total coins

                elif MODE == 'long' and current_price >= last_trade_price * (1 + MANUAL_PERCENTAGE):
                    execute_trade('sell', total_holdings * current_price, current_price)  # Sell all holdings
                    total_holdings = 0  # Reset holdings

                    # **Buy immediately after selling at the same price with new step amount**
                    trade_amount = trade_amounts[step_index]  # Use the current step's amount
                    execute_trade('buy', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings = trade_amount / current_price  # Reset holdings

                    step_index = 0  # Reset to first step

                elif MODE == 'short' and current_price >= last_trade_price * (1 + MANUAL_PERCENTAGE):
                    step_index = min(step_index + 1, len(trade_amounts) - 1)
                    trade_amount = trade_amounts[step_index]
                    execute_trade('sell', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings += trade_amount / current_price  # Accumulate total coins

                elif MODE == 'short' and current_price <= last_trade_price * (1 - MANUAL_PERCENTAGE):
                    execute_trade('buy', total_holdings * current_price, current_price)  # Buy all back
                    total_holdings = 0  # Reset holdings

                    # **Buy immediately after covering at the same price with new step amount**
                    trade_amount = trade_amounts[step_index]  # Use the current step's amount
                    execute_trade('sell', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings = trade_amount / current_price  # Reset holdings

                    step_index = 0  # Reset to first step

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Trading bot stopped by user.")

if __name__ == "__main__":
    trading_logic()
