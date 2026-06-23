#!/usr/bin/env python3
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

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure root package path is loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

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

# Setup logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("run_scenario")


def build_history(symbol: str):
    dates = pd.date_range(end=datetime.utcnow(), periods=100)
    np_random = np.random.default_rng(42)
    returns = pd.Series(np_random.normal(0.0005, 0.01, size=100))
    prices = 100 * (1 + returns).cumprod()
    returns = prices.pct_change().fillna(0)
    return pd.DataFrame({"timestamp": dates, "symbol": symbol, "price": prices, "returns": returns})


def calculate_sharpe(navs: list) -> float:
    nav_array = np.array(navs)
    if len(nav_array) < 2:
        return 0.0
    returns = np.diff(nav_array) / nav_array[:-1]
    if returns.std() == 0:
        return 0.0
    # Annualized Sharpe ratio (assuming daily states)
    return float((returns.mean() / returns.std()) * np.sqrt(252))


def main():
    parser = argparse.ArgumentParser(description="MarketPredictor Scenario Training Loop")
    parser.add_argument('scenario', nargs='?', default="mixed", 
                        help="Scenario to run, e.g. 'flash_crash', 'bear', or 'flash_crash & bear'")
    parser.add_argument('epochs', nargs='?', type=int, default=1000, 
                        help="Number of epochs to train")
    parser.add_argument('agents_list', nargs='?', default="all", 
                        help="Agents to run/train (comma-separated, e.g. 'Sentinel,Tactician' or 'all')")
    parser.add_argument('--smoke-test', action='store_true', 
                        help="Run quick smoke test (1 year training, 0.5 years testing per epoch, fewer epochs)")
    
    args = parser.parse_args()
    
    symbol = "SPY"
    history = build_history(symbol)
    simulator = DigitalTwin(history)
    
    # 1. Parse Scenarios
    scenario_str = args.scenario
    if '&' in scenario_str:
        scenarios = [s.strip() for s in scenario_str.split('&') if s.strip()]
    else:
        scenarios = [scenario_str]
        
    print(f"\n=========================================================")
    print(f"🚀 SCENARIO TRAINING START")
    print(f"=========================================================")
    print(f"Target Scenarios: {scenarios}")
    print(f"Total Epochs:     {args.epochs}")
    print(f"Target Agents:    {args.agents_list}")
    print(f"Smoke Test Mode:  {args.smoke_test}")
    print(f"=========================================================\n")
    
    # 2. Parse and Instantiate Target Agents
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
    
    requested_names = [a.strip().lower() for a in args.agents_list.split(",") if a.strip()]
    
    active_agents = []
    if "all" in requested_names:
        active_agents = [
            Berserker(), 
            NLPExplorer(), 
            QuantExplorer(), 
            Sentinel(), 
            Anchor(), 
            CapitalManager(),
            RLTactician()
        ]
    else:
        for name in requested_names:
            matched_cls = None
            if name in agent_map:
                matched_cls = agent_map[name]
            else:
                for k, cls in agent_map.items():
                    if k in name or name in k:
                        matched_cls = cls
                        break
            if matched_cls:
                active_agents.append(matched_cls())
            else:
                print(f"⚠️ Warning: Could not match agent name '{name}'")
    if not active_agents:
        print("❌ Error: No valid agents loaded.")
        sys.exit(1)
        
    print(f"Active Agents in Orchestration: {[a.name for a in active_agents]}")
    
    # 3. Setup CSV log
    csv_file = "training_results.csv"
    csv_header = ["epoch", "scenario", "train_days", "test_days", "start_nav", "final_nav", "pnl", "trades_count", "win_rate", "sharpe_ratio"]
    
    # Write header if new file
    file_exists = os.path.exists(csv_file)
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(csv_header)
            
    # Set run lengths
    train_days = 252 if args.smoke_test else 5 * 252
    test_days = 126 if args.smoke_test else 2 * 252
    
    # Track history of parameters and performance across all epochs for performance-weighted normalization
    parameter_histories = {agent.name: {k: [] for k in agent.parameters.keys()} for agent in active_agents}
    performance_histories = {agent.name: [] for agent in active_agents}
    
    # Run loop
    for epoch in range(1, args.epochs + 1):
        current_scenario = random.choice(scenarios)
        
        # --- PHASE 1: TRAINING ---
        # Enable parameter adaptation
        for agent in active_agents:
            agent.learning_enabled = True
            
        train_states = simulator.generate(symbol, days=train_days, scenario=current_scenario)
        
        for state in train_states:
            for agent in active_agents:
                agent.update(state)
                intents = agent.decide(state)
                # Run virtual execution to adapt parameters
                for intent in intents:
                    agent.execute_virtual_intent(intent, state.price)
                    
        # Close out virtual portfolio at training end to finalize training step
        final_train_price = train_states[-1].price if train_states else 100.0
        for agent in active_agents:
            agent.close_all_virtual(final_train_price, symbol)
            # Record current state of parameters and agent's virtual realized PnL
            for k in agent.parameters.keys():
                parameter_histories[agent.name][k].append(agent.parameters[k])
            performance_histories[agent.name].append(agent.virtual_realized_pnl)
            agent.save_parameters()
            
        # --- PHASE 2: TESTING (OUT-OF-SAMPLE) ---
        # Disable parameter adaptation to test performance on frozen parameters
        for agent in active_agents:
            agent.learning_enabled = False
            agent.reset()
            
        test_states = simulator.generate(symbol, days=test_days, scenario=current_scenario)
        
        blackboard = Blackboard()
        protocol = SyntheticHedgeProtocol(blackboard)
        portfolio = Portfolio(cash=1_000_000.0)
        starting_nav = portfolio.cash
        
        test_navs = []
        
        for state in test_states:
            current_nav = portfolio.net_asset_value({symbol: state.price})
            protocol.update(state, current_nav=current_nav)
            
            # Agents observe and decide
            for agent in active_agents:
                agent.update(state)
                intents = agent.decide(state)
                
                # Apply filter to scout agents
                if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                    intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
                    
                # Register intents
                for intent in intents:
                    # Sync virtual portfolio (executes the raw intent fully on the agent's virtual tracker)
                    agent.execute_virtual_intent(intent, state.price)
                    try:
                        blackboard.register_model_intent(intent)
                    except Exception:
                        pass
                    
            # Resolve blackboard netting
            orders = blackboard.resolve(state.price)
            
            # Execute netted orders
            for order in orders:
                portfolio.execute(order.symbol, order.side, order.quantity, state.price)
                
            # Settle options daily (1-day hold)
            portfolio.settle_options_daily(state.price)
                
            # Track daily test NAV
            current_nav = portfolio.net_asset_value({symbol: state.price})
            test_navs.append(current_nav)
            
        # Close out testing portfolio
        final_test_price = test_states[-1].price if test_states else 100.0
        portfolio.close_all({symbol: final_test_price})
        portfolio.settle_options(final_test_price)
        
        # Close out virtual portfolios
        for agent in active_agents:
            agent.close_all_virtual(final_test_price, symbol)
            
        # Compute test metrics
        final_nav = portfolio.net_asset_value({symbol: final_test_price})
        pnl = final_nav - starting_nav
        
        # Extract trade statistics
        trades = portfolio.get_trade_history()
        round_trips = [t for t in trades if t['side'] in ('SELL', 'COVER', 'PUT_SETTLE', 'CALL_SETTLE')]
        trades_count = len(round_trips)
        winning_trades = sum(1 for t in round_trips if t.get('trade_pnl', 0) > 0)
        win_rate = (winning_trades / trades_count * 100.0) if trades_count > 0 else 0.0
        sharpe = calculate_sharpe(test_navs)
        
        # Save results to CSV
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([epoch, current_scenario, train_days, test_days, starting_nav, final_nav, pnl, trades_count, win_rate, sharpe])
            
        # Print progress summary
        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            print(f"📅 Epoch {epoch:04d}/{args.epochs:04d} | Scenario: {current_scenario.upper()}")
            print(f"   Train Days: {train_days} | Test Days: {test_days}")
            print(f"   Test NAV:   ${final_nav:,.2f} (PnL: ${pnl:+,.2f})")
            print(f"   Activity:   {trades_count} trades | Win Rate: {win_rate:.1f}% | Sharpe: {sharpe:.3f}")
            
            # Print snapshot of dynamic agent parameters to show adaptation
            print(f"   Agent Parameter Snapshot & Capital Consumption:")
            for agent in active_agents:
                # Show dynamic capital allocated
                allocated_cap = getattr(agent, 'allocated_capital', 0.0)
                virtual_pnl = getattr(agent, 'virtual_realized_pnl', 0.0)
                virtual_cash = getattr(agent, 'virtual_cash', 0.0)
                print(f"     {agent.name:<18} -> Allocated Cap: ${allocated_cap:,.2f} | Virtual PnL: ${virtual_pnl:+,.2f} | Virtual Cash: ${virtual_cash:,.2f}")
            print(f"---------------------------------------------------------")

    # Calculate and assign performance-weighted normalized parameter sets based on training runs
    print(f"\n[Post-Training] Consolidating parameter histories. Assigning and saving performance-normalized parameters...")
    for agent in active_agents:
        performances = np.array(performance_histories[agent.name])
        # Calculate weights using softmax over Z-scored performance
        if len(performances) > 1 and np.std(performances) > 1e-8:
            z_scores = (performances - np.mean(performances)) / np.std(performances)
            exp_z = np.exp(z_scores - np.max(z_scores))
            weights = exp_z / np.sum(exp_z)
        else:
            weights = np.ones(len(performances)) / len(performances)
            
        print(f"  Agent: {agent.name:<18} | Max PnL: ${np.max(performances):+,.2f} | Min PnL: ${np.min(performances):+,.2f}")
        
        for k in agent.parameters.keys():
            history_vals = np.array(parameter_histories[agent.name][k])
            if len(history_vals) > 0:
                weighted_val = np.sum(history_vals * weights)
                # Cast back to the original type to avoid JSON serialization/type issues
                orig_type = type(agent.parameters[k])
                agent.parameters[k] = orig_type(weighted_val)
        agent.save_parameters()
        print(f"  ✓ Saved performance-normalized parameters for '{agent.name}'")


if __name__ == "__main__":
    main()
