#!/usr/bin/env python3
"""
Advanced Backtest: Test MarketPredictor performance over configurable timespans (up to 5 years).

Usage:
    python backtest.py 30                   # Last 30 days
    python backtest.py 90                   # Last 90 days (3 months)
    python backtest.py 252                  # Last year (252 trading days)
    python backtest.py 1260                 # Last 5 years (5 * 252 days)
    python backtest.py --days 30            # Explicit: last 30 days
    python backtest.py --symbol AAPL 90    # Last 90 days of AAPL
    python backtest.py --symbol QQQ 252    # Last year of QQQ

This script:
1. Fetches real historical market data for the specified timespan
2. Generates trading strategy decisions at the start of the period
3. Simulates portfolio execution through the entire timespan
4. Compares projections to actual outcomes
5. Reports detailed performance metrics including accuracy, drawdown, Sharpe ratio
"""

import sys
import io

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import random
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.heuristic.marketstate import MarketState
from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from strategies.heuristic.agents import Berserker, Sentinel, Anchor, CapitalManager
from strategies.explorer.nlp_model import NLPExplorer
from strategies.explorer.company_evaluator import QuantExplorer
from simulator.simulator import DigitalTwin
from simulator.learning import ShadowTrader
from simulator.state_persistence import StateManager
from core.execution import Portfolio


