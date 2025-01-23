#!/usr/bin/env python
# coding: utf-8

# In[31]:


import requests
import time
import random
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

# Simulated breakout strategy
def breakout_strategy(symbol, opening_high, opening_low, current_price, direction="bullish"):
    print(f"Monitoring {symbol} for a {direction} breakout...")
    breakout_level = opening_high if direction == "bullish" else opening_low

    if (direction == "bullish" and current_price > breakout_level) or \
       (direction == "bearish" and current_price < breakout_level):
        print(f"{direction.capitalize()} breakout detected for {symbol} at ${current_price:.2f}!")

        # Wait for QRNG-determined delay
        delay = quantum_random_interval(2, 10)
        print(f"Waiting {delay} minutes to confirm breakout...")
        time.sleep(delay * 60)  # Convert minutes to seconds for demo

        # Generate quantum price target
        range_percentage = 0.02  # Example: 2% range
        target_price = quantum_price_target(current_price, range_percentage)

        # Generate embedding for proximity analysis
        embedding = [
            breakout_level / 200.0,
            current_price / 200.0,
            target_price / 200.0
        ]

        # Convert UTC time to Phoenix time
        utc_time = datetime.utcnow()
        phoenix_time = utc_time.astimezone(timezone('America/Phoenix'))

        return {
            "symbol": symbol,
            "direction": direction,
            "entry_price": current_price,
            "target_price": target_price,
            "breakout_level": breakout_level,
            "delay_minutes": delay,
            "embedding": embedding,
            "executed_at": phoenix_time
        }
    else:
        print(f"No breakout detected for {symbol} at ${current_price:.2f}. Support: ${opening_low:.2f}, Resistance: ${opening_high:.2f}")
        return None

# Store simulated trade in database
def store_simulated_trade(trade):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Insert trade into the simulated_trades table
        insert_query = """
        INSERT INTO simulated_trades (
            symbol, direction, entry_price, target_price, breakout_level, 
            delay_minutes, embedding, executed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(insert_query, (
            trade["symbol"], trade["direction"], trade["entry_price"],
            trade["target_price"], trade["breakout_level"],
            trade["delay_minutes"], trade["embedding"], trade["executed_at"]
        ))
        conn.commit()
        print("Simulated trade stored successfully.")
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()

# Validate target price with market data
def validate_target_price(symbol, target_price, executed_at, validation_window=60):
    try:
        start_time = executed_at.strftime('%Y-%m-%dT%H:%M:%SZ')
        barset = alpaca.get_bars(
            symbol,
            TimeFrame.Minute,
            start=start_time,
            limit=validation_window,
            feed="iex"
        )
        prices = [bar.h for bar in barset]
        if prices:
            closest_price = max(prices)
            target_hit = any(price >= target_price for price in prices)
        else:
            closest_price = None
            target_hit = False
        return {
            "target_hit": target_hit,
            "closest_price": closest_price,
            "validation_window": validation_window
        }
    except Exception as e:
        print(f"Error validating target price: {e}")
        return {
            "target_hit": False,
            "closest_price": None,
            "validation_window": validation_window
        }

# Simulate and validate a trade
def simulate_and_store_trade_with_validation(symbol, opening_high, opening_low, current_price, direction="bullish"):
    trade = breakout_strategy(symbol, opening_high, opening_low, current_price, direction)
    if trade:
        store_simulated_trade(trade)
        print(f"\nSimulated Trade Details:\n{trade}")
        validation_results = validate_target_price(
            symbol, trade["target_price"], trade["executed_at"], validation_window=60
        )
        print("\nValidation Results:")
        print(f"Target Hit: {validation_results['target_hit']}")
        print(f"Closest Price: {validation_results['closest_price']}")
        print(f"Validation Window: {validation_results['validation_window']} minutes")
    else:
        print("No trade simulated.")

# Run the simulation for multiple symbols with both bullish and bearish scenarios
if __name__ == "__main__":
    symbols = ["NVDA", "IONQ", "AMD", "MU", "GILD", "INTC", "AMBA"]
    for symbol in symbols:
        try:
            market_levels = fetch_market_levels(symbol, timeframe=TimeFrame.Minute, lookback=50)
            
            if market_levels:
                print(f"\nAnalyzing {symbol}:")
                phoenix_time = market_levels["timestamp"].astimezone(timezone('America/Phoenix'))
                print(f"Current price: ${market_levels['current_price']:.2f} at {phoenix_time.strftime('%Y-%m-%d %H:%M:%S %Z')} (Phoenix Time)")
                print(f"Support Level: ${market_levels['support']:.2f}, Resistance Level: ${market_levels['resistance']:.2f}")

                # Check for bullish breakout
                simulate_and_store_trade_with_validation(
                    symbol,
                    opening_high=market_levels["resistance"],
                    opening_low=market_levels["support"],
                    current_price=market_levels["current_price"],
                    direction="bullish"
                )
    
                # Check for bearish breakout
                simulate_and_store_trade_with_validation(
                    symbol,
                    opening_high=market_levels["resistance"],
                    opening_low=market_levels["support"],
                    current_price=market_levels["current_price"],
                    direction="bearish"
                )
        except ValueError as e:
            print(f"Error for {symbol}: {e}. Skipping this symbol.")
            continue
        except Exception as e:
            print(f"Unexpected error for {symbol}: {e}. Skipping this symbol.")
            continue



