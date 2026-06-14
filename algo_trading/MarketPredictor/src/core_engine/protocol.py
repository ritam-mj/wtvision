from __future__ import annotations
from collections import deque
from typing import Set, Optional

from src.core_engine.blackboard import Blackboard
from src.core_engine.market_state import MarketState, CyclePhase


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

    def update(self, state: MarketState):
        self.regime.update(state)
        detected = self.regime.detect(state)

        if detected == CyclePhase.BEAR:
            if not self.bear_active:
                self.bear_active = True
                self.blackboard.enable_synthetic_hedge(state.symbol)
                self.market_watch.add(state.symbol)
            return

        if self.bear_active and detected == CyclePhase.BULL:
            self.bear_active = False
            for symbol in list(self.market_watch):
                self.blackboard.disable_synthetic_hedge(symbol)
                self.market_watch.remove(symbol)

    def should_allow_scout(self, confidence: float, rnd: float) -> bool:
        # 50% chance to try low-confidence exploration during early testing
        return rnd < 0.5 or confidence >= 0.55
