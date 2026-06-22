"""
Risk Management Module - Enforces trading limits, stops, and circuit breakers

Provides:
- Position size limits (max % of portfolio per symbol)
- Daily loss limits (circuit breaker if down X% in a day)
- Leverage limits (no borrowing beyond threshold)
- Sector concentration limits
- Order validation before execution
"""

from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RiskConfig:
    """Configuration for risk management thresholds"""
    
    def __init__(self):
        # Position limits
        self.max_position_size_pct = 0.10          # Max 10% of portfolio per symbol
        self.max_sector_exposure_pct = 0.25        # Max 25% per sector
        self.max_correlated_exposure_pct = 0.20    # Max 20% in correlated stocks
        
        # Daily/trading limits
        self.max_daily_loss_pct = 0.02             # Stop trading if lost 2% in a day
        self.max_leverage = 1.5                     # Max 1.5x leverage (50% borrowed)
        self.stop_loss_pct = 0.05                  # Exit positions if down 5%
        
        # Time-decaying stop-loss parameters
        self.stop_loss_base_pct = 0.15             # 15% base stop-loss
        self.stop_loss_min_pct = 0.02              # 2% minimum stop-loss
        self.stop_loss_decay_lambda = 0.15         # Exponential decay factor lambda
        self.stop_loss_profit_scale = 0.2          # Compresses stop-loss by 2% for every 10% gain
        
        # Portfolio limits
        self.min_cash_buffer_pct = 0.05            # Keep minimum 5% in cash
        self.max_trades_per_day = 50               # Circuit breaker on trade count
        
        # Risk flags
        self.trading_halted = False                # Master kill switch
        self.halt_reason = None


class RiskViolation:
    """Represents a risk limit violation"""
    
    def __init__(self, rule: str, severity: str, message: str, action: str = "REJECT"):
        self.rule = rule
        self.severity = severity  # INFO, WARNING, CRITICAL
        self.message = message
        self.action = action      # REJECT, WARN, EXECUTE, HALT
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"[{self.severity}] {self.rule}: {self.message}"


