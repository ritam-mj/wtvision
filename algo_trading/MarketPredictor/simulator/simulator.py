from __future__ import annotations
import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from strategies.heuristic.marketstate import MarketState, CyclePhase
from simulator.state_persistence import StateManager


class SimulatorLearner:
    def __init__(self):
        self.history: List[Dict] = []  # [(scenario, params, mse, final_price), ...]
        self.best_params = {}

    def record_outcome(self, scenario: str, params: Dict, mse: float, final_price: float):
        self.history.append({
            "scenario": scenario,
            "params": params.copy(),
            "mse": mse,
            "final_price": final_price,
        })

    def best_for_scenario(self, scenario: str) -> Dict:
        """Return best params found for a scenario."""
        matches = [h for h in self.history if h["scenario"] == scenario]
        if not matches:
            return {}
        best = min(matches, key=lambda x: x["mse"])
        return best["params"]

    def adaptive_params(self, scenario: str, base_params: Dict) -> Dict:
        """Suggest adapted params based on learning history."""
        best = self.best_for_scenario(scenario)
        if not best:
            return base_params.copy()
        # Blend best learned + base by 30/70 to avoid overfit
        adapted = {}
        for key in base_params:
            if key in best:
                adapted[key] = 0.3 * best[key] + 0.7 * base_params[key]
            else:
                adapted[key] = base_params[key]
        return adapted
    
    def report(self) -> str:
        """Generate summary of learner state."""
        lines = ["Learner State:"]
        lines.append(f"  Total outcomes recorded: {len(self.history)}")
        scenarios = set(h["scenario"] for h in self.history)
        lines.append(f"  Scenarios tracked: {len(scenarios)} ({', '.join(sorted(scenarios))})")
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Serialize learner state to dictionary for persistence."""
        return {
            "history": self.history,
            "best_params": self.best_params
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'SimulatorLearner':
        """Deserialize learner state from dictionary."""
        learner = SimulatorLearner()
        learner.history = data.get("history", [])
        learner.best_params = data.get("best_params", {})
        return learner


class DigitalTwin:
    
    def __init__(self, history: pd.DataFrame, symbol: str = None):
        self.history = history
        self.symbol = symbol if symbol else (history['symbol'].iloc[0] if history is not None and not history.empty and 'symbol' in history.columns else 'default')
        self.learner = self._load_or_create_learner()
    
    def _load_or_create_learner(self) -> SimulatorLearner:
        """Load learner state from database, or create fresh instance."""
        try:
            state_manager = StateManager(backend='postgres')
            data = state_manager.load_learner_state(self.symbol)
            if data:
                learner = SimulatorLearner.from_dict(data)
                print(f"[Loaded learner for {self.symbol} from DB: {len(learner.history)} outcomes recorded]")
                return learner
        except Exception as e:
            print(f"[Failed to load learner for {self.symbol} from DB: {e}; creating fresh]")
        return SimulatorLearner()
    
    def save_learner(self) -> None:
        """Persist learner state to database."""
        try:
            state_manager = StateManager(backend='postgres')
            state_manager.save_learner_state(self.symbol, self.learner.to_dict())
            print(f"[Saved learner state for {self.symbol} to DB: {len(self.learner.history)} outcomes]")
        except Exception as e:
            print(f"[Failed to save learner to DB: {e}]")

    @staticmethod
    def _simulate_jump_diffusion(s0: float, mu: float, sigma: float, lamb: float, mu_j: float, sigma_j: float, steps: int, dt: float):
        prices = np.zeros(steps)
        prices[0] = max(s0, 0.01)
        for t in range(1, steps):
            z = np.random.normal()
            jump = np.random.poisson(lamb * dt)
            y = np.random.normal(mu_j, sigma_j) if jump > 0 else 0.0
            new_price = prices[t - 1] * np.exp((mu - 0.5 * sigma * sigma) * dt + sigma * np.sqrt(dt) * z + y)
            if not np.isfinite(new_price) or new_price <= 0:
                new_price = max(prices[t - 1] * 0.995, 0.01)
            prices[t] = new_price
        return prices

    @staticmethod
    def _create_flash_crash_path(prices: np.ndarray, crash_day: int, crash_magnitude: float = 0.25, rebound_days: int = 10):
        if crash_day >= len(prices):
            return prices

        before = prices[:crash_day]
        crash_start = prices[crash_day - 1] if crash_day > 0 else prices[0]
        crash_val = crash_start * (1 - crash_magnitude)
        prices[crash_day] = crash_val

        for i in range(1, min(rebound_days, len(prices) - crash_day)):
            prices[crash_day + i] = crash_val + (crash_start - crash_val) * (i / rebound_days)

        for i in range(crash_day + rebound_days, len(prices)):
            drift = np.mean(np.diff(prices[:crash_day])) if crash_day > 1 else 0
            prices[i] = prices[i - 1] + drift

        return prices

    def generate(self, symbol: str, days: int = 252, scenario: str = "mixed", use_learning: bool = False) -> List[MarketState]:
        s0 = float(self.history.loc[self.history.symbol == symbol, "price"].iloc[-1])
        mu = self.history.loc[self.history.symbol == symbol, "returns"].mean()
        sigma = self.history.loc[self.history.symbol == symbol, "returns"].std()

        if scenario == "bear":
            mu = min(mu, -0.0005)
            sigma = max(sigma, 0.02)
            lamb, mu_j, sigma_j = 0.25, -0.03, 0.1
        elif scenario == "bull":
            mu = max(mu, 0.001)
            sigma = max(sigma, 0.013)
            lamb, mu_j, sigma_j = 0.05, 0.01, 0.02
        elif scenario == "chop":
            mu = 0.0
            sigma = max(sigma, 0.01)
            lamb, mu_j, sigma_j = 0.1, 0.0, 0.05
        else:
            lamb, mu_j, sigma_j = 0.12, -0.01, 0.06

        base_params = {"lamb": lamb, "mu_j": mu_j, "sigma_j": sigma_j}
        
        if use_learning:
            params = self.learner.adaptive_params(scenario, base_params)
            lamb, mu_j, sigma_j = params["lamb"], params["mu_j"], params["sigma_j"]

        prices = self._simulate_jump_diffusion(s0, mu, sigma, lamb, mu_j, sigma_j, days, 1 / 252)

        if scenario == "flash_crash":
            prices = self._create_flash_crash_path(prices, crash_day=int(days * 0.4), crash_magnitude=0.35, rebound_days=15)

        sigma_vol = max(sigma, 0.01)
        states: List[MarketState] = []
        for i, p in enumerate(prices):
            cycle = self._phase_from_price(p, s0)
            if scenario == "bear":
                cycle = CyclePhase.BEAR
            elif scenario == "bull":
                cycle = CyclePhase.BULL
            elif scenario == "chop":
                cycle = CyclePhase.CHOP

            vol = float(np.clip(abs(np.random.normal(sigma_vol * 2, sigma_vol * 0.5)), 0.01, 3.0))
            states.append(MarketState(symbol, float(p), vol, cycle, datetime.utcnow() + timedelta(days=i)))

        # Calculate MSE vs baseline for learning feedback
        baseline_prices = self._simulate_jump_diffusion(s0, mu, sigma, 0.1, -0.01, 0.06, days, 1 / 252)
        mse = ((prices - baseline_prices) ** 2).mean()
        self.learner.record_outcome(scenario, base_params, mse, prices[-1])

        return states

    def generate_ensemble(self, symbol: str, days: int = 252, n_scenarios: int = 5) -> Dict[str, List[MarketState]]:
        """Generate multiple scenarios for ensemble shadow trading."""
        scenarios = ["bull", "bear", "chop", "flash_crash", "mixed"]
        results = {}
        for i, scenario in enumerate(scenarios[:n_scenarios]):
            results[scenario] = self.generate(symbol, days=days, scenario=scenario, use_learning=(i > 0))
        return results
    
    @staticmethod
    def fetch_real_market_data(symbol: str, days: int = 100, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Fetch real market data from Upstox or Yahoo Finance.
        
        Args:
            symbol: Ticker symbol or instrument key
            days: Number of days of history to fetch
            end_date: End date (YYYY-MM-DD), default is today
        
        Returns:
            DataFrame with columns: [timestamp, symbol, price, returns, volatility]
            OR None if fetch fails
        """
        token = os.getenv("UPSTOX_ANALYTICS_TOKEN")
        if token:
            try:
                from core.utils.upstox_feeder import UpstoxFeeder
                feeder = UpstoxFeeder(analytics_token=token)
                # Upstox key format: e.g. NSE_EQ|INE002A01018. If it's a standard short ticker (e.g. Reliance), map/use it directly.
                df = feeder.fetch_historical_candles(instrument_key=symbol, days=days)
                if df is not None and not df.empty:
                    print(f"[Loaded Upstox Data] {symbol}: {len(df)} candles fetched.")
                    return df
            except Exception as e:
                print(f"[WARNING] Failed to fetch historical data from Upstox: {e}. Falling back to Yahoo Finance.")

        try:
            import yfinance as yf
        except ImportError:
            print("[WARNING] yfinance not installed. Run: pip install yfinance")
            return None
        
        try:
            # Calculate date range
            if end_date is None:
                end_date = datetime.utcnow().date()
            else:
                end_date = pd.to_datetime(end_date).date()
            
            start_date = end_date - timedelta(days=days + 50)  # Extra buffer for volatility
            
            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                print(f"[ERROR] Failed to fetch {symbol}: No data for this symbol/date range. Check symbol spelling and date validity.")
                return None
            
            # Use Adj Close if available, otherwise use Close
            if 'Adj Close' in df.columns:
                df['price'] = df['Adj Close'].astype(float)
            elif 'Close' in df.columns:
                df['price'] = df['Close'].astype(float)
            else:
                print(f"[ERROR] Failed to fetch {symbol}: No price column found. Available columns: {list(df.columns)}")
                return None
            df['returns'] = df['price'].pct_change()
            
            # Calculate rolling volatility (20-day)
            df['volatility'] = df['returns'].rolling(window=20).std()
            df['volatility'] = df['volatility'].bfill().fillna(0.01)
            
            # Keep last 'days' rows
            df = df.iloc[-days:].reset_index(drop=False)
            
            # Verify we have enough data
            if len(df) == 0:
                print(f"[ERROR] Failed to fetch {symbol}: No data after filtering for last {days} days")
                return None
            
            df['timestamp'] = df['Date']
            df['symbol'] = symbol
            
            # Select relevant columns
            result = df[['timestamp', 'symbol', 'price', 'returns', 'volatility']].copy()
            result['returns'] = result['returns'].fillna(0)
            
            # Final validation
            if len(result) == 0 or result['price'].isna().all():
                print(f"[ERROR] Failed to fetch {symbol}: Empty or invalid price data returned")
                return None
            
            print(f"[Loaded real data] {symbol}: {len(result)} days, price range ${result['price'].min():.2f}-${result['price'].max():.2f}")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch {symbol}: {e}")
            return None
    
    def generate_from_real_data(self, symbol: str, days: int = 30, data_df: Optional[pd.DataFrame] = None) -> List[MarketState]:
        """Generate market states from real historical data for backtesting.
        
        Args:
            symbol: Ticker symbol
            days: Number of days to use (from end of data)
            data_df: DataFrame with real market data. If None, fetches automatically.
        
        Returns:
            List of MarketState objects representing real market history
        """
        if data_df is None:
            data_df = self.fetch_real_market_data(symbol, days=days)
            if data_df is None:
                print("[ERROR] Could not load real data")
                return []
        
        # Use last 'days' rows
        data_df = data_df.tail(days).reset_index(drop=True)
        
        states: List[MarketState] = []
        prices = data_df['price'].values
        
        for i, row in data_df.iterrows():
            price = float(row['price'])
            volatility = float(row['volatility'])
            timestamp = row['timestamp']
            
            # Detect cycle from real returns
            if i < 20:
                cycle = CyclePhase.CHOP
            else:
                # Use last 20-day performance
                lookback_return = (prices[i] - prices[max(0, i-20)]) / prices[max(0, i-20)]
                if lookback_return > 0.05:
                    cycle = CyclePhase.BULL
                elif lookback_return < -0.05:
                    cycle = CyclePhase.BEAR
                else:
                    cycle = CyclePhase.CHOP
            
            states.append(MarketState(symbol, price, volatility, cycle, timestamp))
        
        # Record as synthetic scenario for learner (reference point)
        mse = 0.0  # Real data has no prediction error
        params = {"lamb": 0.1, "mu_j": 0.0, "sigma_j": 0.01}
        self.learner.record_outcome("real_data", params, mse, prices[-1])
        
        return states
    
    @staticmethod
    def _phase_from_price(price: float, base: float) -> CyclePhase:
        if not np.isfinite(price) or price <= 0 or base <= 0:
            return CyclePhase.CHOP
        change = (price - base) / base
        if change > 0.1:
            return CyclePhase.BULL
        if change < -0.05:
            return CyclePhase.BEAR
        return CyclePhase.CHOP

    def feedback(self, generated: List[MarketState], actual: List[MarketState]):
        # stub: compare outcomes and adapt parameters
        predicted_returns = np.array([s.price for s in generated])
        actual_returns = np.array([s.price for s in actual])
        if len(predicted_returns) != len(actual_returns):
            return
        mse = ((predicted_returns - actual_returns)**2).mean()
        # append to internal history or adjust lambda etc
        self.history.loc[len(self.history)] = {
            "timestamp": datetime.utcnow(),
            "symbol": generated[0].symbol,
            "price": float(actual_returns[-1]),
            "returns": float(np.log(actual_returns[-1] / actual_returns[0])) if actual_returns[0] > 0 else 0
        }
        return mse
