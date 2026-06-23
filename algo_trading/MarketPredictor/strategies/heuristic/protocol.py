from __future__ import annotations
from collections import deque
from typing import Set, Optional

from strategies.heuristic.blackboard import Blackboard
from strategies.heuristic.marketstate import MarketState, CyclePhase


class RegimeDetector:
    def __init__(self, window: int = 20, drawdown_threshold: float = 0.07, volatility_threshold: float = 0.6):
        self.window = window
        self.prices = deque(maxlen=window)
        self.vols = deque(maxlen=window)
        self.drawdown_threshold = drawdown_threshold
        self.volatility_threshold = volatility_threshold

    def update(self, state: MarketState):
        self.prices.append(state.price)
        self.vols.append(state.volatility)

    def _drawdown(self) -> Optional[float]:
        if not self.prices:
            return None
        prices = list(self.prices)
        peak = max(prices)
        trough = min(prices)
        if peak <= 0:
            return None
        return (peak - trough) / peak

    def detect(self, state: MarketState) -> CyclePhase:
        if len(self.prices) < self.window:
            return state.cycle_phase

        drawdown = self._drawdown() or 0.0
        mean_vol = sum(self.vols) / len(self.vols)

        if drawdown >= self.drawdown_threshold or mean_vol > self.volatility_threshold:
            return CyclePhase.BEAR

        recent = self.prices[-1]
        old = self.prices[0]
        change_pct = (recent - old) / old if old > 0 else 0
        if change_pct > 0.08:
            return CyclePhase.BULL

        return CyclePhase.CHOP


class SyntheticHedgeProtocol:
    def __init__(self, blackboard: Blackboard):
        self.blackboard = blackboard
        self.regime = RegimeDetector()
        self.bear_active: bool = False
        self.market_watch: Set[str] = set()
        
        # New properties for risk mitigation and performance-based routing
        self.prev_regime: Optional[CyclePhase] = None
        self.shift_cooldown_counter: int = 0
        self.agent_pnl_baselines: Dict[str, float] = {}
        self.agent_pnl_multipliers: Dict[str, float] = {}
        self.step_counter: int = 0

    def update(self, state: MarketState, current_nav: Optional[float] = None):
        self.regime.update(state)
        detected = self.regime.detect(state)
        self.step_counter += 1

        # 1. Hedge Permitting logic
        if detected == CyclePhase.BEAR:
            if not self.bear_active:
                self.bear_active = True
                self.blackboard.enable_synthetic_hedge(state.symbol)
                self.market_watch.add(state.symbol)
        elif self.bear_active and detected == CyclePhase.BULL:
            self.bear_active = False
            for symbol in list(self.market_watch):
                self.blackboard.disable_synthetic_hedge(symbol)
                self.market_watch.remove(symbol)

        # 2. Regime Shift Risk Mitigation (New Territory Cooldown)
        from strategies.heuristic.agents import BaseAgent
        
        if self.prev_regime is None:
            self.prev_regime = detected

        if detected != self.prev_regime:
            print(f"[REGIME SHIFT ALERT] Trend shifted from {self.prev_regime.name} to {detected.name}. Triggering risk reduction cooldown.")
            self.shift_cooldown_counter = 10
            self.prev_regime = detected

        if self.shift_cooldown_counter > 0:
            BaseAgent.quantity_multiplier = 0.25  # Force 25% size in new territory
            self.shift_cooldown_counter -= 1
        else:
            BaseAgent.quantity_multiplier = 1.0

        # 3. Dynamic Capital Allocation Routing & Performance-Based Routing
        from core.utils.market_cap import get_market_cap_category
        
        category = get_market_cap_category(state.symbol)
        
        # Update performance multipliers every 20 steps based on virtual realized PnL trajectory
        if self.step_counter % 20 == 0 or not self.agent_pnl_baselines:
            for agent in BaseAgent.registry:
                current_pnl = getattr(agent, 'virtual_realized_pnl', 0.0)
                baseline_pnl = self.agent_pnl_baselines.get(agent.name, current_pnl)
                pnl_diff = current_pnl - baseline_pnl
                
                prev_mult = self.agent_pnl_multipliers.get(agent.name, 1.0)
                if pnl_diff > 0:
                    new_mult = min(2.0, prev_mult * 1.25)
                elif pnl_diff < 0:
                    new_mult = max(0.5, prev_mult * 0.75)
                else:
                    new_mult = prev_mult
                    
                self.agent_pnl_multipliers[agent.name] = new_mult
                self.agent_pnl_baselines[agent.name] = current_pnl

        # Calculate dynamic capital allocations based on 50% baseline (equally split) and 50% performance pool
        trading_agents = [a for a in BaseAgent.registry if a.name != "The Capital Manager"]
        M = len(trading_agents)
        c_total = current_nav if current_nav is not None else 1000000.0
        
        if M > 0:
            base_pct = 0.50 / M
            sum_mult = sum(self.agent_pnl_multipliers.get(a.name, 1.0) for a in trading_agents)
            
            for agent in trading_agents:
                m_i = self.agent_pnl_multipliers.get(agent.name, 1.0)
                p_i = (m_i / sum_mult) if sum_mult > 0 else (1.0 / M)
                
                # Dynamic allocated capital
                agent.allocated_capital = c_total * (base_pct + p_i * 0.50)
                # Map to capital weight
                agent.capital_weight = agent.allocated_capital / (166666.67 if M == 3 else c_total / M)
                
                # Apply custom floors if needed
                if agent.name == "The Anchor" and category == "bigcap" and detected in (CyclePhase.BEAR, CyclePhase.CHOP):
                    # Ensure Anchor retains a floor weight under stress
                    agent.capital_weight = max(0.3, agent.capital_weight)


    def should_allow_scout(self, confidence: float, rnd: float) -> bool:
        # 50% chance to try low-confidence exploration during early testing
        return rnd < 0.5 or confidence >= 0.55
