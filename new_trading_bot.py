import sys
import time
import os
import math
import logging
import json
import datetime
from configparser import ConfigParser
from pybit.unified_trading import HTTP
import streamlit as st  # ✅ Add this line for Streamlit integration

# ✅ Unbuffered Output for Streamlit (Python 3.7+)
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
PROXY_URL = "http://87.106.90.137:8080"
# ✅ Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ Load API Credentials (Priority: Environment → Streamlit Secrets)
def get_api_credentials():
    api_key = st.secrets.get("api", {}).get("api_key", "")
    api_secret = st.secrets.get("api", {}).get("api_secret", "")
    
    if not api_key or not api_secret:
        raise ValueError("API credentials not found in Streamlit secrets.")
    
    return api_key, api_secret

# ✅ Load general configuration from config.ini
config = ConfigParser()
config.read('config.ini')
api_key, api_secret = get_api_credentials()
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
    api_key=api_key,
    api_secret=api_secret,
    request_timeout=10,
    proxies={"http": PROXY_URL, "https": PROXY_URL}
)

def log_trade(action, qty, price, success=True, error=None):
    """Log structured trade details for Streamlit."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        "timestamp": timestamp,
        "action": action,
        "quantity": qty,
        "price": price,
        "status": "SUCCESS" if success else "FAILED",
        "error": error
    }
    # Print JSON log for Streamlit
    print(json.dumps(log_entry), flush=True)
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
    try:
        response = retry_api_call(session.get_tickers, category="linear", symbol=SYMBOL)
        if response:
            headers = response.get("headers", {})
            remaining_limit = headers.get("X-Bapi-Limit-Status", "unknown")

            if remaining_limit != "unknown":
                logging.info(f"Remaining API limit: {remaining_limit}")

                # Throttle if remaining requests are low
                if int(remaining_limit) < 10:
                    logging.warning("Approaching rate limit. Backing off for 10 seconds.")
                    time.sleep(10)

            ticker_list = response.get("result", {}).get("list", [])
            if ticker_list:
                return float(ticker_list[0]["lastPrice"])
    except Exception as e:
        logging.error(f"Error fetching current price: {e}")
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