class RiskManager:
    """
    Enforces risk limits on trades and portfolio positions.
    
    Usage:
        config = RiskConfig()
        risk = RiskManager(config, starting_capital=1_000_000)
        
        # Before executing a trade
        violations = risk.validate_trade(symbol, side, quantity, current_price)
        if not violations:
            portfolio.execute(symbol, side, quantity, current_price)
        else:
            for v in violations:
                if v.action == "REJECT":
                    print(f"Trade rejected: {v.message}")
    """
    
    def __init__(self, config: RiskConfig, starting_capital: float):
        self.config = config
        self.starting_capital = starting_capital
        self.starting_nav = starting_capital
        
        # Tracking state
        self.daily_trades = []  # List of trades executed today
        self.daily_loss = 0.0   # Loss realized today
        self.daily_pnl_realized = 0.0
        self.daily_pnl_unrealized = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Active positions metadata for dynamic stop-loss tracking
        self.active_positions_meta = {}  # symbol -> {"entry_step": int, "peak_price": float, "is_long": bool}
        
        # Sector mapping (simplified)
        self.sector_map = {
            'SPY': 'broad',   'QQQ': 'tech',   'IWM': 'smallcap',
            'AAPL': 'tech',   'MSFT': 'tech',  'GOOGL': 'tech',
            'AMZN': 'tech',   'NVDA': 'tech',  'META': 'tech',
            'TSLA': 'auto',   'F': 'auto',     'GM': 'auto',
            'XOM': 'energy',  'CVX': 'energy', 'COP': 'energy',
            'JPM': 'finance', 'BAC': 'finance', 'GS': 'finance',
            'JNJ': 'health',  'PFE': 'health', 'UNH': 'health',
        }
    
    def reset_daily_limits(self):
        """Reset daily counters (call at market open)"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trades = []
            self.daily_loss = 0.0
            self.daily_pnl_realized = 0.0
            self.daily_pnl_unrealized = 0.0
            self.last_reset_date = today
    
    def halt_trading(self, reason: str):
        """Emergency stop - disables all trading"""
        self.config.trading_halted = True
        self.config.halt_reason = reason
        logger.critical(f"[HALT] TRADING HALTED: {reason}")
    
    def resume_trading(self):
        """Resume trading after halt"""
        self.config.trading_halted = False
        self.config.halt_reason = None
        logger.info("✅ Trading resumed")
    
    def validate_trade(self, symbol: str, side: str, quantity: float, 
                      current_price: float, portfolio) -> List[RiskViolation]:
        """
        Validate a proposed trade against all risk rules.
        
        Returns: List of violations (empty if trade is valid)
        """
        violations = []
        self.reset_daily_limits()
        
        # Master kill switch
        if self.config.trading_halted:
            violations.append(RiskViolation(
                "TRADING_HALTED",
                "CRITICAL",
                f"Trading halted: {self.config.halt_reason}",
                action="REJECT"
            ))
            return violations
        
        # Check daily trade count
        if len(self.daily_trades) >= self.config.max_trades_per_day:
            violations.append(RiskViolation(
                "TRADE_COUNT_LIMIT",
                "CRITICAL",
                f"Max {self.config.max_trades_per_day} trades per day exceeded",
                action="REJECT"
            ))
        
        # Check daily loss limit
        current_nav = portfolio.net_asset_value({symbol: current_price})
        daily_return = (current_nav - self.starting_nav) / self.starting_nav
        
        if daily_return < -self.config.max_daily_loss_pct:
            violations.append(RiskViolation(
                "DAILY_LOSS_LIMIT",
                "CRITICAL",
                f"Daily loss {daily_return*100:.2f}% exceeds limit {-self.config.max_daily_loss_pct*100:.2f}%",
                action="HALT"
            ))
            self.halt_trading("Daily loss limit exceeded")
        
        # Check position size (only for BUY/SHORT)
        if side in ("BUY", "SHORT"):
            notional = quantity * current_price
            current_nav = portfolio.net_asset_value({symbol: current_price})
            position_pct = notional / current_nav if current_nav > 0 else 0
            
            if position_pct > self.config.max_position_size_pct:
                violations.append(RiskViolation(
                    "POSITION_SIZE_LIMIT",
                    "CRITICAL",
                    f"Position {position_pct*100:.1f}% exceeds max {self.config.max_position_size_pct*100:.1f}%",
                    action="REJECT"
                ))
        
        # Check minimum cash buffer
        cash_pct = portfolio.cash / (portfolio.net_asset_value({symbol: current_price}) or 1)
        if side == "BUY" and cash_pct < self.config.min_cash_buffer_pct:
            violations.append(RiskViolation(
                "CASH_BUFFER_LOW",
                "WARNING",
                f"Cash {cash_pct*100:.1f}% below minimum {self.config.min_cash_buffer_pct*100:.1f}%",
                action="WARN"
            ))
        
        # Check leverage (not enough cash for trade)
        notional = quantity * current_price
        if side == "BUY" and notional > portfolio.cash:
            violations.append(RiskViolation(
                "INSUFFICIENT_CASH",
                "CRITICAL",
                f"Notional ${notional:,.0f} exceeds cash ${portfolio.cash:,.0f}",
                action="REJECT"
            ))
        
        return violations
    
    def validate_stop_loss(self, symbol: str, position_qty: float, 
                          avg_price: float, current_price: float, current_step: int = 0) -> Optional[RiskViolation]:
        """Check if a position should be stopped out using exponential time-decay trailing stop-loss."""
        import numpy as np
        if position_qty == 0:
            # Clear metadata when position is closed
            self.active_positions_meta.pop(symbol, None)
            return None
            
        is_long = position_qty > 0
        
        # Check if position direction changed or is new
        if symbol not in self.active_positions_meta or self.active_positions_meta[symbol]["is_long"] != is_long:
            self.active_positions_meta[symbol] = {
                "entry_step": current_step,
                "peak_price": current_price,
                "is_long": is_long
            }
            
        meta = self.active_positions_meta[symbol]
        
        # Update peak price trailing boundary
        if is_long:
            meta["peak_price"] = max(meta["peak_price"], current_price)
        else:
            meta["peak_price"] = min(meta["peak_price"], current_price)
            
        # Calculate dynamic stop-loss percentage based on held time and unrealized profit
        time_held = max(0, current_step - meta["entry_step"])
        sl_base = self.config.stop_loss_base_pct
        sl_min = self.config.stop_loss_min_pct
        lam = self.config.stop_loss_decay_lambda
        
        sl_pct = sl_min + (sl_base - sl_min) * np.exp(-lam * time_held)
        
        # Calculate unrealized return to compress stop loss as position moves into profit
        unrealized_return = 0.0
        if is_long:
            if avg_price > 0:
                unrealized_return = (current_price - avg_price) / avg_price
        else:
            if avg_price > 0:
                unrealized_return = (avg_price - current_price) / avg_price
                
        # Scale down sl_pct when profit is positive, using profit_scale
        profit_scale = getattr(self.config, 'stop_loss_profit_scale', 0.5)
        if unrealized_return > 0:
            sl_pct = max(sl_min, sl_pct - profit_scale * unrealized_return)
        
        # Calculate stop trigger price boundaries
        if is_long:
            trigger_price = meta["peak_price"] * (1.0 - sl_pct)
            triggered = current_price < trigger_price
            msg = f"{symbol} Long down to {current_price:.2f}, dynamic SL trigger is {trigger_price:.2f} (base {sl_base*100:.1f}%, current {sl_pct*100:.2f}%, held {time_held} steps)"
        else:
            trigger_price = meta["peak_price"] * (1.0 + sl_pct)
            triggered = current_price > trigger_price
            msg = f"{symbol} Short up to {current_price:.2f}, dynamic SL trigger is {trigger_price:.2f} (base {sl_base*100:.1f}%, current {sl_pct*100:.2f}%, held {time_held} steps)"
            
        if triggered:
            self.active_positions_meta.pop(symbol, None)
            return RiskViolation(
                "DYNAMIC_STOP_LOSS_TRIGGERED",
                "WARNING",
                msg,
                action="EXECUTE"
            )
            
        return None
    
    def log_trade(self, symbol: str, side: str, quantity: float, price: float, pnl: float = 0.0):
        """Record a trade for daily tracking"""
        trade = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'pnl': pnl,
        }
        self.daily_trades.append(trade)
        
        if pnl < 0:
            self.daily_loss += abs(pnl)
        
        logger.info(f"[RISK] Trade logged: {side} {quantity} {symbol} @ ${price:.2f}, PnL ${pnl:+.2f}")
    
    def get_portfolio_stats(self, portfolio) -> Dict:
        """Get risk statistics for current portfolio"""
        current_nav = portfolio.net_asset_value({})
        
        return {
            'nav': current_nav,
            'cash': portfolio.cash,
            'cash_pct': portfolio.cash / current_nav if current_nav > 0 else 0,
            'gross_exposure': sum(abs(pos.quantity * pos.avg_price) for pos in portfolio.positions.values()),
            'realized_pnl': portfolio.realized_pnl,
            'unrealized_pnl': 0.0,  # Would need current prices
            'daily_trades_count': len(self.daily_trades),
            'daily_loss': self.daily_loss,
            'trading_halted': self.config.trading_halted,
        }
    
    def report(self) -> str:
        """Generate a risk report"""
        lines = [
            "\n" + "="*70,
            "[RISK MANAGEMENT REPORT]",
            "="*70,
            f"Trading Halted: {self.config.trading_halted}",
            f"Daily Trades: {len(self.daily_trades)}/{self.config.max_trades_per_day}",
            f"Daily Loss: ${self.daily_loss:,.2f}",
            f"Position Size Limit: {self.config.max_position_size_pct*100:.0f}%",
            f"Daily Loss Limit: {self.config.max_daily_loss_pct*100:.1f}%",
            f"Stop Loss Level: {-self.config.stop_loss_pct*100:.1f}%",
            "="*70,
        ]
        return "\n".join(lines)
