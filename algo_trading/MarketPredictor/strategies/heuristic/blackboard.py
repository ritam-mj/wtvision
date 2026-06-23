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
    def __init__(self, enable_locking: bool = False):
        self.order_book = OrderBook()
        self.long_term_locked_symbols = set()  # symbols locked by Anchor
        self.hedge_enabled_symbols = set()  # symbols where short/put against locked longs is allowed
        self.enable_locking = enable_locking

    def register_model_intent(self, intent: TradeIntent):
        if self.enable_locking:
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
        if not self.order_book.pending:
            return output
            
        print(f"\n📊 Blackboard Cross-Agent Delta Analysis (Stock Price: {current_price:.2f}):")
        for intent in self.order_book.pending:
            delta = self.calculate_delta(intent, current_price)
            delta_qty = intent.quantity * delta
            notional = intent.quantity * (intent.strike if intent.strike is not None else current_price)
            print(f"   - Agent: {intent.model_name:<15} | Intent: {intent.side:<5} {intent.quantity:<4} | Delta: {delta:+.3f} | Delta-Eq Qty: {delta_qty:+.2f} | Est Notional: ${notional:,.2f}")
            
        # Group pending intents by portfolio group
        groups = {
            "heur": ["The Anchor", "The Berserker", "The Sentinel"],
            "rl": ["The RL Tactician"],
            "exp": ["The NLP Explorer", "The Quant Explorer"]
        }
        
        categorized = {}
        for intent in self.order_book.pending:
            group_name = "heur"  # Default fallback
            for g, models in groups.items():
                if intent.model_name in models:
                    group_name = g
                    break
            categorized.setdefault((group_name, intent.symbol), []).append(intent)
            
        self.order_book.pending.clear()
        
        for (group_name, symbol), intents in categorized.items():
            # Pass options through directly
            options = [i for i in intents if i.side in ("PUT", "CALL")]
            output.extend(options)
            
            equities = [i for i in intents if i.side in ("BUY", "COVER", "SELL", "SHORT")]
            if not equities:
                continue
                
            total_buy = sum(i.quantity for i in equities if i.side in ("BUY", "COVER"))
            total_sell = sum(i.quantity for i in equities if i.side in ("SELL", "SHORT"))
            
            imbalance = total_buy - total_sell
            
            if imbalance > 0:
                rep = next((i for i in equities if i.side in ("BUY", "COVER")), equities[0])
                output.append(TradeIntent(
                    rep.model_name, symbol, "BUY", imbalance, rep.confidence,
                    f"Netted BUY (imbalance of {total_buy} vs {total_sell})"
                ))
            elif imbalance < 0:
                rep = next((i for i in equities if i.side in ("SELL", "SHORT")), equities[0])
                output.append(TradeIntent(
                    rep.model_name, symbol, "SELL", abs(imbalance), rep.confidence,
                    f"Netted SELL (imbalance of {total_buy} vs {total_sell})"
                ))
                
        return output

