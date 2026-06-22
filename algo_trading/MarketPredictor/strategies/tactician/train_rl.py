#!/usr/bin/env python3
import os
import sys
import csv
import random
import argparse
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Ensure core paths are loaded
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Load environmental configs
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

from simulator.simulator import DigitalTwin
from simulator.gym_env import AITradingEnv
from strategies.tactician.dqn_agent import DQNAgent

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("train_rl")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Train a PyTorch Deep Q-Network Agent on market data.")
    parser.add_argument("--symbol", type=str, default="NSE_TOP10", help="Ticker, comma-separated list, or basket: NSE_TOP5, NSE_TOP10")
    parser.add_argument("--days", type=int, default=1260, help="Total historical days to fetch (e.g. 1260 for 3 years train + 2 years test)")
    parser.add_argument("--train-days", type=int, default=756, help="Days of data used for training (default 756 / 3 years)")
    parser.add_argument("--test-days", type=int, default=504, help="Days of data held out for testing (default 504 / 2 years)")
    parser.add_argument("--epochs", type=int, default=200, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate for DQN optimizer")
    parser.add_argument("--smoke-test", action="store_true", help="Run a quick 5-epoch smoke test")
    parser.add_argument("--scenario", type=str, default="mixed", help="Scenarios to train on (comma-separated list, e.g., 'bear,flash_crash' or 'mixed')")
    parser.add_argument("--resume", action="store_true", help="Resume training from existing model weights")
    parser.add_argument("--gamma", type=float, default=0.997, help="Discount factor for Q-learning")
    return parser.parse_args()

def calculate_sharpe(navs: list) -> float:
    nav_array = np.array(navs)
    if len(nav_array) < 2:
        return 0.0
    returns = np.diff(nav_array) / nav_array[:-1]
    if returns.std() == 0:
        return 0.0
    return float((returns.mean() / (returns.std() + 1e-8)) * np.sqrt(252))

def build_history(symbol: str):
    dates = pd.date_range(end=datetime.now(), periods=100)
    np_random = np.random.default_rng(42)
    returns = pd.Series(np_random.normal(0.0005, 0.01, size=100))
    prices = 100 * (1 + returns).cumprod()
    returns = prices.pct_change().fillna(0)
    return pd.DataFrame({"timestamp": dates, "symbol": symbol, "price": prices, "returns": returns})

def main():
    args = parse_arguments()
    symbol_arg = args.symbol.upper()
    days = args.days
    train_days = args.train_days
    test_days = args.test_days
    epochs = args.epochs
    lr = args.lr
    
    # Pre-defined baskets mapping for Indian stock indices
    baskets = {
        "NSE_TOP5": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"],
        "NSE_TOP10": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", 
                      "BHARTIARTL.NS", "SBIN.NS", "LICI.NS", "LTIM.NS", "ITC.NS"],
        "NIFTY50": [
            "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
            "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
            "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
            "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
            "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
            "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
            "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
            "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
            "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
            "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"
        ]
    }
    
    if symbol_arg in baskets:
        symbols_list = baskets[symbol_arg]
    elif "," in symbol_arg:
        symbols_list = [s.strip() for s in symbol_arg.split(",") if s.strip()]
    else:
        symbols_list = [symbol_arg]
        
    if args.smoke_test:
        epochs = 5
        days = 126
        train_days = 80
        test_days = 46
        print("⚡ Running in SMOKE-TEST mode (5 epochs, 126 calibration days)")
        
    print("\n" + "="*80)
    print(f"🎮 STARTING DEEP REINFORCEMENT LEARNING TRAINING FOR {symbol_arg}")
    print(f"Symbols Basket ({len(symbols_list)} tickers): {symbols_list}")
    print(f"Temporal Split Config: {train_days} Train Days, {test_days} Test Days (Total: {days} days)")
    print("="*80)
    
    # 1. Load historical calibration data for all symbols
    symbol_train_data = {}
    symbol_test_data = {}
    
    print(f"[1/4] Loading calibration data for tickers...")
    for sym in symbols_list:
        real_data = None
        if sym != "SPY":
            try:
                real_data = DigitalTwin.fetch_real_market_data(sym, days=days)
            except Exception as e:
                print(f"⚠️ Warning: Failed to fetch real data for {sym}: {e}")
                
        if real_data is None or real_data.empty:
            print(f"✓ Falling back to synthetic history generation for {sym} (Offline/No-data Mode)...")
            real_data = build_history(sym)
            
        # Temporal Split logic (e.g. 3 years Train, 2 years Test)
        if len(real_data) >= train_days + test_days:
            train_df = real_data.iloc[:train_days].reset_index(drop=True)
            test_df = real_data.iloc[train_days:train_days+test_days].reset_index(drop=True)
        else:
            split_idx = int(len(real_data) * 0.6)
            train_df = real_data.iloc[:split_idx].reset_index(drop=True)
            test_df = real_data.iloc[split_idx:].reset_index(drop=True)
            
        symbol_train_data[sym] = train_df
        symbol_test_data[sym] = test_df
        print(f"  ✓ {sym} loaded. Train shape: {len(train_df)} rows | Test shape: {len(test_df)} rows")
        
    # 2. Instantiate DQN Agent (always uses state_dim=7, action_dim=5)
    agent = DQNAgent(state_dim=7, action_dim=5, lr=lr)
    
    model_path = "rl_trading_model.pt"
    is_resumed = False
    if args.resume:
        if os.path.exists(model_path):
            try:
                agent.load(model_path)
                print(f"✓ Resumed model parameters successfully from {model_path}.")
                is_resumed = True
            except Exception as e:
                print(f"⚠️ Warning: Failed to load existing model from {model_path}, starting fresh: {e}")
        else:
            print(f"⚠️ Warning: No existing model found at {model_path} to resume. Starting fresh.")
            
    # Setup results logger
    csv_file = "training_results.csv"
    csv_header = ["epoch", "selected_symbol", "scenario", "train_days", "test_days", "start_nav", "final_nav", "pnl", "trades_count", "win_rate", "sharpe_ratio"]
    file_exists = os.path.exists(csv_file)
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(csv_header)
            
    # Epsilon decay settings for exploration/exploitation balance
    eps_start = 1.0
    eps_end = 0.1
    if is_resumed:
        eps_start = 0.25  # Start with reduced exploration if resuming
    eps_decay = (eps_start - eps_end) / float(max(1, epochs - 10))
    epsilon = eps_start
    
    best_pnl = -9999999.0
    train_len = 252  # Run environment for 252 steps per epoch (1 simulated year)
    
    # 3. Training Loop
    print(f"\n[2/4] Training DQN Agent for {epochs} epochs...")
    
    # Parse scenarios list
    if args.scenario.lower() == "mixed":
        scenarios = ["bull", "bear", "chop", "flash_crash", "mixed"]
    else:
        scenarios = [s.strip().lower() for s in args.scenario.split(",") if s.strip()]
        
    print(f"✓ Target Scenarios: {scenarios}")
    
    for epoch in range(1, epochs + 1):
        selected_scenario = random.choice(scenarios)
        # Multi-asset joint training: randomly select a symbol from the basket at the start of each epoch
        selected_symbol = random.choice(symbols_list)
        
        train_df = symbol_train_data[selected_symbol]
        
        # Calibrate DigitalTwin dynamically on the training slice of the selected symbol
        twin = DigitalTwin(train_df, symbol=selected_symbol)
        env = AITradingEnv(twin, selected_symbol, days=train_len, scenario=selected_scenario, starting_capital=1000000.0)
        
        obs = env.reset(scenario=selected_scenario)
        
        done = False
        episode_reward = 0.0
        navs_history = [env.starting_capital]
        losses = []
        
        while not done:
            # Select action
            action = agent.select_action(obs, epsilon)
            
            # Execute step
            next_obs, reward, done, info = env.step(action)
            
            # Push transition to experience replay buffer
            agent.replay_buffer.push(obs, action, reward, next_obs, done)
            
            # Optimize network parameters
            loss = agent.train_step(batch_size=64, gamma=args.gamma)
            if loss > 0:
                losses.append(loss)
                
            episode_reward += reward
            navs_history.append(info["nav"])
            obs = next_obs
            
        # Target network sync every 5 epochs
        if epoch % 5 == 0:
            agent.update_target_network()
            
        # Decay epsilon exploration rate
        epsilon = max(eps_end, epsilon - eps_decay)
        
        # Calculate episode summary statistics
        final_nav = navs_history[-1]
        pnl = final_nav - env.starting_capital
        trades_count = info["trades"]
        
        # Compute Win Rate from Trade History
        trade_history = env.portfolio.get_trade_history()
        round_trips = [t for t in trade_history if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
        wins = sum(1 for t in round_trips if t.get('trade_pnl', 0) > 0)
        win_rate = (wins / len(round_trips) * 100.0) if len(round_trips) > 0 else 0.0
        
        sharpe = calculate_sharpe(navs_history)
        avg_loss = np.mean(losses) if losses else 0.0
        
        # Append epoch results to training_results.csv (including symbol column)
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([epoch, selected_symbol, selected_scenario, len(train_df), len(symbol_test_data[selected_symbol]), env.starting_capital, final_nav, pnl, trades_count, win_rate, sharpe])
            
        # Keep track and save best model weights
        if pnl > best_pnl and not args.smoke_test:
            best_pnl = pnl
            agent.save("rl_trading_model.pt")
            
        # Console output summary
        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            print(f"   Epoch {epoch:03d}/{epochs:03d} | Stock: {selected_symbol:12s} | Scenario: {selected_scenario.upper():11s} | "
                  f"Loss: {avg_loss:6.4f} | PnL: INR {pnl:+,.2f} | "
                  f"Trades: {trades_count:2d} | Win Rate: {win_rate:5.1f}% | Sharpe: {sharpe:+.3f}")
            
    # For smoke test, save model unconditionally to verify pipeline output
    if args.smoke_test:
        agent.save("rl_trading_model.pt")
        print("\n✓ Smoke test finished. Model saved.")
    else:
        print(f"\n[3/4] Training complete. Best PnL: INR {best_pnl:+,.2f}. Model saved to rl_trading_model.pt")
        
    # 5. Save learner config
    print("[4/4] Persisting learner parameters to database...")
    twin.save_learner()
    print("✓ Learner state saved to DB successfully.")
    
if __name__ == '__main__':
    main()
