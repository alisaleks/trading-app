import streamlit as st
from configparser import ConfigParser
from dotenv import load_dotenv
import os
import subprocess
import sys
import json

# Load environment variables
load_dotenv()

def save_config(test_mode, base_price, manual_percentage, interval, mode, symbol):
    """Save configuration settings to config.ini"""
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

# Button to Start Trading Bot
if st.button("Run Trading Bot"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Running `new_trading_bot.py`...")

    # Run the trading bot and capture output
    result = subprocess.run(
        [sys.executable, "new_trading_bot.py"],
        capture_output=True,
        text=True
    )

    # Parse JSON-style log output from trading bot
    logs = []
    for line in result.stdout.splitlines():
        try:
            log_entry = json.loads(line)
            logs.append(log_entry)
        except json.JSONDecodeError:
            logs.append({"timestamp": "-", "message": line})

    # Display results in a structured table
    if logs:
        st.subheader("Trading Bot Results")
        log_df = [
            {
                "Timestamp": log.get("timestamp", "-"),
                "Action": log.get("action", "-"),
                "Quantity": log.get("quantity", "-"),
                "Price": log.get("price", "-"),
                "Status": log.get("status", "-"),
                "Error": log.get("error", "-")
            }
            for log in logs
        ]
        st.dataframe(log_df, use_container_width=True)

    # Display raw output (if needed)
    st.subheader("Raw Trading Bot Logs")
    st.text_area("Trading Bot Output", result.stdout)

    # Show errors if any
    if result.stderr:
        st.error(f"Error: {result.stderr}")