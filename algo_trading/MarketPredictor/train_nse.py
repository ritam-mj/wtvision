#!/usr/bin/env python3
"""
NSE Agent Training and Backtesting Orchestrator.
Calibrates simulation parameters to real Indian stock history, trains agents via 
domain-randomized scenarios, and backtests performance on actual historical data.

Usage:
    # Train on Nifty 50 Index for 252 days of history
    python train_nse.py --symbol "^NSEI" --days 252 --epochs 200

    # Train on Reliance Industries
    python train_nse.py --symbol "RELIANCE.NS" --days 252 --epochs 100
"""

import os
import sys
import io
import csv
import random
import argparse
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Setup UTF-8 encoding for standard output to support emojis on Windows terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure core packages path is loaded
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load .env file
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

from strategies.heuristic.marketstate import MarketState, CyclePhase
from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from strategies.heuristic.agents import Berserker, Sentinel, Anchor, CapitalManager
from strategies.explorer.nlp_model import NLPExplorer
from strategies.explorer.company_evaluator import QuantExplorer
from strategies.tactician.rl_agent import RLTactician
from simulator.simulator import DigitalTwin
from simulator.state_persistence import StateManager
from core.execution import Portfolio

# Logging setup
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("train_nse")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calibrate and train MarketPredictor agents on NSE historical tickers.")
    parser.add_argument(
        "--symbol",
        type=str,
        default="RELIANCE.NS",
        help="NSE Ticker symbol ending in .NS or .BO (default: RELIANCE.NS)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=252,
        help="Historical lookback days for calibration/testing (default: 252)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of simulation training epochs (default: 100)"
    )
    parser.add_argument(
        "--agents",
        type=str,
        default="all",
        help="Comma-separated agents to train or 'all' (default: all)"
    )
    return parser.parse_args()


def calculate_sharpe(navs: list) -> float:
    nav_array = np.array(navs)
    if len(nav_array) < 2:
        return 0.0
    returns = np.diff(nav_array) / nav_array[:-1]
    if returns.std() == 0:
        return 0.0
    return float((returns.mean() / returns.std()) * np.sqrt(252))


def calculate_drawdown(prices: np.ndarray) -> float:
    cummax = np.maximum.accumulate(prices)
    drawdown = (prices - cummax) / cummax
    return float(drawdown.min() * 100)


def load_agents(agents_arg: str) -> list:
    agent_map = {
        "tactician": Berserker,
        "berserker": Berserker,
        "nlpexplorer": NLPExplorer,
        "quantexplorer": QuantExplorer,
        "sentinel": Sentinel,
        "anchor": Anchor,
        "capitalmanager": CapitalManager,
        "rltactician": RLTactician
    }
    requested = [a.strip().lower() for a in agents_arg.split(",") if a.strip()]
    if "all" in requested:
        return [
            Berserker(),
            NLPExplorer(),
            QuantExplorer(),
            Sentinel(),
            Anchor(),
            CapitalManager(),
            RLTactician()
        ]
    
    loaded = []
    for r in requested:
        # Match exact first
        if r in agent_map:
            loaded.append(agent_map[r]())
            continue
        # Fallback to substring matching
        for name, cls in agent_map.items():
            if r in name or name in r:
                loaded.append(cls())
                break
    return loaded


