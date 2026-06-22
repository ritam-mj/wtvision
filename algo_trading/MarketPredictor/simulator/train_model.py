#!/usr/bin/env python3
"""
Model Training and Calibration CLI for MarketPredictor.
Fetches historical market data (via Upstox or yfinance) and updates the adaptive parameter learner state in PostgreSQL.

Usage:
    python simulator/train_model.py --symbol "RELIANCE.NS" --days 90
    python simulator/train_model.py --symbol "AAPL" --days 180
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Set up paths to include workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("train_model")

# Load environment variables
load_dotenv()

from simulator.simulator import DigitalTwin

def parse_arguments():
    parser = argparse.ArgumentParser(description="Calibrate and train MarketPredictor model on historical data.")
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Ticker symbol or instrument key (e.g. 'RELIANCE.NS' or 'AAPL')"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=100,
        help="Number of trading days of historical data to train on (default: 100)"
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    symbol = args.symbol
    days = args.days

    logger.info(f"Starting model calibration for {symbol} over the last {days} trading days...")

    # 1. Fetch real historical market data (will route through Upstox if UPSTOX_ANALYTICS_TOKEN is in env, else yfinance)
    logger.info("Fetching historical data...")
    data_df = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if data_df is None or data_df.empty:
        logger.error(f"Failed to load historical data for {symbol}. Make sure UPSTOX_ANALYTICS_TOKEN is valid or yfinance can resolve the symbol.")
        sys.exit(1)

    logger.info(f"Successfully loaded {len(data_df)} days of historical data.")

    # 2. Instantiate simulator/twin
    logger.info("Initializing simulator (DigitalTwin)...")
    try:
        simulator = DigitalTwin(data_df, symbol=symbol)
    except Exception as e:
        logger.error(f"Failed to initialize DigitalTwin: {e}", exc_info=True)
        sys.exit(1)

    # 3. Trigger model training / calibration
    logger.info("Running calibration simulation...")
    try:
        states = simulator.generate_from_real_data(symbol, days=len(data_df), data_df=data_df)
        logger.info(f"Calibrated {len(states)} historical states.")
        
        # Track simulated outcomes to record best params
        # Generate ensemble runs to feed learner state history
        simulator.generate(symbol, days=len(data_df), scenario="bull", use_learning=True)
        simulator.generate(symbol, days=len(data_df), scenario="bear", use_learning=True)
        simulator.generate(symbol, days=len(data_df), scenario="chop", use_learning=True)
        
    except Exception as e:
        logger.error(f"Error during training simulation: {e}", exc_info=True)
        sys.exit(1)

    # 4. Save learner state to PostgreSQL
    logger.info("Persisting trained parameters to database...")
    try:
        simulator.save_learner()
        logger.info(f"Successfully calibrated and saved parameters for {symbol} to PostgreSQL!")
    except Exception as e:
        logger.error(f"Failed to persist learner state to DB: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
