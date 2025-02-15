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
# Load local environment variables (for local development)
load_dotenv()

def get_api_credentials():
    api_key = st.secrets.get("api", {}).get("api_key", "")
    api_secret = st.secrets.get("api", {}).get("api_secret", "")
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
    with open("config.ini", "w") as configfile:
        config.write(configfile)


def get_public_ip():
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        if response.status_code == 200:
            ip = response.json().get("ip")
            logging.info(f"🔍 Your Public IP: {ip}")
            return ip
    except Exception as e:
        logging.error(f"Failed to get public IP: {e}")
    return None

# Call it before running the bot
public_ip = get_public_ip()
logging.info(f"Public IP for Streamlit Server: {public_ip}")
# Initialize persistent session state variables if not already set
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

st.title("Trading Bot Configuration")

# --- User Inputs ---
test_mode = st.checkbox("Test Mode")
base_price = st.number_input("Base Price", value=1500.0)
manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
interval = st.number_input("Interval (seconds)", min_value=1, value=60)
mode = st.selectbox("Mode", ["long", "short"])
symbol = st.text_input("Symbol", value="BTCUSDT")

# --- Start Bot Button ---
if st.button("Run Trading Bot"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Running `new_trading_bot.py`...")
    # Terminate any existing bot process
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
    # Start the trading bot process (stderr is merged into stdout)
    st.session_state.bot_process = subprocess.Popen(
        [sys.executable, "new_trading_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    # Background thread to read log lines and add them to log_queue
    def read_logs(process, log_queue):
        for line in iter(process.stdout.readline, ''):
            log_queue.put(line)
        process.stdout.close()
    thread = threading.Thread(
        target=read_logs, args=(st.session_state.bot_process, st.session_state.log_queue)
    )
    thread.daemon = True
    thread.start()

# --- Stop Bot Button ---
if st.button("Stop Trading Bot"):
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("Trading bot stopped.")
    else:
        st.warning("No active trading bot to stop.")

st.subheader("Trading Bot Live Logs")

# Drain any new logs from the log queue into log_lines
while not st.session_state.log_queue.empty():
    st.session_state.log_lines.append(st.session_state.log_queue.get())

# Show only the last 20 log lines
last_20_logs = "".join(st.session_state.log_lines[-20:])
st.text(last_20_logs)

# --- Manual Refresh ---
# Clicking this button causes the script to re-run, updating the log display.
if st.button("Refresh Logs"):
    st.write("Logs refreshed!")
