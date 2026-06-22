from __future__ import annotations
import random
from collections import deque
from typing import List, Optional

import numpy as np

from strategies.heuristic.marketstate import MarketState, TradeIntent, CyclePhase


class BaseAgent:
    registry: List[BaseAgent] = []
    quantity_multiplier: float = 1.0

    def __init__(self, name: str, history_len: int = 250):
        self.name = name
        self.prices: deque[float] = deque(maxlen=history_len)
        self.vols: deque[float] = deque(maxlen=history_len)
        
        # Virtual portfolio state
        self.virtual_positions = {}  # symbol -> {"quantity": float, "avg_price": float}
        self.virtual_options = []  # list of tuples: (symbol, side, strike, quantity, premium)
        self.virtual_realized_pnl = 0.0
        
        self.parameters = {}
        self.learning_enabled = True
        self.capital_weight = 1.0

        # Prevent duplicate instances in registry
        BaseAgent.registry = [a for a in BaseAgent.registry if a.name != name]
        BaseAgent.registry.append(self)

    def _load_parameters(self):
        try:
            from simulator.state_persistence import StateManager
            state_manager = StateManager(backend='postgres')
            loaded = state_manager.load_agent_parameters(self.name)
            if loaded:
                for k, v in loaded.items():
                    if k in self.parameters:
                        self.parameters[k] = type(self.parameters[k])(v)
                print(f"[Loaded parameters for agent {self.name} from DB]")
        except Exception as e:
            print(f"[Failed to load parameters for {self.name}: {e}]")

    def save_parameters(self):
        try:
            from simulator.state_persistence import StateManager
            state_manager = StateManager(backend='postgres')
            state_manager.save_agent_parameters(self.name, self.parameters)
        except Exception as e:
            print(f"[Failed to save parameters for {self.name}: {e}]")

    def reset(self):
        """Reset agent deques and step-tracking state between phases."""
        self.prices.clear()
        self.vols.clear()

    def update(self, market: MarketState):
        self.prices.append(market.price)
        self.vols.append(market.volatility)
        
        # Settle any options in virtual portfolio if symbol matches
        if self.virtual_options:
            remaining = []
            for item in self.virtual_options:
                symbol, side, strike, qty, premium = item
                if symbol == market.symbol:
                    if side == "PUT":
                        intrinsic = max(strike - market.price, 0.0) * qty
                    else:
                        intrinsic = max(market.price - strike, 0.0) * qty
                    pnl = intrinsic - premium
                    self.virtual_realized_pnl += pnl
                    self.update_from_outcome(symbol, side + "_SETTLE", qty, market.price, pnl)
                else:
                    remaining.append(item)
            self.virtual_options = remaining

    def decide(self, market: MarketState) -> List[TradeIntent]:
        intents = self._decide(market)
        weight = self.capital_weight
        if self.name != "The Capital Manager":
            weight *= BaseAgent.quantity_multiplier
            
        if weight != 1.0:
            filtered_intents = []
            for intent in intents:
                scaled_qty = int(intent.quantity * weight)
                if scaled_qty == 0 and intent.quantity > 0:
                    scaled_qty = 1
                if scaled_qty > 0:
                    intent.quantity = float(scaled_qty)
                    filtered_intents.append(intent)
            return filtered_intents
        return intents

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        raise NotImplementedError

    def _sma(self, window: int) -> Optional[float]:
        if len(self.prices) < window:
            return None
        return float(np.mean(list(self.prices)[-window:]))

    def _ema(self, values: List[float], window: int):
        if len(values) < window:
            return None
        weights = np.exp(np.linspace(-1., 0., window))
        weights /= weights.sum()
        return float(np.convolve(values, weights, mode='valid')[-1])

    def _rsi(self, window: int = 14) -> Optional[float]:
        if len(self.prices) < window + 1:
            return None
        deltas = np.diff(np.array(self.prices))
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def execute_virtual_intent(self, intent: TradeIntent, price: float):
        """Execute the agent's intent on its own virtual portfolio to calculate outcomes and adapt."""
        if intent.quantity <= 0 or not np.isfinite(price) or price <= 0:
            return
            
        symbol = intent.symbol
        side = intent.side
        qty = intent.quantity
        
        if side == "BUY":
            if symbol in self.virtual_positions:
                pos = self.virtual_positions[symbol]
                if pos["quantity"] < 0:
                    cover_qty = min(qty, -pos["quantity"])
                    pnl = (pos["avg_price"] - price) * cover_qty
                    self.virtual_realized_pnl += pnl
                    pos["quantity"] += cover_qty
                    
                    leftover = qty - cover_qty
                    self.update_from_outcome(symbol, "COVER", cover_qty, price, pnl)
                    
                    if pos["quantity"] == 0:
                        del self.virtual_positions[symbol]
                    
                    if leftover > 0:
                        self.virtual_positions[symbol] = {"quantity": leftover, "avg_price": price}
                else:
                    new_qty = pos["quantity"] + qty
                    if new_qty == 0:
                        del self.virtual_positions[symbol]
                    else:
                        pos["avg_price"] = ((pos["avg_price"] * pos["quantity"]) + (qty * price)) / new_qty
                        pos["quantity"] = new_qty
            else:
                self.virtual_positions[symbol] = {"quantity": qty, "avg_price": price}
                
        elif side == "SELL":
            if symbol not in self.virtual_positions:
                return
            pos = self.virtual_positions[symbol]
            sell_qty = min(qty, pos["quantity"])
            if sell_qty <= 0:
                return
            pnl = (price - pos["avg_price"]) * sell_qty
            self.virtual_realized_pnl += pnl
            pos["quantity"] -= sell_qty
            if pos["quantity"] == 0:
                del self.virtual_positions[symbol]
            self.update_from_outcome(symbol, side, sell_qty, price, pnl)
            
        elif side == "SHORT":
            if symbol in self.virtual_positions:
                pos = self.virtual_positions[symbol]
                if pos["quantity"] > 0:
                    sell_qty = min(qty, pos["quantity"])
                    pnl = (price - pos["avg_price"]) * sell_qty
                    self.virtual_realized_pnl += pnl
                    pos["quantity"] -= sell_qty
                    
                    leftover = qty - sell_qty
                    self.update_from_outcome(symbol, "SELL", sell_qty, price, pnl)
                    
                    if pos["quantity"] == 0:
                        del self.virtual_positions[symbol]
                        
                    if leftover > 0:
                        self.virtual_positions[symbol] = {"quantity": -leftover, "avg_price": price}
                else:
                    pos["quantity"] -= qty
            else:
                self.virtual_positions[symbol] = {"quantity": -qty, "avg_price": price}
                
        elif side == "COVER":
            if symbol not in self.virtual_positions or self.virtual_positions[symbol]["quantity"] >= 0:
                return
            pos = self.virtual_positions[symbol]
            cover_qty = min(qty, -pos["quantity"])
            pnl = (pos["avg_price"] - price) * cover_qty
            self.virtual_realized_pnl += pnl
            pos["quantity"] += cover_qty
            if pos["quantity"] == 0:
                del self.virtual_positions[symbol]
            self.update_from_outcome(symbol, side, cover_qty, price, pnl)
            
        elif side in ("PUT", "CALL"):
            premium = price * 0.005 * qty
            self.virtual_options.append((symbol, side, price, qty, premium))

    def close_all_virtual(self, price: float, symbol: str):
        """Force close open virtual positions at the final price to trigger adaptation at epoch end."""
        if symbol in self.virtual_positions:
            pos = self.virtual_positions[symbol]
            qty = pos["quantity"]
            if qty > 0:
                pnl = (price - pos["avg_price"]) * qty
                self.virtual_realized_pnl += pnl
                self.update_from_outcome(symbol, "SELL", qty, price, pnl)
            elif qty < 0:
                pnl = (pos["avg_price"] - price) * (-qty)
                self.virtual_realized_pnl += pnl
                self.update_from_outcome(symbol, "COVER", -qty, price, pnl)
            del self.virtual_positions[symbol]
            
        if self.virtual_options:
            remaining = []
            for item in self.virtual_options:
                sym, side, strike, qty, premium = item
                if sym == symbol:
                    if side == "PUT":
                        intrinsic = max(strike - price, 0.0) * qty
                    else:
                        intrinsic = max(price - strike, 0.0) * qty
                    pnl = intrinsic - premium
                    self.virtual_realized_pnl += pnl
                    self.update_from_outcome(sym, side + "_SETTLE", qty, price, pnl)
                else:
                    remaining.append(item)
            self.virtual_options = remaining

    def update_from_outcome(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        """Public endpoint to update parameters from an execution outcome (either virtual or real)."""
        if not self.learning_enabled:
            return
        try:
            self._adapt_parameters(symbol, side, quantity, price, pnl)
        except Exception as e:
            print(f"[Error adapting parameters in {self.name}: {e}]")

        for agent in BaseAgent.registry:
            if agent.name == "The Capital Manager" and agent.learning_enabled and agent is not self:
                try:
                    agent._adapt_parameters(symbol, side, quantity, price, pnl)
                except Exception as e:
                    print(f"[Error adapting Capital Manager parameters: {e}]")

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        pass


class Tactician(BaseAgent):
    def __init__(self):
        super().__init__("The Tactician")
        self.parameters = {
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
            "rsi_extreme_bull": 85.0,
            "macd_threshold": 0.0,
            "bear_short_qty": 12.0,
            "bear_short_conf": 0.70,
            "oversold_buy_qty": 15.0,
            "oversold_buy_conf": 0.85,
            "overbought_sell_qty": 14.0,
            "overbought_sell_conf": 0.83,
            "extreme_sell_qty": 6.0,
            "extreme_sell_conf": 0.60,
            "chop_buy_qty": 8.0,
            "chop_buy_conf": 0.40,
            "bull_buy_qty": 16.0,
            "bull_buy_conf": 0.65,
            "bear_fallback_qty": 10.0,
            "bear_fallback_conf": 0.55,
        }
        self._load_parameters()

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        rsi = self._rsi(14)
        ema12 = self._ema(list(self.prices), 12)
        ema26 = self._ema(list(self.prices), 26)

        if rsi is None or ema12 is None or ema26 is None:
            return []

        macd = ema12 - ema26
        intents: List[TradeIntent] = []
        has_short = market.symbol in self.virtual_positions and self.virtual_positions[market.symbol]["quantity"] < 0

        if market.cycle_phase == CyclePhase.BEAR and not has_short:
            intents.append(TradeIntent(
                self.name, market.symbol, "SHORT", 
                int(self.parameters["bear_short_qty"]), 
                self.parameters["bear_short_conf"], "bear momentum entry"
            ))

        if has_short:
            if macd > self.parameters["macd_threshold"] or rsi < self.parameters["rsi_oversold"]:
                intents.append(TradeIntent(
                    self.name, market.symbol, "COVER", 
                    abs(int(self.virtual_positions[market.symbol]["quantity"])), 
                    self.parameters["oversold_buy_conf"], "bear momentum slowdown cover"
                ))

        if market.cycle_phase != CyclePhase.BULL:
            if rsi < self.parameters["rsi_oversold"] and macd > self.parameters["macd_threshold"]:
                intents.append(TradeIntent(
                    self.name, market.symbol, "BUY", 
                    int(self.parameters["oversold_buy_qty"]), 
                    self.parameters["oversold_buy_conf"], "RSI oversold + momentum"
                ))
            elif rsi > self.parameters["rsi_overbought"] and macd < -self.parameters["macd_threshold"]:
                intents.append(TradeIntent(
                    self.name, market.symbol, "SELL", 
                    int(self.parameters["overbought_sell_qty"]), 
                    self.parameters["overbought_sell_conf"], "RSI overbought + momentum"
                ))
        else:
            if rsi > self.parameters["rsi_extreme_bull"] and macd < -0.1:
                intents.append(TradeIntent(
                    self.name, market.symbol, "SELL", 
                    int(self.parameters["extreme_sell_qty"]), 
                    self.parameters["extreme_sell_conf"], "extreme overbought reversal"
                ))
            elif macd < -0.05:
                intents.append(TradeIntent(
                    self.name, market.symbol, "SELL", 
                    max(1, int(self.parameters["overbought_sell_qty"] * 0.5)), 
                    self.parameters["overbought_sell_conf"], "BULL momentum slowdown exit"
                ))

        if not intents:
            if market.cycle_phase == CyclePhase.CHOP:
                intents.append(TradeIntent(
                    self.name, market.symbol, "BUY", 
                    int(self.parameters["chop_buy_qty"]), 
                    self.parameters["chop_buy_conf"], "CHOP exploration"
                ))
            elif market.cycle_phase == CyclePhase.BULL:
                intents.append(TradeIntent(
                    self.name, market.symbol, "BUY", 
                    int(self.parameters["bull_buy_qty"]), 
                    self.parameters["bull_buy_conf"], "BULL momentum aggression"
                ))
            elif market.cycle_phase == CyclePhase.BEAR and not has_short:
                intents.append(TradeIntent(
                    self.name, market.symbol, "SHORT", 
                    int(self.parameters["bear_fallback_qty"]), 
                    self.parameters["bear_fallback_conf"], "BEAR continuation"
                ))

        return intents

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        success = pnl > 0
        if side == "SELL":
            if success:
                self.parameters["oversold_buy_conf"] = min(0.98, self.parameters["oversold_buy_conf"] + 0.01)
                self.parameters["rsi_oversold"] = min(35.0, self.parameters["rsi_oversold"] + 0.2)
                self.parameters["oversold_buy_qty"] = min(30.0, self.parameters["oversold_buy_qty"] + 0.5)
            else:
                self.parameters["oversold_buy_conf"] = max(0.40, self.parameters["oversold_buy_conf"] - 0.02)
                self.parameters["rsi_oversold"] = max(25.0, self.parameters["rsi_oversold"] - 0.5)
                self.parameters["oversold_buy_qty"] = max(5.0, self.parameters["oversold_buy_qty"] - 1.0)
        elif side == "COVER":
            if success:
                self.parameters["overbought_sell_conf"] = min(0.98, self.parameters["overbought_sell_conf"] + 0.01)
                self.parameters["rsi_overbought"] = max(65.0, self.parameters["rsi_overbought"] - 0.2)
                self.parameters["overbought_sell_qty"] = min(30.0, self.parameters["overbought_sell_qty"] + 0.5)
            else:
                self.parameters["overbought_sell_conf"] = max(0.40, self.parameters["overbought_sell_conf"] - 0.02)
                self.parameters["rsi_overbought"] = min(75.0, self.parameters["rsi_overbought"] + 0.5)
                self.parameters["overbought_sell_qty"] = max(5.0, self.parameters["overbought_sell_qty"] - 1.0)


class Sentinel(BaseAgent):
    def __init__(self):
        super().__init__("The Sentinel")
        self.last_hedge_step = -100
        self.parameters = {
            "vol_spike_threshold": 1.2,
            "vol_std_mult": 2.0,
            "hedge_interval": 3.0,
            "put_qty_non_bear": 2.0,
            "put_qty_bear": 3.0,
            "put_conf_non_bear": 0.65,
            "put_conf_bear": 0.72,
        }
        self._load_parameters()

    def reset(self):
        super().reset()
        self.last_hedge_step = -100

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        intents: List[TradeIntent] = []
        current_step = len(self.prices)
        if current_step - self.last_hedge_step < int(self.parameters["hedge_interval"]):
            return intents
        
        atr = self._sma(14)
        vol_spike = market.volatility > self.parameters["vol_spike_threshold"]
        if atr and market.volatility > max(0.6, np.std(list(self.vols)) * self.parameters["vol_std_mult"]):
            vol_spike = True

        if vol_spike or market.cycle_phase == CyclePhase.BEAR:
            put_qty = int(self.parameters["put_qty_bear"]) if market.cycle_phase == CyclePhase.BEAR else int(self.parameters["put_qty_non_bear"])
            confidence = self.parameters["put_conf_bear"] if market.cycle_phase == CyclePhase.BEAR else self.parameters["put_conf_non_bear"]
            intents.append(TradeIntent(self.name, market.symbol, "PUT", put_qty, confidence, "crash protection"))
            self.last_hedge_step = current_step

        return intents

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        success = pnl > 0
        if side in ("PUT", "PUT_SETTLE"):
            if success:
                self.parameters["put_conf_bear"] = min(0.98, self.parameters["put_conf_bear"] + 0.02)
                self.parameters["put_conf_non_bear"] = min(0.95, self.parameters["put_conf_non_bear"] + 0.02)
                self.parameters["vol_spike_threshold"] = max(0.6, self.parameters["vol_spike_threshold"] - 0.05)
            else:
                self.parameters["put_conf_bear"] = max(0.45, self.parameters["put_conf_bear"] - 0.02)
                self.parameters["put_conf_non_bear"] = max(0.40, self.parameters["put_conf_non_bear"] - 0.02)
                self.parameters["vol_spike_threshold"] = min(1.8, self.parameters["vol_spike_threshold"] + 0.05)


class Anchor(BaseAgent):
    def __init__(self):
        super().__init__("The Anchor")
        self.parameters = {
            "ma_window": 200.0,
            "buy_qty": 20.0,
            "buy_conf": 0.95,
        }
        self._load_parameters()

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        intents: List[TradeIntent] = []
        ma_win = int(self.parameters["ma_window"])
        ma200 = self._sma(ma_win)

        if ma200 is None:
            return []

        if market.cycle_phase == CyclePhase.BULL and market.price > ma200:
            intents.append(TradeIntent(
                self.name, market.symbol, "BUY", 
                int(self.parameters["buy_qty"]), 
                self.parameters["buy_conf"], "core winner accumulation"
            ))

        return intents

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        success = pnl > 0
        if side == "SELL":
            if success:
                self.parameters["buy_conf"] = min(0.99, self.parameters["buy_conf"] + 0.005)
                self.parameters["buy_qty"] = min(50.0, self.parameters["buy_qty"] + 1.0)
                self.parameters["ma_window"] = min(300.0, self.parameters["ma_window"] + 5.0)
            else:
                self.parameters["buy_conf"] = max(0.70, self.parameters["buy_conf"] - 0.02)
                self.parameters["buy_qty"] = max(5.0, self.parameters["buy_qty"] - 2.0)
                self.parameters["ma_window"] = max(100.0, self.parameters["ma_window"] - 5.0)


class CapitalManager(BaseAgent):
    def __init__(self):
        super().__init__("The Capital Manager")
        self.peak_pnl = 0.0
        self.parameters = {
            "drawdown_threshold": 10000.0,
            "drawdown_limit": 40000.0,
            "min_scale": 0.1,
            "sharpe_window": 30.0,
            "sharpe_high": 0.2,
            "sharpe_low": -0.2,
            "buy_qty": 3.0,
            "buy_conf": 0.65,
            "sell_qty": 2.0,
            "sell_conf": 0.60,
        }
        self._load_parameters()

    def reset(self):
        super().reset()
        self.peak_pnl = 0.0
        BaseAgent.quantity_multiplier = 1.0

    def _decide(self, market: MarketState) -> List[TradeIntent]:
        # 1. Drawdown Circuit Breaker logic (from Meta-Opt)
        agg_pnl = 0.0
        for agent in BaseAgent.registry:
            if agent.name == "The Capital Manager":
                continue
            unrealized = 0.0
            for symbol, pos in agent.virtual_positions.items():
                unrealized += (market.price - pos["avg_price"]) * pos["quantity"]
            agg_pnl += agent.virtual_realized_pnl + unrealized

        if agg_pnl > self.peak_pnl:
            self.peak_pnl = agg_pnl

        drawdown = self.peak_pnl - agg_pnl
        threshold = self.parameters.get("drawdown_threshold", 10000.0)
        limit = self.parameters.get("drawdown_limit", 40000.0)
        min_scale = self.parameters.get("min_scale", 0.1)

        if drawdown <= threshold:
            scale_factor = 1.0
        elif drawdown >= limit:
            scale_factor = min_scale
        else:
            scale_factor = 1.0 - (drawdown - threshold) / (limit - threshold) * (1.0 - min_scale)

        BaseAgent.quantity_multiplier = scale_factor

        # 2. Reallocation/Risk-Reduction logic (from Treasurer)
        sharpe_win = int(self.parameters["sharpe_window"])
        if len(self.prices) < sharpe_win + 1:
            return []

        prices_window = list(self.prices)[-(sharpe_win + 1):]
        returns = np.diff(np.log(np.array(prices_window)))
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8)

        if sharpe > self.parameters["sharpe_high"] and market.cycle_phase == CyclePhase.BULL:
            return [TradeIntent(
                self.name, market.symbol, "BUY", 
                int(self.parameters["buy_qty"]), 
                self.parameters["buy_conf"], "performance reallocation"
            )]
        if sharpe < self.parameters["sharpe_low"] and market.cycle_phase == CyclePhase.BEAR:
            return [TradeIntent(
                self.name, market.symbol, "SELL", 
                int(self.parameters["sell_qty"]), 
                self.parameters["sell_conf"], "risk reduce"
            )]

        return []

    def _adapt_parameters(self, symbol: str, side: str, quantity: float, price: float, pnl: float):
        success = pnl > 0
        if side == "SELL":
            if success:
                self.parameters["buy_conf"] = min(0.95, self.parameters["buy_conf"] + 0.01)
                self.parameters["sharpe_high"] = max(0.05, self.parameters["sharpe_high"] - 0.01)
                self.parameters["buy_qty"] = min(10.0, self.parameters["buy_qty"] + 0.5)
                self.parameters["drawdown_threshold"] = min(20000.0, self.parameters["drawdown_threshold"] + 100.0)
                self.parameters["drawdown_limit"] = min(80000.0, self.parameters["drawdown_limit"] + 400.0)
            else:
                self.parameters["buy_conf"] = max(0.45, self.parameters["buy_conf"] - 0.02)
                self.parameters["sharpe_high"] = min(0.35, self.parameters["sharpe_high"] + 0.02)
                self.parameters["buy_qty"] = max(1.0, self.parameters["buy_qty"] - 0.5)
                self.parameters["drawdown_threshold"] = max(10000.0, self.parameters["drawdown_threshold"] - 200.0)
                self.parameters["drawdown_limit"] = max(30000.0, self.parameters["drawdown_limit"] - 800.0)
        elif side == "COVER":
            if success:
                self.parameters["sell_conf"] = min(0.95, self.parameters["sell_conf"] + 0.01)
                self.parameters["sharpe_low"] = min(-0.05, self.parameters["sharpe_low"] + 0.01)
                self.parameters["sell_qty"] = min(10.0, self.parameters["sell_qty"] + 0.5)
                self.parameters["drawdown_threshold"] = min(20000.0, self.parameters["drawdown_threshold"] + 100.0)
                self.parameters["drawdown_limit"] = min(80000.0, self.parameters["drawdown_limit"] + 400.0)
            else:
                self.parameters["sell_conf"] = max(0.40, self.parameters["sell_conf"] - 0.02)
                self.parameters["sharpe_low"] = max(-0.35, self.parameters["sharpe_low"] - 0.02)
                self.parameters["sell_qty"] = max(1.0, self.parameters["sell_qty"] - 0.5)
                self.parameters["drawdown_threshold"] = max(10000.0, self.parameters["drawdown_threshold"] - 200.0)
                self.parameters["drawdown_limit"] = max(30000.0, self.parameters["drawdown_limit"] - 800.0)
