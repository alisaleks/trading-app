import streamlit as st
from configparser import ConfigParser
from dotenv import load_dotenv
import os
import subprocess
import sys
import json
import time

# Load environment variables
load_dotenv()

# Save configuration to config.ini
def save_config(test_mode, base_price, manual_percentage, interval, mode, symbol):
    config = ConfigParser()
    config['API'] = {
        'api_key': '[Stored securely in .env]',
        'api_secret': '[Stored securely in .env]'
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

# Streamlit UI
st.title("Trading Bot Configuration")

# UI Inputs
test_mode = st.checkbox("Test Mode")
base_price = st.number_input("Base Price", value=1500.0)
manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
interval = st.number_input("Interval (seconds)", min_value=1, value=60)
mode = st.selectbox("Mode", ["long", "short"])
symbol = st.text_input("Symbol", value="BTCUSDT")

# Store bot process globally
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None

# Button to Start Trading Bot
if st.button("Run Trading Bot"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Running `new_trading_bot.py`...")

    # Terminate any existing bot process
    if st.session_state.bot_process is not None:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None

    # Run trading bot in the background (non-blocking)
    st.session_state.bot_process = subprocess.Popen(
        [sys.executable, "new_trading_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffering
        universal_newlines=True
    )

# Button to Stop Trading Bot
if st.button("Stop Trading Bot"):
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
        st.success("Trading bot stopped.")
    else:
        st.warning("No active trading bot to stop.")

# Live Log Display
st.subheader("Trading Bot Live Logs")

# Stream logs live
log_area = st.empty()

if st.session_state.bot_process:
    for line in iter(st.session_state.bot_process.stdout.readline, ''):
        log_area.text(line)
        time.sleep(0.1)  # Smooth streaming
else:
    st.info("No active trading bot. Click 'Run Trading Bot' to start.")