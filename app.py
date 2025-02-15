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
import json

# 🛡 Load local environment variables (for local development)
load_dotenv()

# ✅ Get API Credentials (from Streamlit secrets or .env)
def get_api_credentials():
    api_key = st.secrets.get("api", {}).get("api_key", "")
    api_secret = st.secrets.get("api", {}).get("api_secret", "")
    if not api_key or not api_secret:
        st.error("🚨 API credentials not found. Add them to Streamlit Secrets.")
    return api_key, api_secret

# ✅ Save Configuration to `config.ini`
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
    with open("config.ini", "w") as configfile:
        config.write(configfile)
    st.success("✅ Configuration saved to `config.ini`.")

# ✅ Get Public IP to diagnose region blocks
def get_public_ip():
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        if response.status_code == 200:
            ip = response.json().get("ip")
            st.info(f"🔍 Public IP for Streamlit Server: `{ip}`")
            return ip
    except Exception as e:
        st.error(f"Failed to get public IP: {e}")
    return None

# ✅ Check Bybit Testnet API status (useful for diagnosing rate limits or region blocks)
def check_bybit_connection():
    url = "https://api-testnet.bybit.com/v5/market/tickers"
    params = {"category": "linear", "symbol": "BTCUSDT"}
    try:
        response = requests.get(url, params=params, timeout=5)
        status_code = response.status_code
        response_text = response.text

        if status_code == 200:
            st.success("✅ Bybit Testnet is accessible.")
            return True
        elif status_code == 403:
            st.error("🚫 Bybit blocked your IP (Region Block or Missing API Permissions).")
        elif status_code == 429:
            st.error("🚨 Bybit Rate Limit hit. Try again later or use backoff logic.")
        else:
            st.error(f"🚫 Bybit Testnet Error: {status_code} - {response_text}")
        return False
    except Exception as e:
        st.error(f"🚨 Bybit Testnet connection failed: {e}")
        return False

# ✅ Run Public IP and API Status Check Before Running the Bot
public_ip = get_public_ip()
bybit_status = check_bybit_connection()

# ✅ Initialize persistent session state
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

# 📊 Streamlit Interface
st.title("🚀 Trading Bot Dashboard")

# --- 🛠 User Inputs ---
with st.sidebar:
    st.header("⚙️ Bot Configuration")
    test_mode = st.checkbox("Test Mode (Bybit Testnet)", value=True)
    base_price = st.number_input("Base Price", value=1500.0)
    manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
    interval = st.number_input("Interval (seconds)", min_value=1, value=60)
    mode = st.selectbox("Mode", ["long", "short"])
    symbol = st.text_input("Symbol", value="BTCUSDT")

# --- 💾 Save Configuration Button ---
if st.button("💾 Save Configuration"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)

# ✅ Function to read logs from bot process and store in queue
def read_logs(process, log_queue):
    for line in iter(process.stdout.readline, ''):
        log_queue.put(line)
    process.stdout.close()

# ✅ Start Bot Process
def start_bot():
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("🚀 Starting `new_trading_bot.py`...")

    # Terminate any existing process
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None

    # Start the bot as a subprocess
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

# ✅ Stop Bot Process
def stop_bot():
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("🛑 Trading bot stopped.")
    else:
        st.warning("⚠️ No active bot process to stop.")

# --- 🚀 Start/Stop Buttons ---
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

# ✅ Show Live Logs from Bot Process
st.subheader("📈 Trading Bot Live Logs")
while not st.session_state.log_queue.empty():
    st.session_state.log_lines.append(st.session_state.log_queue.get())

# Show only last 30 log lines
st.text_area("Logs", "\n".join(st.session_state.log_lines[-30:]), height=300)

# --- 🔄 Manual Refresh Logs ---
if st.button("🔄 Refresh Logs"):
    st.experimental_rerun()

# ✅ Automatic Log Refresh every 3 seconds
st.experimental_set_query_params(refresh=True)
time.sleep(3)
st.experimental_rerun()
