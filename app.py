import streamlit as st
from configparser import ConfigParser
from dotenv import load_dotenv
import os
import subprocess
import sys
import threading
import queue
import time

# Load environment variables for local development
load_dotenv()

def get_api_credentials():
    # Try local environment variables first; if not found, use Streamlit secrets.
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
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

# Initialize session state variables if not already set
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []
if "last_20_logs" not in st.session_state:
    st.session_state.last_20_logs = ""
if "log_updater_started" not in st.session_state:
    st.session_state.log_updater_started = False

st.title("Trading Bot Configuration")

# UI Inputs
test_mode = st.checkbox("Test Mode")
base_price = st.number_input("Base Price", value=1500.0)
manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
interval = st.number_input("Interval (seconds)", min_value=1, value=60)
mode = st.selectbox("Mode", ["long", "short"])
symbol = st.text_input("Symbol", value="BTCUSDT")

# Button to start the trading bot
if st.button("Run Trading Bot"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Running `new_trading_bot.py`...")
    
    # Terminate any existing bot process
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
    
    # Start the trading bot process (combine stderr into stdout)
    st.session_state.bot_process = subprocess.Popen(
        [sys.executable, "new_trading_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Background thread to read logs from the process and put them in a queue
    def read_logs(process, log_queue):
        for line in iter(process.stdout.readline, ''):
            log_queue.put(line)
        process.stdout.close()
    
    read_thread = threading.Thread(
        target=read_logs, args=(st.session_state.bot_process, st.session_state.log_queue)
    )
    read_thread.daemon = True
    read_thread.start()

# Button to stop the trading bot
if st.button("Stop Trading Bot"):
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("Trading bot stopped.")
    else:
        st.warning("No active trading bot to stop.")

st.subheader("Trading Bot Live Logs")

# Function to update the last 20 log lines in session state
def update_logs():
    while True:
        # Exit if the bot process is no longer running
        if st.session_state.bot_process is None:
            break
        # Drain the log queue into log_lines
        while not st.session_state.log_queue.empty():
            st.session_state.log_lines.append(st.session_state.log_queue.get())
        # Keep only the last 20 lines
        st.session_state.last_20_logs = "".join(st.session_state.log_lines[-20:])
        time.sleep(2)

# Start a background thread to update the log display if not already started
if not st.session_state.log_updater_started and st.session_state.bot_process is not None:
    st.session_state.log_updater_started = True
    log_update_thread = threading.Thread(target=update_logs)
    log_update_thread.daemon = True
    log_update_thread.start()

# Display the last 20 log lines
st.text(st.session_state.last_20_logs)