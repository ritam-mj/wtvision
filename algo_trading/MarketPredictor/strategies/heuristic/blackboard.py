from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict

from strategies.heuristic.marketstate import TradeIntent


@dataclass
class OrderBook:
    pending: List[TradeIntent] = field(default_factory=list)


class CoreLockViolation(Exception):
    pass


class Blackboard:
    def __init__(self):
        self.order_book = OrderBook()
        self.long_term_locked_symbols = set()  # symbols locked by Anchor
        self.hedge_enabled_symbols = set()  # symbols where short/put against locked longs is allowed

    def register_model_intent(self, intent: TradeIntent):
        if intent.symbol in self.long_term_locked_symbols and intent.side == "SELL":
            raise CoreLockViolation(
                f"Core Lock: {intent.model_name} cannot SELL locked symbol {intent.symbol}"
            )
        if intent.symbol in self.long_term_locked_symbols and intent.side in ("SHORT", "PUT"):
            if intent.symbol not in self.hedge_enabled_symbols:
                raise CoreLockViolation(
                    f"Hedge Lock: {intent.model_name} cannot {intent.side} locked symbol {intent.symbol} without hedge permit"
                )
        self.order_book.pending.append(intent)

    def lock_long_term(self, symbol: str):
        self.long_term_locked_symbols.add(symbol)

    def unlock_long_term(self, symbol: str):
        self.long_term_locked_symbols.discard(symbol)

    def enable_synthetic_hedge(self, symbol: str):
        self.hedge_enabled_symbols.add(symbol)

    def disable_synthetic_hedge(self, symbol: str):
        self.hedge_enabled_symbols.discard(symbol)

    def calculate_delta(self, intent: TradeIntent, current_price: float) -> float:
        side = intent.side
        strike = intent.strike if intent.strike is not None else current_price
        
        if side in ("BUY", "COVER"):
            return 1.0
        elif side in ("SELL", "SHORT"):
            return -1.0
        elif side == "CALL":
            # Sigmoid approximation: 1 / (1 + (strike/price)^2)
            ratio = strike / current_price
            return 1.0 / (1.0 + ratio * ratio)
        elif side == "PUT":
            # Sigmoid approximation: -1 / (1 + (price/strike)^2)
            ratio = current_price / strike
            return -1.0 / (1.0 + ratio * ratio)
        return 0.0

    def resolve(self, current_price: float = 100.0) -> List[TradeIntent]:
        output: List[TradeIntent] = []
        
        # Log and compare pending trade intents using delta-equivalency
        if self.order_book.pending:
            print(f"\n📊 Blackboard Cross-Agent Delta Analysis (Stock Price: {current_price:.2f}):")
            for intent in self.order_book.pending:
                delta = self.calculate_delta(intent, current_price)
                delta_qty = intent.quantity * delta
                notional = intent.quantity * (intent.strike if intent.strike is not None else current_price)
                print(f"   - Agent: {intent.model_name:<15} | Intent: {intent.side:<5} {intent.quantity:<4} | Delta: {delta:+.3f} | Delta-Eq Qty: {delta_qty:+.2f} | Est Notional: ${notional:,.2f}")
                
                # Double-check locks
                if intent.symbol in self.long_term_locked_symbols:
                    if intent.side == "SELL":
                        continue
                    if intent.side in ("SHORT", "PUT") and intent.symbol not in self.hedge_enabled_symbols:
                        continue
                output.append(intent)
                
        self.order_book.pending.clear()
        return output
