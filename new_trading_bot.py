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
import logging
import json

# Configure logging for structured output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

import datetime
import logging
import json

def log_trade(action, qty, price, success=True, error=None):
    """Log structured trade details in JSON format for Streamlit."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # ✅ Use datetime instead of Formatter
    log_entry = {
        "timestamp": timestamp,
        "action": action,
        "quantity": qty,
        "price": price,
        "status": "SUCCESS" if success else "FAILED",
        "error": error
    }
    # Print structured log for Streamlit output
    print(json.dumps(log_entry))
    # Log detailed info using logging
    logging.info(f"{action.capitalize()} Order: qty={qty}, price={price}, status={'SUCCESS' if success else 'FAILED'}")
    
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
        log_trade(action, 0, price, success=False, error="Failed to retrieve symbol info")
        return

    qty = total_trade_value / price
    qty = adjust_qty(qty, symbol_info['qty_step'], symbol_info['precision'])

    if qty < symbol_info['min_qty']:
        log_trade(action, qty, price, success=False, error=f"Quantity below minimum: {symbol_info['min_qty']}")
        return

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
        if response and response.get('retCode') == 0:
            log_trade(action, qty, price, success=True)
        else:
            error_msg = response.get('retMsg', 'Unknown Error')
            log_trade(action, qty, price, success=False, error=error_msg)

    except Exception as e:
        log_trade(action, qty, price, success=False, error=str(e))

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
    total_holdings = 0  # Track total accumulated coins

    logging.info("Trading bot initialized. Monitoring price movements...")

    try:
        while True:
            current_price = get_current_price()
            log_trade("price_check", 0, current_price, success=True)

            if last_trade_price is None:
                trade_amount = trade_amounts[step_index]
                execute_trade('buy' if MODE == 'long' else 'sell', trade_amount, current_price)
                last_trade_price = current_price
                total_holdings = trade_amount / current_price

            elif MODE == 'long':
                if current_price <= last_trade_price * (1 - MANUAL_PERCENTAGE):
                    step_index = min(step_index + 1, len(trade_amounts) - 1)
                    trade_amount = trade_amounts[step_index]
                    execute_trade('buy', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings += trade_amount / current_price

                elif current_price >= last_trade_price * (1 + MANUAL_PERCENTAGE):
                    execute_trade('sell', total_holdings * current_price, current_price)
                    total_holdings = 0
                    step_index = 0

            elif MODE == 'short':
                if current_price >= last_trade_price * (1 + MANUAL_PERCENTAGE):
                    step_index = min(step_index + 1, len(trade_amounts) - 1)
                    trade_amount = trade_amounts[step_index]
                    execute_trade('sell', trade_amount, current_price)
                    last_trade_price = current_price
                    total_holdings += trade_amount / current_price

                elif current_price <= last_trade_price * (1 - MANUAL_PERCENTAGE):
                    execute_trade('buy', total_holdings * current_price, current_price)
                    total_holdings = 0
                    step_index = 0

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Trading bot stopped by user.")

if __name__ == "__main__":
    trading_logic()
