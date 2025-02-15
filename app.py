import streamlit as st
from configparser import ConfigParser
from dotenv import load_dotenv
import os
import subprocess
import sys
import threading
import queue
import time
from streamlit_autorefresh import st_autorefresh

# Load environment variables for local development
load_dotenv()

def get_api_credentials():
    # Try to get from environment first (for local development)
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    # If not found, try Streamlit secrets (for cloud deployment)
    if not api_key or not api_secret:
        api_key = st.secrets.get("API", {}).get("api_key", "")
        api_secret = st.secrets.get("API", {}).get("api_secret", "")
    return api_key, api_secret

def save_config(test_mode, base_price, manual_percentage, interval, mode, symbol):
    api_key, api_secret = get_api_credentials()
    config = ConfigParser()
    config['API'] = {
        'api_key': api_key,
        'api_secret': api_secret
    }
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

# Initialize session state variables
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

# Streamlit UI
st.title("Trading Bot Configuration")

# UI Inputs
test_mode = st.checkbox("Test Mode")
base_price = st.number_input("Base Price", value=1500.0)
manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
interval = st.number_input("Interval (seconds)", min_value=1, value=60)
mode = st.selectbox("Mode", ["long", "short"])
symbol = st.text_input("Symbol", value="BTCUSDT")

# Button to Start Trading Bot
if st.button("Run Trading Bot"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Running `new_trading_bot.py`...")
    
    # Terminate any existing bot process
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
    
    # Start the trading bot process with stderr combined into stdout
    st.session_state.bot_process = subprocess.Popen(
        [sys.executable, "new_trading_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Start a background thread to read logs from the process
    def read_logs(process, log_queue):
        for line in iter(process.stdout.readline, ''):
            log_queue.put(line)
        process.stdout.close()
    
    thread = threading.Thread(target=read_logs, args=(st.session_state.bot_process, st.session_state.log_queue))
    thread.daemon = True
    thread.start()

# Button to Stop Trading Bot
if st.button("Stop Trading Bot"):
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("Trading bot stopped.")
    else:
        st.warning("No active trading bot to stop.")

st.subheader("Trading Bot Live Logs")

# Auto-refresh the page every 2 seconds so new logs are shown
st_autorefresh(interval=2000, key="log_autorefresh")

# Poll the log queue for new log lines
while not st.session_state.log_queue.empty():
    new_line = st.session_state.log_queue.get()
    st.session_state.log_lines.append(new_line)

# Display the accumulated logs
st.text("".join(st.session_state.log_lines))