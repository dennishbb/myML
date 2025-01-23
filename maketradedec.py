#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
import time
import psycopg2
from datetime import datetime
from alpaca_trade_api.rest import REST, TimeFrame
from dotenv import load_dotenv
import os
from pytz import timezone

# Load environment variables from .env file
load_dotenv('/home/developer/projects/myML/.env')

# Retrieve environment variables
API_KEY = os.getenv('APCA_API_KEY_ID')
SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
BASE_URL = os.getenv('APCA_API_BASE_URL')
DB_CONFIG = {
    "dbname": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "host": os.getenv('DB_HOST'),
    "port": int(os.getenv('DB_PORT', 5432))  # Default to 5432 if DB_PORT is not set
}

# Initialize Alpaca REST client
alpaca = REST(API_KEY, SECRET_KEY, BASE_URL, api_version="v2")

# Function to generate quantum random intervals
def quantum_random_interval(min_time, max_time):
    api_url = "https://qrng.anu.edu.au/API/jsonI.php"
    while True:
        try:
            response = requests.get(api_url, params={"length": 1, "type": "uint8"})
            response.raise_for_status()
            quantum_number = response.json()["data"][0]
            return min_time + (quantum_number % (max_time - min_time + 1))
        except Exception as e:
            print(f"QRNG Error: {e}. Retrying...")
            time.sleep(5)

# Function to fetch market levels
def fetch_market_levels(symbol, timeframe=TimeFrame.Minute, lookback=50):
    max_retries = 5
    retries = 0
    bars = None

    while retries < max_retries:
        try:
            # Check if the market is open
            clock = alpaca.get_clock()
            if not clock.is_open:
                raise ValueError("Market is closed")

            # Fetch historical data
            print(f"Fetching historical data for {symbol} with timeframe {timeframe} and lookback {lookback}")
            bars = alpaca.get_bars(
                symbol,
                timeframe,
                limit=lookback,
                feed="iex"  # Specify the IEX feed
            )

            if not bars or len(bars) == 0:
                raise ValueError("No historical data fetched")

            # Calculate support and resistance
            highs = [bar.h for bar in bars]
            lows = [bar.l for bar in bars]
            support = min(lows)
            resistance = max(highs)
            break
        except Exception as e:
            print(f"Error fetching market levels: {e}. Retrying... ({retries + 1}/{max_retries})")
            retries += 1
            time.sleep(5)

    if retries == max_retries:
        raise ValueError("Failed to fetch historical data after multiple attempts")

    # Fetch the latest price (current price) and timestamp
    last_bar = bars[-1]
    last_price = last_bar.c  # Close price of the most recent bar
    last_timestamp = last_bar.t  # Timestamp of the most recent bar

    return {
        "support": support,
        "resistance": resistance,
        "current_price": last_price,
        "timestamp": last_timestamp
    }

# Function to generate quantum price targets
def quantum_price_target(current_price, range_percentage):
    random_factor = quantum_random_interval(1, 100) / 100
    return current_price + (current_price * range_percentage * random_factor)

# Function to decide trading action based on breakout levels
def trading_decision(symbol, support, resistance, current_price):
    print(f"Analyzing {symbol}...")
    if current_price > resistance:
        print(f"Bullish breakout detected for {symbol}!")
        target_price = quantum_price_target(current_price, range_percentage=0.02)
        stop_loss = current_price * 0.98
        return {
            "action": "BUY",
            "symbol": symbol,
            "entry_price": current_price,
            "target_price": target_price,
            "stop_loss": stop_loss
        }
    elif current_price < support:
        print(f"Bearish breakout detected for {symbol}!")
        target_price = quantum_price_target(current_price, range_percentage=-0.02)
        stop_loss = current_price * 1.02
        return {
            "action": "SELL",
            "symbol": symbol,
            "entry_price": current_price,
            "target_price": target_price,
            "stop_loss": stop_loss
        }
    else:
        print(f"No breakout detected for {symbol}.")
        return None

# Store trade decision in database
def store_trade_decision(trade_decision):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Insert trade into the simulated_trades table
        insert_query = """
        INSERT INTO simulated_trades (
            symbol, direction, entry_price, target_price, stop_loss, executed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        cursor.execute(insert_query, (
            trade_decision["symbol"], trade_decision["action"], trade_decision["entry_price"],
            trade_decision["target_price"], trade_decision["stop_loss"],
            datetime.utcnow()
        ))
        conn.commit()
        print("Trade decision stored successfully.")
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()

# Main routine with integrated trading_decision
if __name__ == "__main__":
    symbols = ["NVDA", "IONQ", "AMD", "MU", "GILD", "INTC", "AMBA"]
    for symbol in symbols:
        try:
            market_levels = fetch_market_levels(symbol, timeframe=TimeFrame.Minute, lookback=50)
            phoenix_time = market_levels["timestamp"].astimezone(timezone('US/Eastern'))
            print(f"\nAnalyzing {symbol}:")
            print(f"Current price: ${market_levels['current_price']:.2f} at {phoenix_time.strftime('%Y-%m-%d %H:%M:%S %Z')} (Eastern Time)")
            print(f"Support Level: ${market_levels['support']:.2f}, Resistance Level: ${market_levels['resistance']:.2f}")

            # Make a trading decision
            decision = trading_decision(
                symbol,
                support=market_levels["support"],
                resistance=market_levels["resistance"],
                current_price=market_levels["current_price"]
            )
            
            if decision:
                # Store the trade decision
                store_trade_decision(decision)
                print(f"\nTrade Decision Details:\n{decision}")
            else:
                print("No trade action taken.")
        except ValueError as e:
            print(f"Error for {symbol}: {e}. Skipping this symbol.")
            continue
        except Exception as e:
            print(f"Unexpected error for {symbol}: {e}. Skipping this symbol.")
            continue