def main():
    args = parse_arguments()
    symbol = args.symbol.upper()
    days = args.days
    epochs = args.epochs
    
    print("\n" + "="*90)
    print(f"🇮🇳  NSE MARKETPREDICTOR TRAINING ORCHESTRATOR - {symbol}")
    print("="*90)
    print(f"Ticker:        {symbol}")
    print(f"History:       {days} trading days")
    print(f"Train Epochs:  {epochs}")
    print("="*90)

    # 1. Fetch Real Historical NSE data
    print(f"\n[1/5] Fetching historical price feed for {symbol}...")
    real_data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if real_data is None or real_data.empty:
        print(f"❌ Error: Failed to load market data for {symbol}.")
        print("Check if Yahoo Finance resolves the ticker or if UPSTOX_ANALYTICS_TOKEN is valid.")
        sys.exit(1)

    print(f"✓ Loaded {len(real_data)} historical rows.")
    print(f"  Range: {real_data['timestamp'].min().date()} to {real_data['timestamp'].max().date()}")
    print(f"  Close price: INR {real_data['price'].iloc[0]:.2f} -> INR {real_data['price'].iloc[-1]:.2f}")

    # 2. Calibrate the DigitalTwin Simulator to NSE ticker statistics
    print(f"\n[2/5] Calibrating Merton Jump Diffusion and volatility models...")
    twin = DigitalTwin(real_data, symbol=symbol)
    
    # Save base historical baseline parameters
    calibrated_states = twin.generate_from_real_data(symbol, days=len(real_data), data_df=real_data)
    print(f"✓ Calibrated {len(calibrated_states)} historical cycles successfully.")

    # 3. Load Agents
    agents = load_agents(args.agents)
    if not agents:
        print("❌ Error: No valid agents loaded.")
        sys.exit(1)
    print(f"✓ Orchestrated {len(agents)} agents: {[a.name for a in agents]}")

    # 4. Run Randomized Simulation Scenarios (Model Training Phase)
    print(f"\n[3/5] Starting scenario-based parameter adaptation ({epochs} epochs)...")
    scenarios = ["bull", "bear", "chop", "flash_crash", "mixed"]
    
    csv_file = "training_results.csv"
    csv_header = ["epoch", "scenario", "train_days", "test_days", "start_nav", "final_nav", "pnl", "trades_count", "win_rate", "sharpe_ratio"]
    file_exists = os.path.exists(csv_file)
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(csv_header)

    train_len = 252  # 1 trading year synthetic simulation per epoch
    test_len = 126   # 6 months out-of-sample simulation per epoch

    # Track history of parameters and performance across all epochs for performance-weighted normalization
    parameter_histories = {agent.name: {k: [] for k in agent.parameters.keys()} for agent in agents}
    performance_histories = {agent.name: [] for agent in agents}

    for epoch in range(1, epochs + 1):
        selected_scenario = random.choice(scenarios)
        
        # --- Adaptation Step ---
        for agent in agents:
            agent.learning_enabled = True
            
        simulated_states = twin.generate(symbol, days=train_len, scenario=selected_scenario, use_learning=True)
        
        for state in simulated_states:
            for agent in agents:
                agent.update(state)
                intents = agent.decide(state)
                for intent in intents:
                    agent.execute_virtual_intent(intent, state.price)
                    
        # Close out virtual portfolio to store optimization weights
        final_price = simulated_states[-1].price if simulated_states else real_data['price'].iloc[-1]
        for agent in agents:
            agent.close_all_virtual(final_price, symbol)
            # Record current state of parameters and agent's virtual realized PnL
            for k in agent.parameters.keys():
                parameter_histories[agent.name][k].append(agent.parameters[k])
            performance_histories[agent.name].append(agent.virtual_realized_pnl)
            agent.save_parameters()

        # --- Evaluator Step ---
        for agent in agents:
            agent.learning_enabled = False
            agent.reset()
            
        test_states = twin.generate(symbol, days=test_len, scenario=selected_scenario, use_learning=False)
        blackboard = Blackboard()
        protocol = SyntheticHedgeProtocol(blackboard)
        
        # Three separate portfolios, each starting with 100% allocation (1,000,000 INR starting capital each)
        portfolio_heur = Portfolio(cash=1000000.0)
        portfolio_rl = Portfolio(cash=1000000.0)
        portfolio_explorer = Portfolio(cash=1000000.0)
        start_cap = 3000000.0
        test_navs = []
        
        for state in test_states:
            current_nav = portfolio_heur.net_asset_value({symbol: state.price})
            protocol.update(state, current_nav=current_nav)
            for agent in agents:
                agent.update(state)
                intents = agent.decide(state)
                
                # Filter scouts
                if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                    intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
                    
                for intent in intents:
                    agent.execute_virtual_intent(intent, state.price)
                    try:
                        blackboard.register_model_intent(intent)
                    except:
                        pass
                    
            orders = blackboard.resolve(state.price)
            for order in orders:
                if order.model_name == "The RL Tactician":
                    portfolio_rl.execute(order.symbol, order.side, order.quantity, state.price)
                elif order.model_name in ("The NLP Explorer", "The Quant Explorer"):
                    portfolio_explorer.execute(order.symbol, order.side, order.quantity, state.price)
                else:
                    portfolio_heur.execute(order.symbol, order.side, order.quantity, state.price)
            portfolio_rl.settle_options_daily(state.price)
            portfolio_heur.settle_options_daily(state.price)
            portfolio_explorer.settle_options_daily(state.price)
            
            nav_rl = portfolio_rl.net_asset_value({symbol: state.price})
            nav_heur = portfolio_heur.net_asset_value({symbol: state.price})
            nav_exp = portfolio_explorer.net_asset_value({symbol: state.price})
            test_navs.append(nav_rl + nav_heur + nav_exp)
 
        final_test_price = test_states[-1].price if test_states else real_data['price'].iloc[-1]
        portfolio_rl.close_all({symbol: final_test_price})
        portfolio_heur.close_all({symbol: final_test_price})
        portfolio_explorer.close_all({symbol: final_test_price})
        portfolio_rl.settle_options(final_test_price)
        portfolio_heur.settle_options(final_test_price)
        portfolio_explorer.settle_options(final_test_price)
        
        for agent in agents:
            agent.close_all_virtual(final_test_price, symbol)
 
        # Log metrics
        final_nav_rl = portfolio_rl.net_asset_value({symbol: final_test_price})
        final_nav_heur = portfolio_heur.net_asset_value({symbol: final_test_price})
        final_nav_exp = portfolio_explorer.net_asset_value({symbol: final_test_price})
        final_nav = final_nav_rl + final_nav_heur + final_nav_exp
        pnl = final_nav - start_cap
        
        trades = portfolio_rl.get_trade_history() + portfolio_heur.get_trade_history() + portfolio_explorer.get_trade_history()
        completed_trades = [t for t in trades if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
        trades_count = len(completed_trades)
        wins = sum(1 for t in completed_trades if t.get('trade_pnl', 0) > 0)
        win_rate = (wins / trades_count * 100.0) if trades_count > 0 else 0.0
        sharpe = calculate_sharpe(test_navs)
        
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([epoch, selected_scenario, train_len, test_len, start_cap, final_nav, pnl, trades_count, win_rate, sharpe])
 
        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            print(f"   Epoch {epoch:03d}/{epochs:03d} | Scenario: {selected_scenario.upper()} | Test PnL: INR {pnl:+,.2f} | Win Rate: {win_rate:.1f}% | Sharpe: {sharpe:.3f}")

    # Calculate and assign performance-weighted normalized parameter sets based on training runs
    print(f"\n[3.5/5] Consolidating parameter histories. Assigning and saving performance-normalized parameters...")
    for agent in agents:
        performances = np.array(performance_histories[agent.name])
        # Calculate weights using softmax over Z-scored performance
        if len(performances) > 1 and np.std(performances) > 1e-8:
            z_scores = (performances - np.mean(performances)) / np.std(performances)
            exp_z = np.exp(z_scores - np.max(z_scores))
            weights = exp_z / np.sum(exp_z)
        else:
            weights = np.ones(len(performances)) / len(performances)
            
        print(f"  Agent: {agent.name:<18} | Max PnL: INR {np.max(performances):+,.2f} | Min PnL: INR {np.min(performances):+,.2f}")
        
        for k in agent.parameters.keys():
            history_vals = np.array(parameter_histories[agent.name][k])
            if len(history_vals) > 0:
                weighted_val = np.sum(history_vals * weights)
                # Cast back to the original type to avoid JSON serialization/type issues
                orig_type = type(agent.parameters[k])
                agent.parameters[k] = orig_type(weighted_val)
        agent.save_parameters()
        print(f"  ✓ Saved performance-normalized parameters for '{agent.name}'")

    # Save learner state parameters to DB
    print(f"\n[4/5] Saving calibrated learner history to DB...")
    twin.save_learner()

    # 5. Out-of-Sample Historical Backtest
    print(f"\n[5/5] Running validation backtest on real historical {symbol} data...")
    for agent in agents:
        agent.learning_enabled = False
        agent.reset()
        
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    
    # Three separate portfolios, each starting with 100% allocation (1,000,000 INR starting capital each)
    portfolio_heur = Portfolio(cash=1000000.0)
    portfolio_rl = Portfolio(cash=1000000.0)
    portfolio_explorer = Portfolio(cash=1000000.0)
    starting_capital = 3000000.0
    
    historical_navs = []
    historical_navs_rl = []
    historical_navs_heur = []
    historical_navs_explorer = []
    
    for state in calibrated_states:
        current_nav = portfolio_heur.net_asset_value({symbol: state.price})
        protocol.update(state, current_nav=current_nav)
        for agent in agents:
            agent.update(state)
            intents = agent.decide(state)
            
            # Apply scout filter
            if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
                
            for intent in intents:
                agent.execute_virtual_intent(intent, state.price)
                try:
                    blackboard.register_model_intent(intent)
                except:
                    pass
                
        orders = blackboard.resolve(state.price)
        for order in orders:
            if order.model_name == "The RL Tactician":
                portfolio_rl.execute(order.symbol, order.side, order.quantity, state.price)
            elif order.model_name in ("The NLP Explorer", "The Quant Explorer"):
                portfolio_explorer.execute(order.symbol, order.side, order.quantity, state.price)
            else:
                portfolio_heur.execute(order.symbol, order.side, order.quantity, state.price)
                    
        portfolio_rl.settle_options_daily(state.price)
        portfolio_heur.settle_options_daily(state.price)
        portfolio_explorer.settle_options_daily(state.price)
        
        nav_rl = portfolio_rl.net_asset_value({symbol: state.price})
        nav_heur = portfolio_heur.net_asset_value({symbol: state.price})
        nav_exp = portfolio_explorer.net_asset_value({symbol: state.price})
        
        historical_navs_rl.append(nav_rl)
        historical_navs_heur.append(nav_heur)
        historical_navs_explorer.append(nav_exp)
        historical_navs.append(nav_rl + nav_heur + nav_exp)

    final_price = calibrated_states[-1].price
    portfolio_rl.close_all({symbol: final_price})
    portfolio_heur.close_all({symbol: final_price})
    portfolio_explorer.close_all({symbol: final_price})
    portfolio_rl.settle_options(final_price)
    portfolio_heur.settle_options(final_price)
    portfolio_explorer.settle_options(final_price)
    
    final_nav_rl = portfolio_rl.net_asset_value({symbol: final_price})
    final_nav_heur = portfolio_heur.net_asset_value({symbol: final_price})
    final_nav_exp = portfolio_explorer.net_asset_value({symbol: final_price})
    final_nav = final_nav_rl + final_nav_heur + final_nav_exp
    
    # Process RL metrics
    trades_rl = portfolio_rl.get_trade_history()
    completed_rl = [t for t in trades_rl if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
    total_trades_rl = len(completed_rl)
    winning_trades_rl = sum(1 for t in completed_rl if t.get('trade_pnl', 0) > 0)
    win_rate_rl = (winning_trades_rl / total_trades_rl * 100) if total_trades_rl > 0 else 0.0
    sharpe_ratio_rl = calculate_sharpe(historical_navs_rl)
    strategy_return_rl = ((final_nav_rl / 1000000.0) - 1) * 100
    
    # Process Heuristics metrics
    trades_heur = portfolio_heur.get_trade_history()
    completed_heur = [t for t in trades_heur if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
    total_trades_heur = len(completed_heur)
    winning_trades_heur = sum(1 for t in completed_heur if t.get('trade_pnl', 0) > 0)
    win_rate_heur = (winning_trades_heur / total_trades_heur * 100) if total_trades_heur > 0 else 0.0
    sharpe_ratio_heur = calculate_sharpe(historical_navs_heur)
    strategy_return_heur = ((final_nav_heur / 1000000.0) - 1) * 100

    # Process Explorer metrics
    trades_exp = portfolio_explorer.get_trade_history()
    completed_exp = [t for t in trades_exp if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
    total_trades_exp = len(completed_exp)
    winning_trades_exp = sum(1 for t in completed_exp if t.get('trade_pnl', 0) > 0)
    win_rate_exp = (winning_trades_exp / total_trades_exp * 100) if total_trades_exp > 0 else 0.0
    sharpe_ratio_exp = calculate_sharpe(historical_navs_explorer)
    strategy_return_explorer = ((final_nav_exp / 1000000.0) - 1) * 100
    
    # Process Overall metrics
    total_trades = total_trades_rl + total_trades_heur + total_trades_exp
    winning_trades = winning_trades_rl + winning_trades_heur + winning_trades_exp
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    max_dd = calculate_drawdown(np.array(historical_navs + [final_nav]))
    sharpe_ratio = calculate_sharpe(historical_navs)
    market_return = ((calibrated_states[-1].price / calibrated_states[0].price) - 1) * 100
    strategy_return = ((final_nav / starting_capital) - 1) * 100
    alpha = strategy_return - market_return

    print("\n" + "="*90)
    print(f"📊 HISTORICAL VALIDATION REPORT - {symbol}")
    print("="*90)
    print(f"  Market Return ({symbol}): {market_return:+.2f}%")
    print(f"  Overall Combined Return:  {strategy_return:+.2f}%")
    print(f"  Overall Combined Alpha:   {alpha:+.2f}%")
    print(f"  Overall Combined Sharpe:  {sharpe_ratio:.3f}")
    print(f"  Combined Max Drawdown:    {max_dd:-.2f}%")
    print(f"  Total Trades Executed:    {total_trades}")
    print(f"  Winning Trades:           {winning_trades} (Win Rate: {win_rate:.1f}%)")
    print("-" * 90)
    print(f"  🤖 CORE PORTFOLIO (RL Model - 100% Capital):")
    print(f"    Return:               {strategy_return_rl:+.2f}%")
    print(f"    Sharpe Ratio:         {sharpe_ratio_rl:.3f}")
    print(f"    Trades Executed:      {total_trades_rl}")
    print(f"    Winning Trades:       {winning_trades_rl} (Win Rate: {win_rate_rl:.1f}%)")
    print("-" * 90)
    print(f"  ⚙️ SATELLITE PORTFOLIO (Heuristic Agents - 100% Capital):")
    print(f"    Return:               {strategy_return_heur:+.2f}%")
    print(f"    Sharpe Ratio:         {sharpe_ratio_heur:.3f}")
    print(f"    Trades Executed:      {total_trades_heur}")
    print(f"    Winning Trades:       {winning_trades_heur} (Win Rate: {win_rate_heur:.1f}%)")
    print("-" * 90)
    print(f"  🔍 EXPLORER PORTFOLIO (NLP & Quant Explorer - 100% Capital):")
    print(f"    Return:               {strategy_return_explorer:+.2f}%")
    print(f"    Sharpe Ratio:         {sharpe_ratio_exp:.3f}")
    print(f"    Trades Executed:      {total_trades_exp}")
    print(f"    Winning Trades:       {winning_trades_exp} (Win Rate: {win_rate_exp:.1f}%)")
    print("="*90)
    print(f"📊 HEURISTIC AGENTS FINAL CAPITAL CONSUMPTION REPORT:")
    print("="*90)
    for agent in agents:
        if agent.name != "The Capital Manager":
            allocated_cap = getattr(agent, 'allocated_capital', 0.0)
            virtual_pnl = getattr(agent, 'virtual_realized_pnl', 0.0)
            virtual_cash = getattr(agent, 'virtual_cash', 0.0)
            print(f"  {agent.name:<18} -> Final Allocated Cap: INR {allocated_cap:,.2f} | Virtual PnL: INR {virtual_pnl:+,.2f} | Virtual Cash: INR {virtual_cash:,.2f}")
    print("="*90)
    
    print("\n✓ Training and verification complete! Calibrated parameters persisted to DB.")


if __name__ == '__main__':
    main()
