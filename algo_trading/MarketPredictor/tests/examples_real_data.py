"""
Integration guide and usage patterns for real market data in MarketPredictor

This module demonstrates best practices for:
- Fetching and validating real market data
- Converting real data to MarketState objects
- Backtesting strategies on real data
- Comparing real vs simulated market scenarios
"""

import os
import sys
import io

# Force stdout/stderr to write UTF-8 to prevent Windows cp1252 encoding crashes on emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from src.learning_model.simulator import DigitalTwin

# ============================================================================
# SECTION 1: BASIC REAL DATA WORKFLOWS
# ============================================================================

def workflow_1_simple_fetch():
    """Workflow 1: The simplest way - fetch real data in 3 lines
    
    Perfect for: Quick testing, one-off backtests
    Time: ~2-3 seconds for 100 days of SPY
    """
    from src.learning_model.simulator import DigitalTwin

    # Fetch
    data = DigitalTwin.fetch_real_market_data('SPY', days=100)

    # Convert to market states
    sim = DigitalTwin(data)
    states = sim.generate_from_real_data('SPY', data_df=data)
    
    # Use
    for state in states[-5:]:  # Last 5 days
        print(f"{state.timestamp}: ${state.price:.2f} ({state.cycle_phase.name})")


def workflow_2_cached_data():
    """Workflow 2: Cache data locally to save API calls
    
    Perfect for: Repeated testing, CI/CD pipelines
    Time: Instant on subsequent runs
    """
    from src.learning_model.simulator import DigitalTwin
    import os
    
    symbol = 'AAPL'
    cache_path = f'/tmp/{symbol}_historical.csv'
    
    # Try to load from cache
    if os.path.exists(cache_path):
        print(f"Loading {symbol} from cache...")
        data = pd.read_csv(cache_path)
    else:
        print(f"Fetching {symbol} from Yahoo Finance...")
        data = DigitalTwin.fetch_real_market_data(symbol, days=252)
        data.to_csv(cache_path, index=False)
    
    # Use
    sim = DigitalTwin(data)
    states = sim.generate_from_real_data(symbol, data_df=data)
    return states


def workflow_3_multiple_symbols():
    """Workflow 3: Fetch data for multiple symbols efficiently
    
    Perfect for: Portfolio testing, correlation analysis
    Time: ~2 seconds for 3 symbols
    """
    from src.learning_model.simulator import DigitalTwin

    symbols = ['SPY', 'QQQ', 'TLT']  # S&P 500, Tech, Bonds
    days = 100
    
    data_dict = {}
    states_dict = {}
    
    for symbol in symbols:
        print(f"Fetching {symbol}...")
        data = DigitalTwin.fetch_real_market_data(symbol, days=days)
        if data is not None:
            data_dict[symbol] = data
            
            sim = DigitalTwin(data)
            states_dict[symbol] = sim.generate_from_real_data(symbol, data_df=data)
    
    return data_dict, states_dict


# ============================================================================
# SECTION 2: BACKTESTING ON REAL DATA
# ============================================================================

def backtest_single_strategy(symbol: str, days: int = 100):
    """Backtest a single strategy on real market data
    
    Returns: Dict with performance metrics
    """
    from src.learning_model.simulator import DigitalTwin
    from src.learning_model.learning import ShadowTrader
    
    # Load real data
    print(f"\n[Backtest] {symbol} - {days} days")
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if data is None:
        print(f"[ERROR] Could not fetch data for {symbol}")
        return None
    sim = DigitalTwin(data)
    real_states = sim.generate_from_real_data(symbol, days=days, data_df=data)
    
    if not real_states:
        print(f"[ERROR] Could not load data for {symbol}")
        return None
    
    # Initialize strategy
    trader = ShadowTrader()
    
    # Run shadow trading scenario on the states
    result = trader.run_shadow_scenario(real_states, scenario_name=symbol)
    
    # Calculate metrics from price data
    prices = [s.price for s in real_states]
    prices_arr = np.array(prices)
    returns = np.diff(prices_arr) / prices_arr[:-1]
    
    total_return = (prices[-1] - prices[0]) / prices[0]
    max_price = max(prices)
    max_drawdown = min((p - max_price) / max_price for p in prices)
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    # Extract P&L from result
    strategy_pnl = result.get('realized_pnl', 0)
    
    results = {
        'symbol': symbol,
        'days': len(real_states),
        'start_price': prices[0],
        'end_price': prices[-1],
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe,
        'pnl': strategy_pnl,
        'scenario_result': result,
        'prices': prices,
    }
    
    return results


