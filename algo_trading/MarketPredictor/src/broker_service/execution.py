from dataclasses import dataclass
from typing import Dict
from datetime import datetime

import numpy as np


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float


class Portfolio:
    def __init__(self, cash: float = 1_000_000.0):
        self.starting_capital = cash
        self.cash = cash
        self.positions: Dict[str, Position] = {}
        self.option_positions: list = []  # tuple(symbol, side, strike, quantity, entry_price)
        self.realized_pnl = 0.0
        self.trade_history: list[Dict] = []
        self.created_at = datetime.now()
        self.daily_pnl = 0.0  # Track PnL within a day

    def _record_trade(self, symbol: str, side: str, quantity: float, price: float, pnl: float = 0.0):
        self.trade_history.append({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "trade_pnl": pnl,
        })

    def execute(self, symbol: str, side: str, quantity: float, price: float):
        if quantity <= 0 or not np.isfinite(price) or price <= 0:
            return

        notional = quantity * price
        if side == "BUY":
            self.cash -= notional
            if symbol in self.positions:
                pos = self.positions[symbol]
                new_qty = pos.quantity + quantity
                pos.avg_price = ((pos.avg_price * pos.quantity) + notional) / new_qty
                pos.quantity = new_qty
            else:
                self.positions[symbol] = Position(symbol, quantity, price)
            self._record_trade(symbol, side, quantity, price, pnl=0.0)

        elif side == "SELL":
            if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                return
            pos = self.positions[symbol]
            self.cash += notional
            pnl = (price - pos.avg_price) * quantity
            self.realized_pnl += pnl
            pos.quantity -= quantity
            if pos.quantity == 0:
                del self.positions[symbol]
            self._record_trade(symbol, side, quantity, price, pnl)

        elif side == "SHORT":
            self.cash += notional
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.quantity -= quantity
            else:
                self.positions[symbol] = Position(symbol, -quantity, price)
            self._record_trade(symbol, side, quantity, price, pnl=0.0)

        elif side == "COVER":
            if symbol not in self.positions or self.positions[symbol].quantity >= 0:
                return
            pos = self.positions[symbol]
            close_qty = min(quantity, -pos.quantity)
            self.cash -= close_qty * price
            pnl = (pos.avg_price - price) * close_qty
            self.realized_pnl += pnl
            pos.quantity += close_qty
            if pos.quantity == 0:
                del self.positions[symbol]
            self._record_trade(symbol, side, close_qty, price, pnl)

        elif side in ("PUT", "CALL"):
            premium = price * 0.005 * quantity
            self.cash -= premium
            self.option_positions.append((symbol, side, price, quantity, premium))
            self._record_trade(symbol, side, quantity, price, pnl=-premium)

    def settle_options(self, market_price: float):
        for symbol, side, strike, quantity, premium in self.option_positions:
            if side == "PUT":
                intrinsic = max(strike - market_price, 0.0) * quantity
            else:
                intrinsic = max(market_price - strike, 0.0) * quantity
            pnl = intrinsic - premium
            self.realized_pnl += pnl
            self.cash += intrinsic
            self._record_trade(symbol, side + "_SETTLE", quantity, market_price, pnl)

        self.option_positions.clear()

    def close_all(self, market_prices: Dict[str, float]):
        for symbol, pos in list(self.positions.items()):
            price = market_prices.get(symbol, pos.avg_price)
            if pos.quantity > 0:
                self.execute(symbol, "SELL", pos.quantity, price)
            elif pos.quantity < 0:
                self.execute(symbol, "COVER", -pos.quantity, price)

    def get_trade_history(self):
        return self.trade_history

    def net_asset_value(self, market_prices: Dict[str, float]) -> float:
        nav = self.cash
        for symbol, pos in self.positions.items():
            price = market_prices.get(symbol, pos.avg_price)
            nav += pos.quantity * price
        return nav
    
    def get_unrealized_pnl(self, market_prices: Dict[str, float] = None) -> float:
        """Calculate unrealized PnL from open positions"""
        if not market_prices:
            return 0.0
        
        unrealized = 0.0
        for symbol, pos in self.positions.items():
            if pos.quantity == 0:
                continue
            price = market_prices.get(symbol, pos.avg_price)
            unrealized += (price - pos.avg_price) * pos.quantity
        return unrealized
    
    def get_daily_pnl(self) -> float:
        """Get PnL realized today"""
        return self.realized_pnl
    
    def get_gross_exposure(self) -> float:
        """Get total notional exposure (sum of absolute position values)"""
        exposure = 0.0
        for pos in self.positions.values():
            exposure += abs(pos.quantity * pos.avg_price)
        return exposure
    
    def get_net_exposure(self) -> float:
        """Get net notional exposure (accounting for shorts)"""
        exposure = 0.0
        for pos in self.positions.values():
            exposure += pos.quantity * pos.avg_price
        return exposure

