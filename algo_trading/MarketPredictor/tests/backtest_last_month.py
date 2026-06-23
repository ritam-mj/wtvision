#!/usr/bin/env python3
"""
Backtest MarketPredictor performance over the last month against real market data.

This script:
1. Fetches the last 30 days of real market data
2. Loads your saved learner parameters
3. Runs shadow trading backtests
4. Reports detailed performance metrics
"""

import sys
import io

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import random
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulator.simulator import DigitalTwin
from simulator.state_persistence import StateManager
from strategies.heuristic.marketstate import MarketState
from simulator.learning import ShadowTrader
from core.execution import Portfolio
from strategies.heuristic.agents import (
    Berserker,
    Sentinel,
    Anchor,
    CapitalManager,
)
from strategies.explorer.nlp_model import NLPExplorer
from strategies.explorer.company_evaluator import QuantExplorer
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from strategies.heuristic.blackboard import Blackboard


def load_learner_state(symbol: str = 'SPY') -> Dict:
    """Load the saved learner state from last run"""
    try:
        state_manager = StateManager(backend='postgres')
        state = state_manager.load_learner_state(symbol)
        if state:
            return state
        return {"history": []}
    except Exception:
        print("⚠️  Database offline or state not found. Using default parameters.")
        return {"history": []}


def fetch_last_month_data(symbol: str = 'SPY') -> pd.DataFrame:
    """Fetch the last 30 days of real market data"""
    print(f"\n📊 Fetching last 30 days of {symbol} data from Yahoo Finance...")
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=30)
    
    if data is None or len(data) == 0:
        print("❌ Failed to fetch real data")
        return None
    
    print(f"✓ Got {len(data)} days of data")
    print(f"  Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"  Price range: ${data['price'].min():.2f} - ${data['price'].max():.2f}")
    print(f"  Total return: {((data['price'].iloc[-1] / data['price'].iloc[0]) - 1) * 100:.2f}%")
    
    return data


def run_backtest_on_real_data(symbol: str, data: pd.DataFrame) -> Dict:
    """Run trading strategy on real market data"""
    print(f"\n🤖 Running trading strategy on real {symbol} data...")
    
    # Generate market states from real data
    sim = DigitalTwin(data)
    real_states = sim.generate_from_real_data(symbol, days=len(data), data_df=data)
    
    if not real_states:
        print("❌ Failed to generate market states")
        return None
    
    print(f"✓ Generated {len(real_states)} market states")
    
    # Initialize agents and portfolio
    agents = [Berserker(), NLPExplorer(), QuantExplorer(), Sentinel(), Anchor(), CapitalManager()]
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)
    starting_capital = portfolio.cash
    
    # Run trading on real data
    trade_pnls = []
    
    for i, state in enumerate(real_states):
        # Update market state in protocol
        protocol.update(state)
        
        # Agents observe and decide
        for agent in agents:
            agent.update(state)
            intents = agent.decide(state)
            
            # Scout agents (Tactician, Explorer) may be filtered by protocol
            if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                intents = [i for i in intents if protocol.should_allow_scout(i.confidence, random.random())]
            
            # Register intents with blackboard
            for intent in intents:
                if agent.name == "The Anchor" and intent.side == "BUY":
                    blackboard.lock_long_term(intent.symbol)
                
                try:
                    blackboard.register_model_intent(intent)
                except Exception as e:
                    pass  # Silently skip blocked intents
                
                # Execute on agent's virtual portfolio for parameter adaptation
                agent.execute_virtual_intent(intent, state.price)
        
        # Resolve intents to orders
        orders = blackboard.resolve()
        
        # Execute orders
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
            # Track trade if it realized PnL (i.e., a sell or cover)
            if order.side in ("SELL", "COVER"):
                # Get the last trade from history
                if portfolio.trade_history:
                    last_trade = portfolio.trade_history[-1]
                    if 'trade_pnl' in last_trade:
                        trade_pnls.append(last_trade['trade_pnl'])
    
    # Close all remaining positions at final price
    final_price = real_states[-1].price
    if real_states:
        for symbol_pos in list(portfolio.positions.keys()):
            pos = portfolio.positions[symbol_pos]
            if pos.quantity > 0:
                portfolio.execute(symbol_pos, "SELL", pos.quantity, final_price)
            elif pos.quantity < 0:
                portfolio.execute(symbol_pos, "COVER", -pos.quantity, final_price)
    
    # Settle any option positions
    portfolio.settle_options(final_price)
    
    # Close out virtual agent portfolios to finalize adaptation
    for agent in agents:
        agent.close_all_virtual(final_price, symbol)
    
    # Calculate final NAV
    final_nav = portfolio.cash
    for pos in portfolio.positions.values():
        if pos.quantity > 0:
            final_nav += pos.quantity * final_price
        else:
            final_nav -= (-pos.quantity) * final_price
    
    # Calculate metrics
    winning_trades = sum(1 for pnl in trade_pnls if pnl > 0)
    total_trades = len(trade_pnls)
    
    return {
        'symbol': symbol,
        'data_points': len(real_states),
        'start_price': real_states[0].price if real_states else 0,
        'end_price': real_states[-1].price if real_states else 0,
        'market_return': ((real_states[-1].price / real_states[0].price) - 1) * 100 if real_states else 0,
        'trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'realized_pnl': portfolio.realized_pnl,
        'unrealized_pnl': 0.0,  # Already closed all positions
        'total_pnl': portfolio.realized_pnl,
        'starting_capital': starting_capital,
        'final_nav': final_nav,
        'total_return': ((final_nav / starting_capital) - 1) * 100,
        'agents_count': len(agents),
    }


