import pytest
import numpy as np
import pandas as pd
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.learning_model.simulator import DigitalTwin
from src.core_engine.market_state import MarketState, CyclePhase
from src.core_engine.protocol import RegimeDetector


def build_sample_history(symbol: str):
    dates = pd.date_range(end=datetime.utcnow(), periods=100)
    np_random = np.random.default_rng(42)
    returns = pd.Series(np_random.normal(0.0005, 0.01, size=100))
    prices = 100 * (1 + returns).cumprod()
    returns = prices.pct_change().fillna(0)
    return pd.DataFrame({"timestamp": dates, "symbol": symbol, "price": prices, "returns": returns})


def test_generate_bull_scenario_contains_bull_phase():
    df = build_sample_history("SPY")
    twin = DigitalTwin(df)
    states = twin.generate("SPY", days=60, scenario="bull")

    assert len(states) == 60
    assert all(isinstance(s, MarketState) for s in states)
    assert any(s.cycle_phase == CyclePhase.BULL for s in states)


def test_generate_bear_scenario_contains_bear_phase():
    df = build_sample_history("SPY")
    twin = DigitalTwin(df)
    states = twin.generate("SPY", days=60, scenario="bear")

    assert len(states) == 60
    assert any(s.cycle_phase == CyclePhase.BEAR for s in states)


def test_generate_chop_scenario_contains_chop_phase():
    df = build_sample_history("SPY")
    twin = DigitalTwin(df)
    states = twin.generate("SPY", days=60, scenario="chop")

    assert len(states) == 60
    assert any(s.cycle_phase == CyclePhase.CHOP for s in states)


def test_generate_flash_crash_has_severe_drop():
    df = build_sample_history("SPY")
    twin = DigitalTwin(df)
    states = twin.generate("SPY", days=60, scenario="flash_crash")

    low_price = min(s.price for s in states)
    high_price = max(s.price for s in states)
    assert low_price / high_price < 0.85


def test_regime_detector_triggers_bear_on_drawdown():
    rd = RegimeDetector(window=10, drawdown_threshold=0.03, volatility_threshold=10)
    base = 100.0

    for i in range(10):
        state = MarketState("SPY", base - i * 1.5, 0.05, CyclePhase.BULL, datetime.utcnow())
        rd.update(state)

    detected = rd.detect(state)
    assert detected == CyclePhase.BEAR
