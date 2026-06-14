from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CyclePhase(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    CHOP = "CHOP"


@dataclass(frozen=True)
class MarketState:
    symbol: str
    price: float
    volatility: float
    cycle_phase: CyclePhase
    timestamp: datetime


@dataclass
class TradeIntent:
    model_name: str
    symbol: str
    side: str  # BUY, SELL, SHORT, COVER, PUT
    quantity: float
    confidence: float
    reason: str = ""