def run_shadow_trading_comparison() -> Dict:
    """Run shadow trading across different scenarios for comparison"""
    print(f"\n📈 Running shadow trading comparison across scenarios...")
    
    trader = ShadowTrader()
    scenarios = ['bull', 'bear', 'chop']
    results = {}
    
    for scenario in scenarios:
        print(f"  Testing {scenario} scenario...", end=" ")
        try:
            result = trader.test_scenario(scenario, days=30)
            if result:
                results[scenario] = result
                print(f"✓ PnL: ${result.get('pnl', 0):.2f}")
            else:
                print("⚠️ No result")
        except Exception as e:
            print(f"⚠️ Error: {e}")
    
    return results


def print_report(real_data_result: Dict, learner_state: Dict):
    """Print a comprehensive performance report"""
    
    print("\n" + "="*80)
    print("📋 MARKETPREDICTOR - LAST MONTH BACKTEST REPORT")
    print("="*80)
    
    if real_data_result:
        print(f"\n🎯 REAL MARKET DATA PERFORMANCE ({real_data_result['symbol']})")
        print("-" * 80)
        print(f"  Period:              {real_data_result['data_points']} trading days")
        print(f"  Start Price:         ${real_data_result['start_price']:.2f}")
        print(f"  End Price:           ${real_data_result['end_price']:.2f}")
        print(f"  Market Return:       {real_data_result['market_return']:+.2f}%")
        print(f"")
        print(f"  Your Strategy:")
        print(f"    Starting Capital:  ${real_data_result['starting_capital']:,.2f}")
        print(f"    Final NAV:         ${real_data_result['final_nav']:,.2f}")
        print(f"    Total Return:      {real_data_result['total_return']:+.2f}%")
        print(f"    Realized PnL:      ${real_data_result['realized_pnl']:+,.2f}")
        print(f"    Unrealized PnL:    ${real_data_result['unrealized_pnl']:+,.2f}")
        print(f"")
        print(f"  Trading Activity:")
        print(f"    Total Trades:      {real_data_result['trades']}")
        print(f"    Winning Trades:    {real_data_result['winning_trades']}")
        print(f"    Win Rate:          {real_data_result['win_rate']:.1f}%")
        print(f"    Agents Active:     {real_data_result['agents_count']}")
        
        # Calculate alpha (strategy return vs market return)
        alpha = real_data_result['total_return'] - real_data_result['market_return']
        if alpha > 0:
            print(f"\n  ✅ ALPHA (Excess Return): {alpha:+.2f}%")
        else:
            print(f"\n  ⚠️  ALPHA (Excess Return): {alpha:+.2f}%")
    
    print(f"\n📚 LEARNED PARAMETERS (from previous runs)")
    print("-" * 80)
    
    if learner_state and "history" in learner_state and len(learner_state["history"]) > 0:
        # Show last 5 learned configurations
        recent = learner_state["history"][-5:]
        
        print(f"  Recent Learning History ({len(recent)} entries):")
        for i, entry in enumerate(recent, 1):
            scenario = entry.get('scenario', 'unknown')
            params = entry.get('params', {})
            mse = entry.get('mse', 0)
            price = entry.get('final_price', 0)
            
            print(f"\n    Entry {i}: {scenario.upper()}")
            print(f"      Jump Frequency (λ):     {params.get('lamb', 0):.4f}")
            print(f"      Jump Direction (μⱼ):    {params.get('mu_j', 0):+.4f}")
            print(f"      Jump Volatility (σⱼ):   {params.get('sigma_j', 0):.4f}")
            print(f"      MSE:                    {mse:.6f}")
            print(f"      Final Price:            ${price:.2f}")
    else:
        print("  ⚠️  No learning history found")
    
    print("\n" + "="*80)


def main():
    print("\n" + "="*80)
    print("🚀 MARKETPREDICTOR - LAST MONTH PERFORMANCE CHECKER")
    print("="*80)
    
    # Load previous learner state
    learner_state = load_learner_state('SPY')
    
    # Fetch real data for last month
    real_data = fetch_last_month_data('SPY')
    if real_data is None:
        print("\n❌ Cannot proceed without real data")
        return
    
    # Run backtest on real data
    real_result = run_backtest_on_real_data('SPY', real_data)
    
    # Print comprehensive report
    print_report(real_result, learner_state)
    
    print("\n💡 INTERPRETATION GUIDE:")
    print("-" * 80)
    print("  ALPHA > 0:   Strategy outperformed the market ✅")
    print("  ALPHA < 0:   Strategy underperformed the market ⚠️")
    print("  Win Rate:    % of trades that were profitable")
    print("  Total Return: Your portfolio's overall percentage gain/loss")
    print("  Market Return: SPY's percentage gain/loss for the period")
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
