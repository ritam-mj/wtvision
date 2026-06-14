from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict

from src.core_engine.market_state import TradeIntent


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

    def resolve(self) -> List[TradeIntent]:
        # Virtual netting: aggregate by symbol and side
        net: Dict[str, Dict[str, float]] = {}
        best_intents: Dict[str, TradeIntent] = {}

        for intent in self.order_book.pending:
            key = (intent.symbol, intent.side)
            if key not in net:
                net[key] = 0.0
            net[key] += intent.quantity
            # keep highest confidence intent for reason logging
            if key not in best_intents or intent.confidence > best_intents[key].confidence:
                best_intents[key] = intent

        output: List[TradeIntent] = []
        for symbol in {i.symbol for i in self.order_book.pending}:
            # core long-term lock: sell of locked positions is forbidden
            buy_amt = net.get((symbol, "BUY"), 0.0)
            sell_amt = net.get((symbol, "SELL"), 0.0)
            short_amt = net.get((symbol, "SHORT"), 0.0)
            cover_amt = net.get((symbol, "COVER"), 0.0)
            put_amt = net.get((symbol, "PUT"), 0.0)
            call_amt = net.get((symbol, "CALL"), 0.0)

            # net underlying position (BUY/SELL)
            net_underlying = buy_amt - sell_amt
            if symbol in self.long_term_locked_symbols and net_underlying < 0:
                net_underlying = 0.0

            if net_underlying > 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="BUY",
                    quantity=net_underlying,
                    confidence=1.0,
                    reason="Virtual netting"
                ))
            elif net_underlying < 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="SELL",
                    quantity=-net_underlying,
                    confidence=1.0,
                    reason="Virtual netting"
                ))

            # net short exposure
            net_short = short_amt - cover_amt
            if symbol in self.long_term_locked_symbols and symbol not in self.hedge_enabled_symbols:
                net_short = 0.0

            if net_short > 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="SHORT",
                    quantity=net_short,
                    confidence=1.0,
                    reason="Virtual netting"
                ))
            elif net_short < 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="COVER",
                    quantity=-net_short,
                    confidence=1.0,
                    reason="Virtual netting"
                ))

            # net optional derivatives (PUT/CALL) as separate signals
            net_put = put_amt - call_amt
            if symbol in self.long_term_locked_symbols and symbol not in self.hedge_enabled_symbols:
                net_put = 0.0

            if net_put > 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="PUT",
                    quantity=net_put,
                    confidence=1.0,
                    reason="Virtual netting"
                ))
            elif net_put < 0:
                output.append(TradeIntent(
                    model_name="Blackboard",
                    symbol=symbol,
                    side="CALL",
                    quantity=-net_put,
                    confidence=1.0,
                    reason="Virtual netting"
                ))

        self.order_book.pending.clear()
        return output
