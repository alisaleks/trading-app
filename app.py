import streamlit as st
import time
import subprocess
import sys
import threading
import queue
import os
from configparser import ConfigParser
from dotenv import load_dotenv
import requests
import logging
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ Proxy Configuration
PROXY_URL = "http://15.236.203.245:3128"  # Example: Germany Proxy
PROXY_CONFIG = {"http": PROXY_URL, "https": PROXY_URL}

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_api_credentials():
    api_key = st.secrets.get("api", {}).get("api_key", os.getenv("API_KEY", ""))
    api_secret = st.secrets.get("api", {}).get("api_secret", os.getenv("API_SECRET", ""))
    if not api_key or not api_secret:
        st.error("🚨 API credentials not found. Add them to Streamlit Secrets.")
    return api_key, api_secret

def save_config(test_mode, base_price, manual_percentage, interval, mode, symbol):
    api_key, api_secret = get_api_credentials()
    config = ConfigParser()
    config['Settings'] = {
        'test_mode': str(test_mode),
        'base_price': str(base_price),
        'manual_percentage': str(manual_percentage),
        'interval': str(interval),
        'mode': str(mode),
        'symbol': str(symbol)
    }
    config['API'] = {
        'api_key': api_key,
        'api_secret': api_secret
    }
    config['Proxy'] = {
        'proxy_url': PROXY_URL
    }
    with open("config.ini", "w") as configfile:
        config.write(configfile)
    st.success("✅ Configuration saved to `config.ini`.")

def get_public_ip():
    try:
        response = requests.get(
            "https://checkip.amazonaws.com",
            proxies=PROXY_CONFIG,
            timeout=25,
            verify=False  # Disable SSL verification
        )
        if response.status_code == 200:
            ip = response.text.strip()
            st.info(f"🔍 Your Public IP via Proxy: `{ip}`")
            return ip
    except Exception as e:
        st.error(f"🚨 Failed to get public IP via Proxy: {e}")
    return None

def check_bybit_connection():
    try:
        response = requests.get(
            "https://api-testnet.bybit.com/v5/market/tickers",
            params={"category": "linear", "symbol": "BTCUSDT"},
            proxies=PROXY_CONFIG,
            timeout=25,
            verify=False  # Disable SSL verification
        )
        status_code = response.status_code
        if status_code == 200:
            st.success("✅ Bybit Testnet is accessible via Proxy.")
            return True
        elif status_code == 403:
            st.error("🚫 Bybit blocked your Proxy IP. Try another Proxy.")
        elif status_code == 429:
            st.error("🚨 Bybit Rate Limit hit. Try again later.")
        else:
            st.error(f"🚫 Bybit Testnet Error: {status_code}")
        return False
    except Exception as e:
        st.error(f"🚨 Bybit Testnet connection via proxy failed: {e}")
        return False

st.title("🚀 Trading Bot Dashboard")
public_ip = get_public_ip()
bybit_status = check_bybit_connection()

if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

with st.sidebar:
    st.header("⚙️ Bot Configuration")
    test_mode = st.checkbox("Test Mode (Bybit Testnet)", value=True)
    base_price = st.number_input("Base Price", value=1500.0)
    manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
    interval = st.number_input("Interval (seconds)", min_value=1, value=60)
    mode = st.selectbox("Mode", ["long", "short"])
    symbol = st.text_input("Symbol", value="BTCUSDT")

if st.button("💾 Save Configuration"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)

def read_logs(process, log_queue):
    for line in iter(process.stdout.readline, ''):
        log_queue.put(line)
    process.stdout.close()

def start_bot():
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("🚀 Starting `new_trading_bot.py`...")

    # Terminate existing process if active
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None

    st.session_state.bot_process = subprocess.Popen(
        [sys.executable, "new_trading_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Start a thread to capture logs in real-time
    thread = threading.Thread(
        target=read_logs, args=(st.session_state.bot_process, st.session_state.log_queue)
    )
    thread.daemon = True
    thread.start()

def stop_bot():
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("🛑 Trading bot stopped.")
    else:
        st.warning("⚠️ No active trading bot to stop.")

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Run Trading Bot", type="primary"):
        if bybit_status:
            start_bot()
        else:
            st.error("🚫 Cannot start bot: Bybit Testnet is not accessible.")
with col2:
    if st.button("🛑 Stop Trading Bot", type="secondary"):
        stop_bot()

st.subheader("📈 Trading Bot Live Logs")
while not st.session_state.log_queue.empty():
    st.session_state.log_lines.append(st.session_state.log_queue.get())

st.text_area("Logs", "\n".join(st.session_state.log_lines[-30:]), height=300)

if st.button("🔄 Refresh Logs"):
    st.rerun()
