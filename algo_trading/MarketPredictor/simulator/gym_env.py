import numpy as np
import random
from collections import deque
from typing import List, Dict, Tuple, Optional

from strategies.heuristic.marketstate import MarketState, CyclePhase, TradeIntent
from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.protocol import SyntheticHedgeProtocol
from core.execution import Portfolio
from core.risk_manager import RiskConfig, RiskManager

class EnvConfig:
    def __init__(self, 
                 state_dim: int = 9, 
                 min_trade_threshold_pct: float = 0.02, 
                 transaction_cost_pct: float = 0.0015, 
                 stop_loss_pct: float = 0.05, 
                 use_one_hot_regime: bool = True,
                 use_learning: bool = True):
        self.state_dim = state_dim
        self.min_trade_threshold_pct = min_trade_threshold_pct
        self.transaction_cost_pct = transaction_cost_pct
        self.stop_loss_pct = stop_loss_pct
        self.use_one_hot_regime = use_one_hot_regime
        self.use_learning = use_learning

class AITradingEnv:
    """
    Custom Gym-like Environment for Deep Reinforcement Learning.
    Wraps the DigitalTwin simulator and Portfolio execution.
    """
    def __init__(self, simulator, symbol: str, days: int, scenario: str = "mixed", starting_capital: float = 1_000_000.0, config: Optional[EnvConfig] = None):
        self.config = config if config is not None else EnvConfig()
        self.simulator = simulator
        self.symbol = symbol
        self.days = days
        self.scenario = scenario
        self.starting_capital = starting_capital
        
        # State tracking deques
        self.history_len = 50
        self.prices: deque[float] = deque(maxlen=self.history_len)
        
        # Core structures
        self.portfolio: Optional[Portfolio] = None
        self.blackboard: Optional[Blackboard] = None
        self.protocol: Optional[SyntheticHedgeProtocol] = None
        self.risk_manager: Optional[RiskManager] = None
        
        # Scenario states
        self.states: List[MarketState] = []
        self.current_idx = 0
        self.peak_nav = starting_capital
        self.prev_action = None
        
        # Stop-loss and cost settings
        self.stop_loss_pct = self.config.stop_loss_pct
        self.transaction_cost_pct = self.config.transaction_cost_pct

    def reset(self, scenario: Optional[str] = None) -> np.ndarray:
        """Reset environment to a fresh scenario run."""
        if scenario:
            self.scenario = scenario
            
        # Generate new trajectory using the digital twin simulator
        self.states = self.simulator.generate(self.symbol, days=self.days, scenario=self.scenario, use_learning=self.config.use_learning)
        self._precompute_indicators()
        self.current_idx = 0
        self.prices.clear()
        
        # Re-initialize execution models
        self.portfolio = Portfolio(cash=self.starting_capital)
        self.blackboard = Blackboard()
        self.protocol = SyntheticHedgeProtocol(self.blackboard)
        
        # Configure Risk Manager
        risk_config = RiskConfig()
        risk_config.stop_loss_pct = self.stop_loss_pct
        self.risk_manager = RiskManager(risk_config, starting_capital=self.starting_capital)
        
        self.peak_nav = self.starting_capital
        self.prev_action = None
        
        # Warmup deques with initial state data
        state = self.states[0]
        self.prices.append(state.price)
        
        return self._get_observation()

    def _precompute_indicators(self):
        """Precompute RSI and MACD for all steps in the episode to avoid redundant step-by-step overhead."""
        prices = [state.price for state in self.states]
        n = len(prices)
        self.precomputed_rsi = np.full(n, 50.0, dtype=np.float32)
        self.precomputed_macd = np.zeros(n, dtype=np.float32)
        
        for i in range(n):
            start_idx = max(0, i - self.history_len + 1)
            window_prices = prices[start_idx:i+1]
            
            # Calculate RSI (window = 14)
            if len(window_prices) >= 15:
                deltas = np.diff(window_prices)
                gains = np.where(deltas > 0, deltas, 0.0)
                losses = np.where(deltas < 0, -deltas, 0.0)
                avg_gain = np.mean(gains[-14:])
                avg_loss = np.mean(losses[-14:])
                if avg_loss == 0:
                    self.precomputed_rsi[i] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    self.precomputed_rsi[i] = 100.0 - (100.0 / (1.0 + rs))
            else:
                self.precomputed_rsi[i] = 50.0
                
            # Calculate MACD (fast=12, slow=26)
            if len(window_prices) >= 26:
                ema_fast = self._ema(window_prices, 12)
                ema_slow = self._ema(window_prices, 26)
                self.precomputed_macd[i] = ema_fast - ema_slow
            else:
                self.precomputed_macd[i] = 0.0

    def _get_observation(self) -> np.ndarray:
        """Construct a normalized 1D state vector of features."""
        # Baseline price fallback if deque has too few elements
        current_price = self.prices[-1] if self.prices else 100.0
        
        # 1. Technical Indicators calculation
        rsi = self.precomputed_rsi[self.current_idx] if self.current_idx < len(self.precomputed_rsi) else 50.0
        macd = self.precomputed_macd[self.current_idx] if self.current_idx < len(self.precomputed_macd) else 0.0
        vol = self.states[self.current_idx].volatility if self.current_idx < len(self.states) else 0.2
        
        # 2. Portfolio Context
        nav = self.portfolio.net_asset_value({self.symbol: current_price}) if self.portfolio else self.starting_capital
        cash_ratio = (self.portfolio.cash / nav) if (self.portfolio and nav > 0) else 1.0
        
        # Position sizing and direction
        pos_qty = 0.0
        pos_avg_price = 0.0
        if self.portfolio and self.symbol in self.portfolio.positions:
            pos = self.portfolio.positions[self.symbol]
            pos_qty = pos.quantity
            pos_avg_price = pos.avg_price
            
        # Calculate unrealized PnL
        unrealized_pnl = 0.0
        if pos_qty > 0:
            unrealized_pnl = (current_price - pos_avg_price) / pos_avg_price
        elif pos_qty < 0:
            unrealized_pnl = (pos_avg_price - current_price) / pos_avg_price
            
        # Normalize features strictly to [-1.0, 1.0] range
        norm_rsi = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)
        norm_macd = np.clip((macd / current_price) * 50.0 if current_price > 0 else 0.0, -1.0, 1.0)
        norm_vol = np.clip((vol - 0.5) / 1.5, -1.0, 1.0) # standard vol normalizer
        position_value = pos_qty * current_price
        norm_position = np.clip(position_value / nav if nav > 0 else 0.0, -1.0, 1.0)
        norm_unrealized_pnl = np.clip(unrealized_pnl * 20.0, -1.0, 1.0)
        norm_cash_ratio = np.clip((cash_ratio - 0.5) * 2.0, -1.0, 1.0)
        
        # Regime indicators (one-hot or continuous)
        regime = self.states[self.current_idx].cycle_phase if self.current_idx < len(self.states) else CyclePhase.CHOP
        
        if self.config.use_one_hot_regime:
            is_bull = 1.0 if regime == CyclePhase.BULL else 0.0
            is_bear = 1.0 if regime == CyclePhase.BEAR else 0.0
            is_chop = 1.0 if regime == CyclePhase.CHOP else 0.0
            
            obs = np.array([
                norm_rsi,
                norm_macd,
                norm_vol,
                norm_position,
                norm_unrealized_pnl,
                norm_cash_ratio,
                is_bull,
                is_bear,
                is_chop,
            ], dtype=np.float32)
        else:
            norm_regime = 1.0 if regime == CyclePhase.BULL else (-1.0 if regime == CyclePhase.BEAR else 0.0)
            
            obs = np.array([
                norm_rsi,
                norm_macd,
                norm_vol,
                norm_position,
                norm_unrealized_pnl,
                norm_cash_ratio,
                norm_regime,
            ], dtype=np.float32)
        
        return obs

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Execute one action step.
        action: 0 = Neutral/Exit,
                1 = Go Long (5% NAV), 2 = Go Long (25% NAV),
                3 = Go Short (5% NAV), 4 = Go Short (25% NAV)
        """
        if self.current_idx >= len(self.states) - 1:
            return self._get_observation(), 0.0, True, {}
            
        state = self.states[self.current_idx]
        self.prices.append(state.price)
        
        # Get current position info
        current_qty = 0.0
        if self.symbol in self.portfolio.positions:
            current_qty = self.portfolio.positions[self.symbol].quantity
            
        # Reset blackboard and protocol for the step
        self.blackboard = Blackboard()
        self.protocol = SyntheticHedgeProtocol(self.blackboard)
        self.protocol.update(state)
        
        # Base trade sizing (dynamic relative to NAV)
        nav = self.portfolio.net_asset_value({self.symbol: state.price})
        
        # Determine target quantity and direction based on 5 actions and dynamic capital weight
        capital_weight = 1.0
        if state.cycle_phase == CyclePhase.BULL:
            capital_weight = 0.5
        elif state.cycle_phase == CyclePhase.BEAR:
            capital_weight = 1.5
        elif state.cycle_phase == CyclePhase.CHOP:
            capital_weight = 1.2
            
        target_qty = 0.0
        if action in (1, 2, 3, 4):
            size_mult = 1.0 if action in (1, 3) else 5.0
            target_qty = max(10.0, int((nav * 0.05 * size_mult * capital_weight) / state.price))
            if action in (3, 4):
                target_qty = -target_qty
                
        # Convert Discrete Actions into netted Trade Intents
        intents = []
        qty_to_buy = target_qty - current_qty
        min_trade_threshold = (nav * self.config.min_trade_threshold_pct) / state.price  # custom NAV threshold limit from config
        
        if abs(qty_to_buy) >= min_trade_threshold or action != self.prev_action:
            if target_qty > 0: # We want to be Long target_qty
                if current_qty < 0:
                    # Cover short first
                    intents.append(TradeIntent("RLAgent", self.symbol, "COVER", abs(current_qty), 1.0))
                    current_qty = 0.0
                
                # Adjust to target long quantity
                qty_to_buy = target_qty - current_qty
                if qty_to_buy > 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "BUY", qty_to_buy, 1.0))
                elif qty_to_buy < 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "SELL", abs(qty_to_buy), 1.0))
                    
            elif target_qty < 0: # We want to be Short abs(target_qty)
                if current_qty > 0:
                    # Sell long first
                    intents.append(TradeIntent("RLAgent", self.symbol, "SELL", current_qty, 1.0))
                    current_qty = 0.0
                    
                # Adjust to target short quantity
                diff = target_qty - current_qty
                if diff < 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "SHORT", abs(diff), 1.0))
                elif diff > 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "COVER", diff, 1.0))
                    
            else: # target_qty == 0, Neutral/Exit
                if current_qty > 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "SELL", current_qty, 1.0))
                elif current_qty < 0:
                    intents.append(TradeIntent("RLAgent", self.symbol, "COVER", abs(current_qty), 1.0))
                
        # Register intents and resolve
        for intent in intents:
            try:
                self.blackboard.register_model_intent(intent)
            except:
                pass
                
        orders = self.blackboard.resolve(state.price)
        
        # Execute orders and track transaction costs
        pnl_before = self.portfolio.realized_pnl
        for order in orders:
            # Apply transaction costs directly to cash
            cost = order.quantity * state.price * self.transaction_cost_pct
            self.portfolio.cash -= cost
            self.portfolio.execute(order.symbol, order.side, order.quantity, state.price)
            
        self.portfolio.settle_options_daily(state.price)
        
        # --- ACTIVE RISK MANAGER STOP-LOSS VALIDATION ---
        sl_triggered = False
        if self.symbol in self.portfolio.positions:
            pos = self.portfolio.positions[self.symbol]
            violation = self.risk_manager.validate_stop_loss(self.symbol, pos.quantity, pos.avg_price, state.price, current_step=self.current_idx)
            if violation:
                # Immediate forced stop-out trade
                self.portfolio.execute(self.symbol, "SELL" if pos.quantity > 0 else "COVER", abs(pos.quantity), state.price)
                sl_triggered = True
                
        # Advance index to next state
        self.current_idx += 1
        next_state = self.states[self.current_idx]
        
        # Compute Reward
        next_nav = self.portfolio.net_asset_value({self.symbol: next_state.price})
        nav_change = next_nav - nav
        
        # Calculate Peak Drawdown
        if next_nav > self.peak_nav:
            self.peak_nav = next_nav
        drawdown = (self.peak_nav - next_nav) / self.peak_nav if self.peak_nav > 0 else 0.0
        
        # Determine regime context for rewards
        regime = state.cycle_phase
        
        # Reward function: NAV changes - Drawdown Penalty - Stop Loss Penalty
        base_pnl_reward = nav_change / self.starting_capital * 100.0
        
        # Multi-objective asymmetric scaling by regime
        if regime == CyclePhase.BULL:
            # Reward: lower drawdown sensitivity, higher holding bonus for longs
            step_reward = base_pnl_reward
            step_reward -= drawdown * 0.5
            
            # Holding bonus
            unrealized_return = 0.0
            if self.symbol in self.portfolio.positions:
                pos = self.portfolio.positions[self.symbol]
                if pos.quantity > 0:
                    unrealized_return = (next_state.price - pos.avg_price) / pos.avg_price
                elif pos.quantity < 0:
                    unrealized_return = (pos.avg_price - next_state.price) / pos.avg_price
            
            if unrealized_return > 0.01:
                if self.symbol in self.portfolio.positions and self.portfolio.positions[self.symbol].quantity > 0:
                    step_reward += 1.0  # Stronger holding bonus for longs in BULL
                else:
                    step_reward += 0.25
            
            # Stiffer penalty for exiting/shorting in BULL
            if action in (3, 4):
                step_reward -= 2.0  # Stiff shorting penalty in BULL
            elif action == 0 and self.prev_action in (1, 2):
                step_reward -= 1.0  # Stiff exiting penalty in BULL
                
        elif regime == CyclePhase.BEAR:
            # Reward: highly defensive, penalize long drawdown, boost shorting profits
            step_reward = base_pnl_reward
            
            # Boost shorting profits (when nav_change is positive and agent is short)
            if nav_change > 0 and action in (3, 4):
                step_reward += base_pnl_reward  # Double the reward for profitable shorting
                
            step_reward -= drawdown * 3.0  # Harsh drawdown penalty in bear
            
            # Penalize holding longs during bear regime to encourage short/cash bias
            if action in (1, 2):
                step_reward -= 0.5
            
            # Standard holding bonus
            unrealized_return = 0.0
            if self.symbol in self.portfolio.positions:
                pos = self.portfolio.positions[self.symbol]
                if pos.quantity > 0:
                    unrealized_return = (next_state.price - pos.avg_price) / pos.avg_price
                elif pos.quantity < 0:
                    unrealized_return = (pos.avg_price - next_state.price) / pos.avg_price
            if unrealized_return > 0.01:
                step_reward += 0.2
                
        else:  # CHOP
            # Reward: discourage trading, penalize whipsawing heavily
            step_reward = base_pnl_reward
            step_reward -= drawdown * 2.0
            
            # Standard holding bonus
            unrealized_return = 0.0
            if self.symbol in self.portfolio.positions:
                pos = self.portfolio.positions[self.symbol]
                if pos.quantity > 0:
                    unrealized_return = (next_state.price - pos.avg_price) / pos.avg_price
                elif pos.quantity < 0:
                    unrealized_return = (pos.avg_price - next_state.price) / pos.avg_price
            if unrealized_return > 0.01:
                step_reward += 0.2
                
        # Common penalties
        if sl_triggered:
            step_reward -= 5.0  # Large penalty for stop-loss violation
            
        # Action Change Penalty (Anti-Whipsaw)
        if self.prev_action is not None:
            prev_is_long = self.prev_action in (1, 2)
            prev_is_short = self.prev_action in (3, 4)
            curr_is_long = action in (1, 2)
            curr_is_short = action in (3, 4)
            if (curr_is_long and prev_is_short) or (curr_is_short and prev_is_long):
                # Double whipsaw penalty in CHOP to force inactivity
                whipsaw_penalty = 1.0 if regime == CyclePhase.CHOP else 0.5
                step_reward -= whipsaw_penalty
                
            # Extra transaction fee friction penalty in CHOP for any active order change
            if regime == CyclePhase.CHOP and action != self.prev_action and action != 0:
                step_reward -= 0.5
                
        # Update prev_action for next step
        self.prev_action = action
            
        done = (self.current_idx >= len(self.states) - 1)
        
        info = {
            "nav": next_nav,
            "realized_pnl": self.portfolio.realized_pnl,
            "trades": len(self.portfolio.get_trade_history()),
            "drawdown": drawdown,
            "sl_triggered": sl_triggered
        }
        
        return self._get_observation(), float(step_reward), done, info

    def _calculate_rsi(self, window: int) -> float:
        """Helper to calculate standard RSI from prices deque."""
        if len(self.prices) < window + 1:
            return 50.0
        deltas = np.diff(np.array(self.prices))
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_macd(self, fast: int, slow: int) -> float:
        """Helper to calculate standard MACD (EMA_fast - EMA_slow)."""
        if len(self.prices) < slow:
            return 0.0
        # Calculate simple exponential smoothing
        prices_arr = list(self.prices)
        ema_fast = self._ema(prices_arr, fast)
        ema_slow = self._ema(prices_arr, slow)
        return ema_fast - ema_slow

    def _ema(self, values: List[float], window: int) -> float:
        alpha = 2.0 / (window + 1.0)
        ema = values[0]
        for val in values[1:]:
            ema = alpha * val + (1.0 - alpha) * ema
        return ema
