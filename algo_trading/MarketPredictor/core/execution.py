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
        self.option_positions: list = []  # list of [symbol, side, strike, quantity, premium, age]
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
        
        # Cash/Buying power guard
        if side == "BUY" and self.cash < notional:
            # pass  # print(f"⚠️ Rejecting BUY order of {quantity} {symbol} due to insufficient cash (${self.cash:,.2f} < ${notional:,.2f})")
            return
        if side == "COVER" and symbol in self.positions:
            close_qty = min(quantity, -self.positions[symbol].quantity)
            if self.cash < close_qty * price:
                # pass  # print(f"⚠️ Rejecting COVER order of {close_qty} {symbol} due to insufficient cash (${self.cash:,.2f} < ${close_qty * price:,.2f})")
                return

        if side == "BUY":
            self.cash -= notional
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.quantity < 0:
                    # Covering a short position with a BUY
                    cover_qty = min(quantity, -pos.quantity)
                    pnl = (pos.avg_price - price) * cover_qty
                    self.realized_pnl += pnl
                    remaining = quantity - cover_qty
                    pos.quantity += cover_qty
                    if pos.quantity == 0:
                        if remaining > 0:
                            # Flip to long with remainder
                            pos.avg_price = price
                            pos.quantity = remaining
                        else:
                            del self.positions[symbol]
                    self._record_trade(symbol, side, quantity, price, pnl)
                else:
                    # Adding to existing long position
                    new_qty = pos.quantity + quantity
                    pos.avg_price = ((pos.avg_price * pos.quantity) + notional) / new_qty
                    pos.quantity = new_qty
                    self._record_trade(symbol, side, quantity, price, pnl=0.0)
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
                if pos.quantity > 0:
                    # Selling a long position with a SHORT
                    sell_qty = min(quantity, pos.quantity)
                    pnl = (price - pos.avg_price) * sell_qty
                    self.realized_pnl += pnl
                    remaining = quantity - sell_qty
                    pos.quantity -= sell_qty
                    if pos.quantity == 0:
                        if remaining > 0:
                            # Flip to short with remainder
                            pos.avg_price = price
                            pos.quantity = -remaining
                        else:
                            del self.positions[symbol]
                    self._record_trade(symbol, side, quantity, price, pnl)
                else:
                    # Adding to existing short position — weighted avg
                    old_short_qty = -pos.quantity
                    new_short_qty = old_short_qty + quantity
                    pos.avg_price = ((pos.avg_price * old_short_qty) + notional) / new_short_qty
                    pos.quantity = -new_short_qty
                    self._record_trade(symbol, side, quantity, price, pnl=0.0)
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
            if self.cash < premium:
                print(f"⚠️ Rejecting {side} order of {quantity} {symbol} due to insufficient cash for premium (${self.cash:,.2f} < ${premium:,.2f})")
                return
            self.cash -= premium
            self.option_positions.append([symbol, side, price, quantity, premium, 0])
            self._record_trade(symbol, side, quantity, price, pnl=-premium)

    def settle_options_daily(self, market_price: float):
        """Settle options that have been held for at least 1 day (age >= 1) and increment age of others."""
        remaining = []
        for opt in self.option_positions:
            symbol, side, strike, quantity, premium, age = opt
            if age >= 1:
                # Settle option
                if side == "PUT":
                    intrinsic = max(strike - market_price, 0.0) * quantity
                else:
                    intrinsic = max(market_price - strike, 0.0) * quantity
                pnl = intrinsic - premium
                self.realized_pnl += pnl
                self.cash += intrinsic
                self._record_trade(symbol, side + "_SETTLE", quantity, market_price, pnl)
            else:
                # Increment age to settle on the next day
                opt[5] += 1
                remaining.append(opt)
        self.option_positions = remaining

    def settle_options(self, market_price: float):
        """Force-settle all remaining options at the end of the backtest."""
        for opt in self.option_positions:
            symbol, side, strike, quantity, premium, age = opt
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
        
        # Include intrinsic value of open option positions in daily NAV
        for opt in self.option_positions:
            symbol, side, strike, quantity, premium, age = opt
            current_price = market_prices.get(symbol, strike)
            if side == "PUT":
                intrinsic = max(strike - current_price, 0.0) * quantity
            else:
                intrinsic = max(current_price - strike, 0.0) * quantity
            nav += intrinsic
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

