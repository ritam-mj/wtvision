from __future__ import annotations
import os
import numpy as np
from typing import List, Optional

from strategies.heuristic.agents import BaseAgent
from strategies.heuristic.marketstate import MarketState, TradeIntent, CyclePhase

class RLTactician(BaseAgent):
    """
    Unified Deep Reinforcement Learning Agent.
    Loads trained Q-Network weights from rl_trading_model.pt and predicts optimal actions.
    """
    def __init__(self):
        super().__init__("The RL Tactician")
        self.parameters = {}
        
        # Load torch dynamically to avoid loading issues elsewhere
        import torch
        from strategies.tactician.dqn_agent import QNetwork
        from simulator.gym_env import EnvConfig
        
        self.config = EnvConfig()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = QNetwork(state_dim=self.config.state_dim, action_dim=5).to(self.device)
        self.policy_net.eval()
        
        # Resolve model path relative to this script's directory
        model_path = os.path.join(os.path.dirname(__file__), "rl_trading_model.pt")
        if os.path.exists(model_path):
            try:
                self.policy_net.load_state_dict(torch.load(model_path, map_location=self.device))
                print(f"[RLTactician] Loaded trained policy model from {model_path}")
            except Exception as e:
                print(f"[RLTactician] Error loading model from {model_path}: {e}")
        else:
            print(f"[RLTactician] Warning: No trained model weights found at {model_path}. Actions will be neutral.")

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        # Ensure we have warm prices history
        if len(self.prices) < 30:
            return []
            
        import torch
        
        # 1. Indicator calculations
        rsi = self._rsi(14) or 50.0
        
        # Calculate MACD
        ema12 = self._ema(list(self.prices), 12) or market.price
        ema26 = self._ema(list(self.prices), 26) or market.price
        macd = ema12 - ema26
        
        # 2. Portfolio features from virtual portfolio
        pos_qty = 0.0
        pos_avg_price = 0.0
        if market.symbol in self.virtual_positions:
            pos = self.virtual_positions[market.symbol]
            pos_qty = pos["quantity"]
            pos_avg_price = pos["avg_price"]
            
        unrealized_pnl = 0.0
        if pos_qty > 0:
            unrealized_pnl = (market.price - pos_avg_price) / pos_avg_price
        elif pos_qty < 0:
            unrealized_pnl = (pos_avg_price - market.price) / pos_avg_price
            
        # Calculate virtual NAV
        unrealized = pos_qty * (market.price - pos_avg_price) if pos_qty != 0 else 0.0
        nav = 1000000.0 + self.virtual_realized_pnl + unrealized
        cash = nav - (pos_qty * market.price)
        cash_ratio = (cash / nav) if nav > 0 else 1.0
        
        # 3. Parameter Normalization matching AITradingEnv
        norm_rsi = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)
        norm_macd = np.clip((macd / market.price) * 50.0 if market.price > 0 else 0.0, -1.0, 1.0)
        norm_vol = np.clip((market.volatility - 0.5) / 1.5, -1.0, 1.0)
        position_value = pos_qty * market.price
        norm_position = np.clip(position_value / nav if nav > 0 else 0.0, -1.0, 1.0)
        norm_unrealized_pnl = np.clip(unrealized_pnl * 20.0, -1.0, 1.0)
        norm_cash_ratio = np.clip((cash_ratio - 0.5) * 2.0, -1.0, 1.0)
        
        if self.config.use_one_hot_regime:
            is_bull = 1.0 if market.cycle_phase == CyclePhase.BULL else 0.0
            is_bear = 1.0 if market.cycle_phase == CyclePhase.BEAR else 0.0
            is_chop = 1.0 if market.cycle_phase == CyclePhase.CHOP else 0.0
            
            obs = np.array([
                norm_rsi,
                norm_macd,
                norm_vol,
                norm_position,
                norm_unrealized_pnl,
                norm_cash_ratio,
                is_bull,
                is_bear,
                is_chop
            ], dtype=np.float32)
        else:
            norm_regime = 1.0 if market.cycle_phase == CyclePhase.BULL else (-1.0 if market.cycle_phase == CyclePhase.BEAR else 0.0)
            
            obs = np.array([
                norm_rsi,
                norm_macd,
                norm_vol,
                norm_position,
                norm_unrealized_pnl,
                norm_cash_ratio,
                norm_regime
            ], dtype=np.float32)
        
        # Forward pass through Q-Network
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.policy_net(obs_t)
            action = int(q_values.argmax(dim=1).item())
            
        # 4. Action execution translation
        size_mult = 1.0 if action in (1, 3) else 5.0
        target_qty = 0.0
        if action in (1, 2, 3, 4):
            target_qty = max(10.0, int((nav * 0.05 * size_mult) / market.price))
            if action in (3, 4):
                target_qty = -target_qty
                
        intents: List[TradeIntent] = []
        if target_qty > 0: # We want to be Long
            if pos_qty < 0:
                intents.append(TradeIntent(self.name, market.symbol, "COVER", abs(pos_qty), 1.0, "RL cover short"))
                pos_qty = 0.0
            
            qty_to_buy = target_qty - pos_qty
            if qty_to_buy > 0:
                intents.append(TradeIntent(self.name, market.symbol, "BUY", qty_to_buy, 1.0, "RL long entry/adjust"))
            elif qty_to_buy < 0:
                intents.append(TradeIntent(self.name, market.symbol, "SELL", abs(qty_to_buy), 1.0, "RL long reduce"))
                
        elif target_qty < 0: # We want to be Short
            if pos_qty > 0:
                intents.append(TradeIntent(self.name, market.symbol, "SELL", pos_qty, 1.0, "RL sell long"))
                pos_qty = 0.0
                
            diff = target_qty - pos_qty
            if diff < 0:
                intents.append(TradeIntent(self.name, market.symbol, "SHORT", abs(diff), 1.0, "RL short entry/adjust"))
            elif diff > 0:
                intents.append(TradeIntent(self.name, market.symbol, "COVER", diff, 1.0, "RL short reduce"))
                
        else: # target_qty == 0, Neutral/Exit
            if pos_qty > 0:
                intents.append(TradeIntent(self.name, market.symbol, "SELL", pos_qty, 1.0, "RL exit long"))
            elif pos_qty < 0:
                intents.append(TradeIntent(self.name, market.symbol, "COVER", abs(pos_qty), 1.0, "RL exit short"))
                
        return intents

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        # Reinforcement Learning agent parameters are adapted via gradient descent, not heuristics
        pass
