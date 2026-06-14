#!/usr/bin/env python3
"""
Test real market data integration with MarketPredictor

This script demonstrates:
1. Fetching real market data from Yahoo Finance
2. Generating market states from real data
3. Comparing real vs simulated market dynamics
4. Testing shadow trading strategies on real data
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project to path
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.learning_model.simulator import DigitalTwin
from src.core_engine.market_state import MarketState, CyclePhase
from src.learning_model.learning import ShadowTrader


def test_fetch_real_data():
    """Test 1: Fetch real market data for multiple symbols"""
    print("\n" + "="*70)
    print("TEST 1: Fetch Real Market Data")
    print("="*70)
    
    symbols = ['SPY', 'AAPL', 'QQQ']
    
    for symbol in symbols:
        print(f"\n[Fetching] {symbol}...")
        data = DigitalTwin.fetch_real_market_data(symbol, days=100)
        
        if data is not None:
            print(f"  ✓ Got {len(data)} days of data")
            print(f"    Price range: ${data['price'].min():.2f} - ${data['price'].max():.2f}")
            print(f"    Avg return: {data['returns'].mean()*100:.3f}%")
            print(f"    Volatility: {data['volatility'].mean()*100:.2f}%")
            print(f"    Latest price: ${data['price'].iloc[-1]:.2f}")
        else:
            print(f"  ✗ Failed to fetch {symbol}")


def test_real_vs_simulated():
    """Test 2: Compare real market data with simulated data"""
    print("\n" + "="*70)
    print("TEST 2: Real vs Simulated Market Dynamics")
    print("="*70)
    
    symbol = 'SPY'
    days = 60
    
    # Fetch real data
    print(f"\n[Loading real data] {symbol}...")
    real_data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if real_data is None:
        print("[SKIP] Could not fetch real data")
        return
    
    # Generate real market states
    sim = DigitalTwin(real_data)
    real_states = sim.generate_from_real_data(symbol, days=days, data_df=real_data)
    
    print(f"\n[Generating simulated data] {symbol}...")
    # Generate simulated scenarios
    sim_states = {
        'bull': sim.generate(symbol, days=days, scenario='bull'),
        'bear': sim.generate(symbol, days=days, scenario='bear'),
        'chop': sim.generate(symbol, days=days, scenario='chop'),
    }
    
    # Compare statistics
    print("\n[Comparison] Real vs Simulated Statistics:")
    print(f"{'Metric':<20} {'Real':<15} {'Bull Sim':<15} {'Bear Sim':<15} {'Chop Sim':<15}")
    print("-" * 80)
    
    real_prices = [s.price for s in real_states]
    real_returns = np.diff(real_prices) / np.array(real_prices[:-1])
    real_vol = np.std(real_returns)
    real_mean_return = np.mean(real_returns)
    
    for scenario_name, scenario_states in sim_states.items():
        sim_prices = [s.price for s in scenario_states]
        sim_returns = np.diff(sim_prices) / np.array(sim_prices[:-1])
        sim_vol = np.std(sim_returns)
        sim_mean_return = np.mean(sim_returns)
        
        print(f"{'Price Vol (daily)':<20} {real_vol*100:<14.2f}% {sim_vol*100:<14.2f}% " + 
              ("(Real)" if scenario_name == 'bull' else ""))
        print(f"{'Return Mean':<20} {real_mean_return*100:<14.3f}% {sim_mean_return*100:<14.3f}%")
    
    # Cycle phase distribution
    real_cycles = [s.cycle_phase for s in real_states]
    print(f"\n[Real data cycle distribution]")
    for phase in CyclePhase:
        count = real_cycles.count(phase)
        pct = count / len(real_cycles) * 100
        print(f"  {phase.name:<12}: {count:3d} days ({pct:5.1f}%)")


def test_backtesting_real_data():
    """Test 3: Run shadow trading strategy on real data"""
    print("\n" + "="*70)
    print("TEST 3: Shadow Trading on Real Market Data")
    print("="*70)
    
    symbol = 'SPY'
    days = 100
    
    # Load real data
    print(f"\n[Loading real data] {symbol} ({days} days)...")
    real_data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if real_data is None:
        print("[SKIP] Could not fetch real data")
        return
    
    # Generate real market states
    sim = DigitalTwin(real_data)
    real_states = sim.generate_from_real_data(symbol, days=days, data_df=real_data)
    
    print(f"[Trading] Running shadow trader on {len(real_states)} real market states...")
    
    # Initialize trader
    trader = ShadowTrader()
    
    # Run shadow trading scenario on real data
    result = trader.run_shadow_scenario(real_states, scenario_name="real_data")
    
    # Print results
    print(f"\n[Results]")
    print(f"  Initial price: ${real_states[0].price:.2f}")
    print(f"  Final price:   ${real_states[-1].price:.2f}")
    print(f"  Price change:  {(real_states[-1].price - real_states[0].price) / real_states[0].price * 100:+.2f}%")
    print(f"  Scenario: {result.get('scenario_name', 'real_data')}")
    if 'portfolio_nav' in result:
        print(f"  Final NAV: ${result['portfolio_nav']:.2f}")
    if 'avg_pnl' in result:
        print(f"  Avg PnL: ${result['avg_pnl']:.2f}")


def test_ensemble_with_real_baseline():
    """Test 4: Generate ensemble scenarios using real data as baseline"""
    print("\n" + "="*70)
    print("TEST 4: Ensemble Generation with Real Baseline")
    print("="*70)
    
    symbol = 'QQQ'
    days = 50
    
    # Load real data as baseline
    print(f"\n[Loading real baseline] {symbol}...")
    real_data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    
    if real_data is None:
        print("[SKIP] Could not fetch real data")
        return
    
    sim = DigitalTwin(real_data)
    
    # Generate ensemble scenarios
    print(f"[Generating ensemble scenarios]...")
    ensemble = sim.generate_ensemble(symbol, days=days, n_scenarios=5)
    
    print(f"\n[Ensemble scenarios generated]:")
    for scenario_name, states in ensemble.items():
        prices = [s.price for s in states]
        returns = (prices[-1] - prices[0]) / prices[0] * 100
        volatility = np.std(np.diff(prices) / np.array(prices[:-1])) * 100
        print(f"  {scenario_name:<15}: {returns:+6.2f}% return, {volatility:5.2f}% vol")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("MarketPredictor - Real Data Integration Test Suite")
    print("="*70)
    
    try:
        # Test 1: Fetch real data
        test_fetch_real_data()
        
        # Test 2: Compare real vs simulated
        test_real_vs_simulated()
        
        # Test 3: Backtest on real data
        test_backtesting_real_data()
        
        # Test 4: Ensemble with real baseline
        test_ensemble_with_real_baseline()
        
        print("\n" + "="*70)
        print("All tests completed!")
        print("="*70)
        
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("\nTo use real market data, install yfinance:")
        print("  pip install yfinance")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