def backtest_ensemble(symbol: str, days: int = 100):
    """Backtest strategy on ensemble of real + simulated scenarios
    
    Returns: Dict comparing all scenarios
    """
    from src.learning_model.simulator import DigitalTwin
    
    print(f"\n[Ensemble Backtest] {symbol} - {days} days")
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if data is None:
        print(f"Could not fetch {symbol}")
        return None
    sim = DigitalTwin(data)
    
    # Real baseline
    print("  Loading real data...")
    real_results = backtest_single_strategy(symbol, days=days)
    
    # Simulated scenarios
    results = {'real': real_results}
    
    for scenario in ['bull', 'bear', 'chop', 'flash_crash']:
        print(f"  Testing {scenario} scenario...")
        sim_states = sim.generate(symbol, days=days, scenario=scenario)
        
        # Quick P&L calculation on simulated
        prices = [s.price for s in sim_states]
        sim_return = (prices[-1] - prices[0]) / prices[0]
        
        results[scenario] = {
            'total_return': sim_return,
            'scenario': scenario,
        }
    
    return results


# ============================================================================
# SECTION 3: REAL VS SIMULATED COMPARISON
# ============================================================================

def compare_distributions(symbol: str, days: int = 100):
    """Compare real market distribution vs simulated scenarios
    
    Returns: Dict with statistical comparisons
    """
    from src.learning_model.simulator import DigitalTwin

    # Get real data
    print(f"\n[Comparison] {symbol} - {days} days")
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if data is None:
        print(f"Could not fetch {symbol}")
        return None
    
    sim = DigitalTwin(data)
    
    real_states = sim.generate_from_real_data(symbol, days=days, data_df=data)
    if not real_states:
        return None
    
    real_prices = np.array([s.price for s in real_states])
    real_returns = np.diff(real_prices) / real_prices[:-1]
    
    comparison = {
        'symbol': symbol,
        'real': {
            'mean_return': np.mean(real_returns),
            'volatility': np.std(real_returns),
            'skewness': np.mean(((real_returns - np.mean(real_returns)) / np.std(real_returns)) ** 3),
            'max_return': np.max(real_returns),
            'min_return': np.min(real_returns),
        }
    }
    
    # Compare with scenarios
    for scenario in ['bull', 'bear', 'chop']:
        sim_states = sim.generate(symbol, days=days, scenario=scenario)
        sim_prices = np.array([s.price for s in sim_states])
        sim_returns = np.diff(sim_prices) / sim_prices[:-1]
        
        comparison[scenario] = {
            'mean_return': np.mean(sim_returns),
            'volatility': np.std(sim_returns),
            'skewness': np.mean(((sim_returns - np.mean(sim_returns)) / np.std(sim_returns)) ** 3),
            'max_return': np.max(sim_returns),
            'min_return': np.min(sim_returns),
        }
    
    return comparison


def validate_learner_calibration(symbol: str, days: int = 100):
    """Validate that learner properly calibrates parameters from real data
    
    The learner updates its GJR-GARCH parameters after processing real data
    """
    from src.learning_model.simulator import DigitalTwin
    
    print(f"\n[Learner Calibration] {symbol} - {days} days")
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if data is None:
        print(f"Could not fetch {symbol}")
        return
    
    sim = DigitalTwin(data)
    
    # Initial parameters
    print("  Initial learner state:")
    print(f"    Lambda (mean reversion): {sim.learner.lamb:.4f}")
    print(f"    Mu jump (drift): {sim.learner.mu_j:.6f}")
    print(f"    Sigma jump: {sim.learner.sigma_j:.6f}")
    
    # Process real data
    real_states = sim.generate_from_real_data(symbol, days=days, data_df=data)
    
    # Updated parameters
    print("  After processing real data:")
    print(f"    Lambda: {sim.learner.lamb:.4f}")
    print(f"    Mu jump: {sim.learner.mu_j:.6f}")
    print(f"    Sigma jump: {sim.learner.sigma_j:.6f}")
    
    return sim.learner


