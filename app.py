# Installation Instructions:
# Run these commands to install required libraries:
# pip install streamlit configparser python-dotenv

import streamlit as st
from configparser import ConfigParser
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

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

# Streamlit UI for local testing
st.title("Trading Bot Configuration (Localhost)")

test_mode = st.checkbox("Test Mode")
base_price = st.number_input("Base Price", value=1500.0)
manual_percentage = st.number_input("Manual Percentage (%)", value=2.0)
interval = st.number_input("Interval (seconds)", min_value=1, value=60)
mode = st.selectbox("Mode", ["long", "short"])
symbol = st.text_input("Symbol", value="BTCUSDT")

if st.button("Run Bot Locally"):
    save_config(test_mode, base_price, manual_percentage, interval, mode, symbol)
    st.success("Configuration saved. Run the bot locally using `python trading_bot.py`.")
    st.write("Use `streamlit run app.py` to test the Streamlit app on localhost.")