def parse_arguments():
    """Parse command-line arguments for flexible timespan specification."""
    parser = argparse.ArgumentParser(
        description='Backtest MarketPredictor over configurable timespans (up to 5 years)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backtest.py 30                    # Last 30 days
  python backtest.py 90                    # Last 90 days
  python backtest.py 252                   # Last trading year
  python backtest.py 1260                  # Last 5 trading years
  python backtest.py --symbol AAPL 252    # Last year of AAPL
  python backtest.py --symbol QQQ 1260    # Last 5 years of QQQ
  python backtest.py --days 180            # Last 180 days
        """
    )
    
    parser.add_argument('days', nargs='?', type=int, default=252, 
                        help='Number of days to backtest (default: 252 = 1 trading year)')
    parser.add_argument('--days', dest='days_explicit', type=int,
                        help='Alternative way to specify days')
    parser.add_argument('--symbol', type=str, default='SPY',
                        help='Stock symbol to backtest (default: SPY)')
    parser.add_argument('--max-days', type=int, default=1260,
                        help='Maximum allowed days (default: 1260 = 5 years)')
    parser.add_argument('--agent', type=str, default='all',
                        choices=['all', 'tactician', 'berserker', 'explorer', 'sentinel', 'anchor', 'treasurer', 'metaopt'],
                        help='Specific agent to backtest (default: all)')
    
    args = parser.parse_args()
    
    # Use explicit --days if provided, otherwise use positional days
    if args.days_explicit:
        args.days = args.days_explicit
    
    # Validate timespan
    if args.days <= 0:
        print(f"❌ Days must be positive, got {args.days}")
        sys.exit(1)
    
    if args.days > args.max_days:
        print(f"❌ Requested {args.days} days exceeds max {args.max_days} days (5 years)")
        sys.exit(1)
    
    return args


def load_learner_state(symbol: str = 'SPY') -> Dict:
    """Load the saved learner state from previous runs."""
    try:
        state_manager = StateManager(backend='postgres')
        state = state_manager.load_learner_state(symbol)
        if state:
            return state
        return {"history": []}
    except Exception:
        return {"history": []}


def fetch_historical_data(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Fetch historical market data for the specified timespan."""
    print(f"\n📊 Fetching {days} days of {symbol} historical data from Yahoo Finance...")
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if data is None or len(data) == 0:
        print("❌ Failed to fetch real data")
        return None
    
    print(f"✓ Got {len(data)} trading days of data")
    print(f"  Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"  Price range: ${data['price'].min():.2f} - ${data['price'].max():.2f}")
    
    # Calculate statistics
    returns = data['returns'].fillna(0)
    total_return = ((data['price'].iloc[-1] / data['price'].iloc[0]) - 1) * 100
    max_drawdown = calculate_drawdown(data['price'].values)
    volatility = data['volatility'].mean() * 100
    
    print(f"  Total return: {total_return:+.2f}%")
    print(f"  Max drawdown: {max_drawdown:-.2f}%")
    print(f"  Avg volatility: {volatility:.2f}%")
    
    return data


def calculate_drawdown(prices: np.ndarray) -> float:
    """Calculate maximum drawdown from a price series."""
    cummax = np.maximum.accumulate(prices)
    drawdown = (prices - cummax) / cummax
    return drawdown.min() * 100


def run_backtest_on_historical_data(symbol: str, data: pd.DataFrame, agent_name: str = 'all') -> Dict:
    """Run trading strategy on historical market data."""
    print(f"\n🤖 Running trading strategy on {symbol} historical data ({len(data)} days) using agent: {agent_name}...")
    
    # Generate market states from real data
    sim = DigitalTwin(data)
    real_states = sim.generate_from_real_data(symbol, days=len(data), data_df=data)
    
    if not real_states:
        print("❌ Failed to generate market states")
        return None
    
    print(f"✓ Generated {len(real_states)} market states")
    
    # Initialize agents and portfolio
    agent_map = {
        'tactician': Berserker,
        'berserker': Berserker,
        'nlpexplorer': NLPExplorer,
        'quantexplorer': QuantExplorer,
        'sentinel': Sentinel,
        'anchor': Anchor,
        'capitalmanager': CapitalManager
    }
    
    if agent_name.lower() == 'all':
        agents = [Berserker(), NLPExplorer(), QuantExplorer(), Sentinel(), Anchor(), CapitalManager()]
    elif agent_name.lower() == 'explorer':
        agents = [NLPExplorer(), QuantExplorer()]
    elif agent_name.lower() == 'treasurer' or agent_name.lower() == 'metaopt':
        agents = [CapitalManager()]
    else:
        agents = [agent_map[agent_name.lower()]()]
    blackboard = Blackboard()
    protocol = SyntheticHedgeProtocol(blackboard)
    portfolio = Portfolio(cash=1_000_000.0)
    starting_capital = portfolio.cash
    
    # Track all trades for analysis
    trade_pnls = []
    daily_navs = []
    
    # Run trading on historical data
    for i, state in enumerate(real_states):
        # Update market state in protocol
        protocol.update(state)
        
        # Agents observe and decide
        for agent in agents:
            agent.update(state)
            intents = agent.decide(state)
            
            # Scout agents (Berserker, Explorers) may be filtered
            if agent.name in ("The Berserker", "The NLP Explorer", "The Quant Explorer") and len(intents) > 0:
                intents = [intent for intent in intents if protocol.should_allow_scout(intent.confidence, random.random())]
            
            # Register intents with blackboard
            for intent in intents:
                if agent.name == "The Anchor" and intent.side == "BUY":
                    blackboard.lock_long_term(intent.symbol)
                
                try:
                    blackboard.register_model_intent(intent)
                except Exception:
                    pass  # Silently skip blocked intents
                
                # Execute on agent's virtual portfolio for parameter adaptation
                agent.execute_virtual_intent(intent, state.price)
        
        # Resolve intents to orders
        orders = blackboard.resolve()
        
        # Execute orders
        for order in orders:
            portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
            # Track realized PnL from trades
            if portfolio.trade_history:
                last_trade = portfolio.trade_history[-1]
                if 'trade_pnl' in last_trade and last_trade['trade_pnl'] != 0:
                    trade_pnls.append(last_trade['trade_pnl'])
        
        # Track daily NAV
        current_nav = portfolio.cash
        for pos in portfolio.positions.values():
            if pos.quantity > 0:
                current_nav += pos.quantity * state.price
            else:
                current_nav -= (-pos.quantity) * state.price
        daily_navs.append(current_nav)
    
    # Close all remaining positions at final price
    final_price = real_states[-1].price if real_states else 0
    if real_states:
        for sym_pos in list(portfolio.positions.keys()):
            pos = portfolio.positions[sym_pos]
            if pos.quantity > 0:
                portfolio.execute(sym_pos, "SELL", pos.quantity, final_price)
            elif pos.quantity < 0:
                portfolio.execute(sym_pos, "COVER", -pos.quantity, final_price)
    
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
    
    # Calculate comprehensive metrics
    total_trades = len(trade_pnls)
    winning_trades = sum(1 for pnl in trade_pnls if pnl > 0)
    
    # Calculate Sharpe ratio (annualized, assuming 252 trading days)
    nav_array = np.array(daily_navs)
    nav_returns = np.diff(nav_array) / nav_array[:-1]
    sharpe_ratio = 0.0
    if len(nav_returns) > 0 and nav_returns.std() > 0:
        annual_return = ((final_nav / starting_capital) - 1) * (252 / len(real_states))
        annual_vol = nav_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0
    
    # Calculate max drawdown
    nav_prices = np.array(daily_navs + [final_nav])
    max_dd = calculate_drawdown(nav_prices)
    
    return {
        'symbol': symbol,
        'data_points': len(real_states),
        'start_price': real_states[0].price if real_states else 0,
        'end_price': real_states[-1].price if real_states else 0,
        'market_return': ((real_states[-1].price / real_states[0].price) - 1) * 100 if real_states else 0,
        'trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        'avg_trade_pnl': np.mean(trade_pnls) if trade_pnls else 0,
        'realized_pnl': portfolio.realized_pnl,
        'starting_capital': starting_capital,
        'final_nav': final_nav,
        'total_return': ((final_nav / starting_capital) - 1) * 100,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe_ratio,
        'agents_count': len(agents),
        'timespan_days': len(real_states),
    }


def print_report(result: Dict, learner_state: Dict, args):
    """Print comprehensive backtest report."""
    
    # Calculate timespan description
    days = result['timespan_days']
    years = days / 252
    if years >= 1:
        timespan_desc = f"{years:.1f} years ({days} days)"
    else:
        months = days / 21
        timespan_desc = f"{months:.1f} months ({days} days)"
    
    print("\n" + "="*90)
    print(f"📋 MARKETPREDICTOR BACKTEST REPORT - {result['symbol']}")
    print("="*90)
    
    print(f"\n⏱️  TIMESPAN: {timespan_desc}")
    print(f"   Period: Real historical data from {days} days ago to today")
    print("-"*90)
    
    if result:
        print(f"\n🎯 MARKET PERFORMANCE ({result['symbol']})")
        print("-"*90)
        print(f"  Start Price:         ${result['start_price']:.2f}")
        print(f"  End Price:           ${result['end_price']:.2f}")
        print(f"  Market Return:       {result['market_return']:+.2f}%")
        
        print(f"\n💰 STRATEGY PERFORMANCE")
        print("-"*90)
        print(f"  Starting Capital:    ${result['starting_capital']:,.2f}")
        print(f"  Final NAV:           ${result['final_nav']:,.2f}")
        print(f"  Total Return:        {result['total_return']:+.2f}%")
        print(f"  Realized PnL:        ${result['realized_pnl']:+,.2f}")
        
        print(f"\n📊 RISK METRICS")
        print("-"*90)
        print(f"  Max Drawdown:        {result['max_drawdown']:-.2f}%")
        print(f"  Sharpe Ratio:        {result['sharpe_ratio']:.3f}")
        
        print(f"\n🎲 TRADING ACTIVITY")
        print("-"*90)
        print(f"  Total Trades:        {result['trades']}")
        print(f"  Winning Trades:      {result['winning_trades']}")
        print(f"  Win Rate:            {result['win_rate']:.1f}%")
        print(f"  Avg Trade PnL:       ${result['avg_trade_pnl']:+,.2f}")
        
        # Calculate alpha
        alpha = result['total_return'] - result['market_return']
        alpha_symbol = "✅" if alpha > 0 else "⚠️"
        print(f"\n{alpha_symbol} ALPHA (Excess Return): {alpha:+.2f}%")
        
        # Performance interpretation
        print(f"\n📈 INTERPRETATION")
        print("-"*90)
        if alpha > 0:
            print(f"  ✅ Strategy OUTPERFORMED market by {abs(alpha):.2f}%")
        else:
            print(f"  ⚠️  Strategy UNDERPERFORMED market by {abs(alpha):.2f}%")
        
        if result['sharpe_ratio'] > 1.0:
            print(f"  ✅ Risk-adjusted return (Sharpe) is excellent ({result['sharpe_ratio']:.3f})")
        elif result['sharpe_ratio'] > 0:
            print(f"  ⚠️  Risk-adjusted return (Sharpe) is moderate ({result['sharpe_ratio']:.3f})")
        else:
            print(f"  ❌ Risk-adjusted return (Sharpe) is poor ({result['sharpe_ratio']:.3f})")
        
        if result['max_drawdown'] < -20:
            print(f"  ⚠️  Large drawdown experienced ({result['max_drawdown']:.2f}%)")
        else:
            print(f"  ✅ Drawdown contained ({result['max_drawdown']:.2f}%)")


def main():
    """Main execution function."""
    args = parse_arguments()
    
    print("\n" + "="*90)
    print("🚀 MARKETPREDICTOR - ADVANCED BACKTEST")
    print("="*90)
    
    # Load previous learner state
    learner_state = load_learner_state(args.symbol)
    
    # Fetch historical data
    real_data = fetch_historical_data(args.symbol, args.days)
    if real_data is None:
        print("\n❌ Cannot proceed without historical data")
        return
    
    # Run backtest on historical data
    result = run_backtest_on_historical_data(args.symbol, real_data, args.agent)
    
    # Print comprehensive report
    print_report(result, learner_state, args)
    
    print("\n" + "="*90)
    print("💡 REFERENCE: METRICS EXPLAINED")
    print("="*90)
    print("""
  TOTAL RETURN:     Your portfolio's percentage gain/loss
  MARKET RETURN:    The underlying asset's percentage gain/loss
  ALPHA:            Excess return (strategy vs market) - higher is better
  MAX DRAWDOWN:     Largest peak-to-trough decline - lower (closer to 0) is better
  SHARPE RATIO:     Risk-adjusted return - higher is better (>1.0 is good)
  WIN RATE:         Percentage of trades that were profitable
    """)
    print("="*90 + "\n")


if __name__ == '__main__':
    main()