# ============================================================================
# SECTION 4: DATA VALIDATION AND QUALITY CHECKS
# ============================================================================

def validate_real_data(symbol: str, days: int = 100) -> Tuple[bool, str]:
    """Validate quality of fetched real market data
    
    Returns: (is_valid, message)
    """
    from src.learning_model.simulator import DigitalTwin
    
    data = DigitalTwin.fetch_real_market_data(symbol, days=days)
    if data is None:
        return False, f"Could not fetch data for {symbol}"
    
    # Check completeness
    if len(data) < days * 0.8:  # Allow 20% gaps
        return False, f"Only got {len(data)}/{days} days"
    
    # Check for NaN
    if data[['price', 'volatility', 'returns']].isna().any().any():
        return False, "Data contains NaN values"
    
    # Check price range
    if (data['price'] <= 0).any():
        return False, f"Invalid prices: {data[data['price'] <= 0]}"
    
    # Check volatility range
    if (data['volatility'] < 0.001).any():
        return False, f"Volatility too low: {data['volatility'].min()}"
    
    if (data['volatility'] > 1.0).any():
        return False, f"Volatility too high: {data['volatility'].max()}"
    
    return True, f"Valid data: {len(data)} days, price ${data['price'].min():.2f}-${data['price'].max():.2f}"


def data_quality_report(symbols: List[str], days: int = 100):
    """Generate quality report for multiple symbols"""
    print(f"\n[Data Quality Report] - {days} days per symbol")
    print("-" * 70)
    
    for symbol in symbols:
        is_valid, message = validate_real_data(symbol, days=days)
        status = "✓" if is_valid else "✗"
        print(f"{status:2} {symbol:8} {message}")


# ============================================================================
# SECTION 5: PRODUCTION PATTERNS
# ============================================================================

class RealDataBacktester:
    """Production-ready backtester for real market data
    
    Usage:
        backtester = RealDataBacktester()
        results = backtester.backtest('SPY', days=252, strategy='shadow')
    """
    
    def __init__(self, cache_dir: str = '/tmp/market_cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def backtest(self, symbol: str, days: int = 100, strategy: str = 'shadow'):
        """Run backtest on real data with caching"""
        # Get data (from cache or fetch)
        data = self._get_data(symbol, days)
        if data is None:
            raise ValueError(f"Could not get data for {symbol}")
        
        # Convert to states
        from src.learning_model.simulator import DigitalTwin
        sim = DigitalTwin(data)
        states = sim.generate_from_real_data(symbol, data_df=data)
        
        # Run strategy
        results = backtest_single_strategy(symbol, days)
        
        return results
    
    def _get_data(self, symbol: str, days: int):
        """Get data from cache or fetch"""
        from src.learning_model.simulator import DigitalTwin
        
        cache_file = f"{self.cache_dir}/{symbol}_{days}d.csv"
        
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file)
        
        data = DigitalTwin.fetch_real_market_data(symbol, days=days)
        if data is not None:
            data.to_csv(cache_file, index=False)
        
        return data


# ============================================================================
# MAIN: Run Examples
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("MarketPredictor - Real Data Integration Workflows")
    print("="*70)
    
    try:
        # Example 1: Simple fetch
        print("\n[Example 1] Simple Fetch")
        workflow_1_simple_fetch()
        
        # Example 2: Data comparison
        print("\n[Example 2] Real vs Simulated Comparison")
        comp = compare_distributions('SPY', days=60)
        if comp:
            print(f"  Real volatility: {comp['real']['volatility']*100:.2f}%")
            print(f"  Bear scenario volatility: {comp['bear']['volatility']*100:.2f}%")
        
        # Example 3: Data quality
        print("\n[Example 3] Data Quality Report")
        data_quality_report(['SPY', 'AAPL', 'QQQ'], days=100)
        
        # Example 4: Backtesting (if you want to test a strategy)
        # results = backtest_single_strategy('SPY', days=60)
        # if results:
        #     print(f"\n  Return: {results['total_return']*100:+.2f}%")
        #     print(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        
        print("\n" + "="*70)
        print("Examples completed successfully!")
        print("="*70)
        
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("Install with: pip install yfinance pandas numpy")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
