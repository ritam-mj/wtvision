# MarketPredictor - Multi-Agent Autonomous Trading System

**A Python-based blackboard architecture trading system with risk management, persistent state storage, and live dashboard monitoring.**

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Installation & Setup](#installation--setup)
4. [Usage Guide](#usage-guide)
5. [Risk Management](#risk-management)
6. [State Persistence](#state-persistence)
7. [Live Dashboard](#live-dashboard)
8. [Interval Prediction & Integrated Learning](#-interval-prediction--integrated-learning)
9. [Backtesting](#backtesting)
10. [Testing & Verification](#testing--verification)
11. [Deployment Roadmap](#deployment-roadmap)
12. [API Reference](#api-reference)

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone and navigate to project
cd c:\Users\ritam\MarketPredictor

# Install dependencies
pip install numpy pandas yfinance streamlit

# Verify system
python verify_system.py
```

### 2. Run Trading Simulation
```bash
# Bull market scenario (30 days)
python main.py bull 30

# Bear market scenario (20 days)
python main.py bear 20

# Choppy/sideways market (15 days)
python main.py chop 15

# Flash crash scenario (10 days)
python main.py flash_crash 10

# Mixed/random market (default)
python main.py mixed 30
```

### 3. Backtest Historical Performance
```bash
# Last 30 days
python backtest.py 30

# Last 90 days (3 months)
python backtest.py 90

# Last 252 days (1 trading year)
python backtest.py 252

# Last 1260 days (5 trading years)
python backtest.py 1260

# Test other symbols
python backtest.py --symbol AAPL 252
python backtest.py --symbol QQQ 90
```

### 4. Launch Live Dashboard
```bash
# Start dashboard server
streamlit run dashboard.py

# Opens at http://localhost:8501
```

---

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│           MarketPredictor Trading System                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Tactician│  │ Explorer │  │ Sentinel │  │  Anchor  │    │
│  │ (RSI,    │  │ (Probing)│  │(Hedging) │  │(Long-   │    │
│  │ MACD,EMA)│  │          │  │ Options) │  │  term)   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Blackboard Conflict Resolution              │ │
│  │  - Core lock for long-term positions                  │ │
│  │  - Virtual netting for orders                         │ │
│  │  - Confidence-based prioritization                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Risk Manager     │  │ State Persistence│                │
│  │ - Pos limits     │  │ - SQLite DB      │                │
│  │ - Daily stops    │  │ - Trade history  │                │
│  │ - Halts          │  │ - Snapshots      │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Portfolio        │  │ Live Dashboard   │                │
│  │ - Execution      │  │ - Real-time NAV  │                │
│  │ - P&L tracking   │  │ - Position view  │                │
│  │ - History        │  │ - Performance    │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Six Agent Models

| Agent | Strategy | Triggers |
|-------|----------|----------|
| **Tactician** | Technical indicators (RSI, MACD, EMA) | Momentum reversal, trend following, and MACD breakdown exits |
| **Explorer** | Volatility-scaled cluster probing | Low-confidence exploration with dynamic volatility scaling |
| **Sentinel** | Option Hedging (PUT/CALL) | Risk hedging in BEAR regimes and market drawdown phases |
| **Anchor** | Long-term core trend lock | 200-day MA crossover (locks underlying long position) |
| **Treasurer** | Sharpe-based portfolio allocation | High/low Sharpe ratio threshold allocations |
| **MetaOpt** | Drawdown-based global capital allocator | Aggregate realized & unrealized drawdown protection sizing |

#### Detailed Agent Behaviors:

1. **The Tactician**: Trades momentum and trends based on RSI and MACD. In bull regimes, it uses MACD trend breakdown exits (selling if MACD < -0.05) to secure profits early and avoid riding major reversals down. Parameters (like oversold/overbought thresholds) adapt based on trade success.
2. **The Explorer**: Performs low-confidence probing trades using KMeans clustering on rate-of-change (ROC) indicators. It automatically scales its cluster trigger thresholds dynamically using rolling returns standard deviation (normalized to a 1.0% daily volatility baseline) to prevent over-trading in highly volatile regimes.
3. **The Sentinel**: Provides option hedging. In BEAR regimes (detected when drawdown > 7% or volatility > 0.6), it writes CALL or PUT options at strikes relative to the current stock price, executing a 1-day hold options hedging strategy.
4. **The Anchor**: Establishes core long-term holdings using a 200-day Simple Moving Average (SMA) crossover. When the price crosses above the SMA, it locks the position (preventing other agents from selling or shorting unless hedges are enabled), maintaining exposure to long-term secular bull markets.
5. **The Treasurer**: Manages portfolio allocation based on Sharpe ratios calculated over a rolling window. It triggers BUY or SHORT trades when the rolling Sharpe ratio exceeds high or low thresholds, and dynamically adjusts thresholds and trade sizing based on PnL outcomes.
6. **The Meta-Opt**: Acts as a global risk-budgeting supervisor. It continuously tracks the aggregate peak PnL (realized + unrealized) of all other agents. If the current drawdown exceeds a threshold ($10,000), it scales down the trade size multiplier (`quantity_multiplier`) linearly down to a minimum scale of 0.1 at a drawdown limit ($40,000) to protect the portfolio's equity curve. It also adapts these drawdown thresholds during training based on execution outcomes.

### Market Cycle Detection

System automatically detects and trades in:
- **BULL**: Uptrend (price > 20-day EMA)
- **BEAR**: Downtrend (price < 20-day EMA)
- **CHOP**: Sideways (price oscillating)

---

## 📦 Installation & Setup

### Requirements
- Python 3.8+
- pandas, numpy, yfinance
- streamlit (for dashboard)
- sqlite3 (included in Python)

### Step 1: Install Dependencies
```bash
pip install numpy pandas yfinance streamlit
```

### Step 2: Verify Installation
```bash
python verify_system.py
```

Expected output:
```
✓ All modules imported successfully
✓ All core components working
✓ All required files present
✓ Database persistence working
```

### Step 3: Check Database
```bash
# SQLite database auto-created on first run
ls -la portfolio.db

# Verify tables
sqlite3 portfolio.db ".tables"
# Output: portfolio_snapshots risk_events trades
```

---

## 💻 Usage Guide

### Main Script (`main.py`)

**Single Epoch Run** - Run trading strategy on simulated market

```bash
# Default (mixed scenario, 30 days)
python main.py

# Specify scenario and duration
python main.py bull 20
python main.py bear 30
python main.py chop 15
python main.py flash_crash 10

# Disable real data (synthetic only)
# (edit main.py, set include_real_data=False)
```

**Output includes:**
- Trade execution log with timestamps
- Final NAV, cash, realized PnL
- Risk report (daily trades, limits, halts)
- Learner state (parameter optimization history)
- Trade history with per-trade PnL

**Example output:**
```
[Trading] Running agents on 30 market states...
2026-05-01 10:30 | Blackboard -> BUY 100 SPY @ 670.50 (momentum)
2026-05-02 14:15 | Blackboard -> SELL 50 SPY @ 675.25 (profit take)

Final NAV: $1,002,340.50
Realized PnL: $+2,340.50

[RISK MANAGEMENT REPORT]
Trading Halted: False
Daily Trades: 2/50
Daily Loss: $0.00
Position Size Limit: 10%
```

### Backtest Script (`backtest.py`)

**Test historical performance over configurable timespans**

```bash
# Last 30 days
python backtest.py 30

# Last 90 days (3 months)
python backtest.py 90

# Last 252 days (1 trading year)
python backtest.py 252

# Last 1260 days (5 trading years)
python backtest.py 1260

# Other symbols
python backtest.py --symbol AAPL 252
python backtest.py --symbol QQQ 90

# Show help
python backtest.py --help
```

**Output metrics:**
- Market return vs Strategy return
- Alpha (excess return)
- Win rate and trade count
- Max drawdown and Sharpe ratio
- Comparison against benchmark

**Example output:**
```
🎯 MARKET PERFORMANCE (SPY)
Start Price: $670.50
End Price: $713.94
Market Return: +5.48%

💰 STRATEGY PERFORMANCE
Starting Capital: $1,000,000.00
Final NAV: $1,004,935.00
Total Return: +0.49%

[ALPHA] (Excess Return): -4.98%
  Strategy UNDERPERFORMED market by 4.98%
```

### Dashboard Script (`dashboard.py`)

**Real-time portfolio monitoring web interface**

```bash
# Start dashboard
streamlit run dashboard.py

# Opens browser at http://localhost:8501
```

**Features:**
- Portfolio NAV and daily PnL
- Open positions with mark-to-market
- Recent trade history
- Risk metrics and status
- Historical NAV chart
- Learner optimization history

---

## 🛡️ Risk Management

### Risk Manager (`risk_manager.py`)

Enforces hard limits on all trading:

| Limit | Default | Impact |
|-------|---------|--------|
| Position Size | 10% of portfolio | Max loss: 10% × portfolio on any trade |
| Daily Loss | 2% of portfolio | Halt trading if daily loss exceeds 2% |
| Leverage | 1.5x max | Can't borrow more than 50% of portfolio |
| Stop Loss | 5% per position | Auto-exit losing positions |
| Trade Limit | 50/day | Circuit breaker on over-trading |
| Cash Buffer | 5% minimum | Maintain liquidity |

### Portfolio Guards and Option Settlement

- **Cash/Capital Guards**: Enforces strict capital and buying power constraints. If cash is insufficient, BUY, COVER, and option premium orders are rejected to prevent negative cash balances.
- **Option Daily Settlement**: Options (PUT and CALL) are settled on a 1-day rolling basis (1-day hold) or force-settled at the end of simulation. When settled, the intrinsic value of the option is credited to cash, and the trade is logged as `PUT_SETTLE` or `CALL_SETTLE`.
- **NAV Option Valuation**: Open options positions' intrinsic values are dynamically included in the daily portfolio Net Asset Value (NAV) calculation.

### Customizing Risk Limits

Edit `risk_manager.py` (lines 18-30):

```python
class RiskConfig:
    def __init__(self):
        self.max_position_size_pct = 0.10      # Change to 0.15 for 15%
        self.max_daily_loss_pct = 0.02         # Change to 0.05 for 5%
        self.max_leverage = 1.5                # Change to 1.0 for no leverage
        self.stop_loss_pct = 0.05              # Change to 0.03 for 3% stops
        self.max_trades_per_day = 50           # Change as needed
```

### Risk Violation Handling

```python
violations = risk_manager.validate_trade(
    symbol="SPY", 
    side="BUY", 
    quantity=100,
    current_price=670.50,
    portfolio=portfolio
)

if violations:
    for v in violations:
        print(f"[{v.severity}] {v.rule}: {v.message}")
        if v.action == "REJECT":
            # Trade rejected, skip execution
            continue
        if v.action == "HALT":
            # Critical violation, halt all trading
            risk_manager.halt_trading(v.message)
```

---

## 💾 State Persistence

### State Manager (`state_persistence.py`)

Automatically saves portfolio state and trade history to SQLite.

**Features:**
- Auto-save after each trade
- Crash recovery (restore previous state)
- Complete audit trail
- Historical queries

### Database Schema

**Table: portfolio_snapshots**
```sql
CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    nav REAL,              -- Net Asset Value
    cash REAL,             -- Cash balance
    realized_pnl REAL,     -- Realized P&L
    positions_json TEXT,   -- Open positions
    trade_count INTEGER
);
```

**Table: trades**
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    symbol TEXT,
    side TEXT,             -- BUY, SELL, SHORT, COVER, PUT, CALL
    quantity REAL,
    price REAL,
    pnl REAL,              -- Trade P&L
    realized_pnl REAL,     -- Cumulative P&L
    cash REAL
);
```

**Table: risk_events**
```sql
CREATE TABLE risk_events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    rule TEXT,             -- Risk rule name
    severity TEXT,         -- INFO, WARNING, CRITICAL
    message TEXT,
    action TEXT            -- REJECT, WARN, EXECUTE, HALT
);
```

### Using State Manager

```python
from state_persistence import StateManager

# Initialize
state_manager = StateManager(backend='sqlite', db_path='portfolio.db')

# Save portfolio state
state_manager.save(portfolio, nav=1_005_000.0)

# Load latest state
portfolio_data = state_manager.load()
print(f"NAV: ${portfolio_data['nav']:,.2f}")
print(f"Cash: ${portfolio_data['cash']:,.2f}")

# Get history
history = state_manager.get_history(days=7)
for snap in history:
    print(f"{snap['timestamp']}: ${snap['nav']:,.2f}")

# Get trade history
trades = state_manager.get_trades(symbol='SPY', days=1)
for trade in trades:
    print(f"{trade['timestamp']}: {trade['side']} {trade['quantity']} @ ${trade['price']}")
```

### Querying Database

```bash
# Get latest NAV
sqlite3 portfolio.db "SELECT timestamp, nav FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 5;"

# Get all trades for SPY
sqlite3 portfolio.db "SELECT * FROM trades WHERE symbol='SPY';"

# Get risk events
sqlite3 portfolio.db "SELECT timestamp, rule, severity, message FROM risk_events WHERE severity='CRITICAL';"

# Total P&L by scenario
sqlite3 portfolio.db "SELECT 'All Time' as period, SUM(realized_pnl) FROM trades;"
```

---

## 📊 Live Dashboard

### Dashboard Features

**Main Dashboard**
- Portfolio NAV, cash, daily PnL
- Open positions with current prices
- Recent trade history
- Risk configuration status
- Learner state

**Performance Page**
- Historical NAV chart
- Drawdown analysis
- Sharpe ratio, volatility
- Return statistics

**Alerts Page**
- Risk violations
- System events
- Trading halts

### Launching Dashboard

```bash
pip install streamlit yfinance

streamlit run dashboard.py

# Opens at http://localhost:8501
```

### Dashboard Customization

Edit `dashboard.py`:
- Adjust refresh intervals (sidebar)
- Change date ranges for charts
- Customize metrics and KPIs
- Add email alerts (premium feature)

---

## 🔮 Interval Prediction & Integrated Learning

The system includes a state-of-the-art predictive module integrated with the gRPC `StrategyService`, the Spring Boot Java backend, and the graphical user application.

### 1. Multi-Interval Forecast Engine
Query advanced market trend predictions directly from the **Interval Predictor** panel. Supported forecasting intervals include:
- **Intraday**: `5 min`, `1 hour`
- **Swing**: `1 day`, `1 week`
- **Macro / Trend**: `1 month`, `long term`

Predictions leverage dynamically mapped `yfinance` market feeds, combined with **vectorized Jump-Diffusion Monte Carlo simulations** running 1000 simulated paths to estimate target projections, return percentages, and statistical confidence levels.

### 2. Recommended Autosell Targets
For every interval query, the system generates a smart **autosell target price**:
- **Bullish Outlook (BUY)**: Sets a Take-Profit target at 1.5 standard deviations above the current price to lock in statistical high-probability gains.
- **Bearish Outlook (SELL)**: Sets a Stop-Loss target at 1.2 standard deviations below the current price to limit downside momentum.

### 3. Integrated Learning Events Schema
To provide "integrated learning across all users," the system treats every single prediction request, trade signal computation, trade outcome execution, and manual calibration as a persistent database event.
Events are serialized as JSON inputs/outputs and logged in SQLite:
```bash
# Query recent prediction events
sqlite3 portfolio.db "SELECT timestamp, event_type, symbol, user_id FROM learning_events ORDER BY timestamp DESC LIMIT 5;"
```
- **Safety Strategy**: The core model does **not** dynamically shift model parameters dynamically in the background on live trade outcomes to avoid parameter drift. Instead, all outcomes are saved as structured `TRADE_OUTCOME` database records for manual future training.

### 4. Graphical Admin Console
Access the **Admin: Learning System** graphical view directly in the sidebar navigation:
- **Integrated Learning Events Tab**: Inspect cross-user prediction traces and exact gRPC inputs/outputs inside expandable visual cards. Filter by Symbol or Event Type.
- **Calibrations & MSE Curves Tab**: Graphical charts showing Mean Squared Error (MSE) trajectory across calibration runs, scenarios parameter comparisons, and parameter value spreadsheets.
- **Hyperparameter Sensitivity Tab**: Interactive bar charts ranking hyperparameter sensitivity levels (e.g. GARCH volatility, Jump intensity, drift) based on model perturbation analyses.
- **Always-Enabled Manual Calibration Panel**: Allows administrators to input any ticker symbol and lookback period to trigger an immediate GARCH model recalibration loop directly from the UI.

---

## 📈 Backtesting

### Backtest Script (`backtest.py`)

Tests your strategy on real historical data over configurable periods.

**Features:**
- Fetches real market data from Yahoo Finance
- Runs trading strategy through full period
- Calculates detailed performance metrics
- Compares vs market benchmark

### Usage Examples

```bash
# Test different time periods
python backtest.py 30          # Last month
python backtest.py 90          # Last quarter
python backtest.py 252         # Last year
python backtest.py 1260        # Last 5 years

# Test other symbols
python backtest.py --symbol AAPL 252
python backtest.py --symbol QQQ 90
python backtest.py --symbol TLT 252    # Bonds

# Explicit syntax
python backtest.py --days 180
python backtest.py --symbol SPY --days 90
```

### Backtest Output

```
[TIME] TIMESPAN: 3.6 years (898 days)

[MARKET] MARKET PERFORMANCE (SPY)
Start Price: $630.00
End Price: $713.94
Market Return: +105.36%

[STRATEGY] STRATEGY PERFORMANCE
Starting Capital: $1,000,000.00
Final NAV: $2,219,800.00
Total Return: +121.98%

[RISK] RISK METRICS
Max Drawdown: -31.14%
Sharpe Ratio: 1.461

[TRADES] TRADING ACTIVITY
Total Trades: 17
Winning Trades: 6
Win Rate: 35.3%
Avg Trade PnL: $+5,623.00

[RESULT] ALPHA (Excess Return): +16.62%
```

### Interpreting Results

- **Alpha > 0**: Strategy outperformed market ✓
- **Alpha < 0**: Strategy underperformed market
- **Sharpe > 1.0**: Excellent risk-adjusted return
- **Win Rate**: % of profitable trades
- **Max Drawdown**: Largest peak-to-trough decline

---

## ✅ Testing & Verification

### System Verification

```bash
# Run comprehensive system check
python verify_system.py
```

Verifies:
- All modules import correctly
- Core components functional
- All required files present
- Database persistence working
- Risk management system active

**Expected output:**
```
✓ All modules imported successfully
✓ All core components working
✓ All required files present
✓ Database persistence working
✓ VERIFICATION COMPLETE
```

### Running Scenarios

```bash
# Bull scenario
python main.py bull 20

# Bear scenario
python main.py bear 30

# Chop/sideways
python main.py chop 15

# Flash crash
python main.py flash_crash 10

# All scenarios should complete without errors
```

### Backtest Verification

```bash
# Test all timespans work
python backtest.py 30
python backtest.py 90
python backtest.py 252
python backtest.py 1260

# Test other symbols
python backtest.py --symbol AAPL 90
python backtest.py --symbol QQQ 252
```

### Unit Tests

```bash
# Run pytest on simulator tests
pytest tests/test_simulator.py -v

# Run real data tests
python test_real_data.py
```

---

## 🚀 Deployment Roadmap

### Phase 1: Current (Risk + State + Dashboard) ✓
- ✓ Risk management with stops and limits
- ✓ Persistent state storage to SQLite
- ✓ Live monitoring dashboard
- ✓ Comprehensive backtesting

### Phase 2: Broker Integration (Next)
- [ ] Connect to broker API (Interactive Brokers, Alpaca, etc.)
- [ ] Replace Yahoo Finance with live market data
- [ ] Execute real/paper trades
- [ ] Handle order rejections

### Phase 3: Cloud Deployment (After Phase 2)
- [ ] AWS Lambda or VPS for 24/5 trading
- [ ] Automated crash recovery
- [ ] Email/SMS alerting
- [ ] Database backups

### Phase 4: Advanced Features (Future)
- [ ] Multi-symbol portfolio
- [ ] Sector correlation analysis
- [ ] Machine learning model integration
- [ ] Advanced performance reporting

---

## 📚 API Reference

### Market State

```python
from market_state import MarketState, CyclePhase

state = MarketState(
    timestamp=datetime.now(),
    symbol="SPY",
    price=670.50,
    returns=0.005,
    volatility=0.012,
    cycle_phase=CyclePhase.BULL
)

# Access properties
print(state.price)
print(state.cycle_phase.name)  # 'BULL', 'BEAR', 'CHOP'
```

### Trade Intent

```python
from market_state import TradeIntent

intent = TradeIntent(
    agent_name="Tactician",
    symbol="SPY",
    side="BUY",              # BUY, SELL, SHORT, COVER, PUT, CALL
    quantity=100,
    confidence=0.85,
    rationale="RSI oversold"
)
```

### Portfolio

```python
from execution import Portfolio

portfolio = Portfolio(cash=1_000_000.0)

# Execute trades
portfolio.execute("SPY", "BUY", 100, 670.50)
portfolio.execute("SPY", "SELL", 50, 675.25)

# Get metrics
nav = portfolio.net_asset_value({"SPY": 680.00})
unrealized = portfolio.get_unrealized_pnl({"SPY": 680.00})
daily_pnl = portfolio.get_daily_pnl()

# Get history
history = portfolio.get_trade_history()
```

### Risk Manager

```python
from risk_manager import RiskConfig, RiskManager

config = RiskConfig()
risk = RiskManager(config, starting_capital=1_000_000.0)

# Validate trade
violations = risk.validate_trade("SPY", "BUY", 100, 670.50, portfolio)
if not violations:
    portfolio.execute("SPY", "BUY", 100, 670.50)
    risk.log_trade("SPY", "BUY", 100, 670.50)

# Check stop loss
stop_violation = risk.validate_stop_loss("SPY", 100, 670.50, 630.00)
if stop_violation:
    print(f"Stop loss: {stop_violation.message}")
```

### State Manager

```python
from state_persistence import StateManager

state = StateManager(backend='sqlite')

# Save state
state.save(portfolio, nav=1_005_000.0)

# Load state
data = state.load()

# Get history
history = state.get_history(days=7)
trades = state.get_trades(symbol='SPY', days=1)
```

---

## 📁 File Structure

```
MarketPredictor/
├── main.py                          # Main trading loop
├── backtest.py                      # Historical backtest
├── dashboard.py                     # Live monitoring dashboard
├── verify_system.py                 # System verification
│
├── agents.py                        # 6 agent models
├── blackboard.py                    # Conflict resolution
├── market_state.py                  # Data classes
├── protocol.py                      # Regime detection
├── simulator.py                     # Market simulation
├── execution.py                     # Portfolio execution
├── learning_module/                 # Strategy learning module
│   └── learning.py                  # Learning & optimization
├── risk_manager.py                  # Risk limits & stops
├── state_persistence.py             # SQLite persistence
├── kite-java-backend/               # Java backend for Zerodha Kite API
│
├── tests/
│   └── test_simulator.py            # Simulator tests
├── test_real_data.py                # Real data tests
├── test_fetch_debug.py              # Data fetch debugging
│
├── README.md                        # This file
├── portfolio.db                     # SQLite database (auto-created)
└── learner_state.json               # Optimization parameters
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Optional: Set log level
export LOG_LEVEL=INFO

# Optional: Set database path
export DB_PATH=/path/to/portfolio.db
```

### Configuration Files

**learner_state.json** - Optimization parameters from previous runs
**portfolio.db** - SQLite database with trade history

---

## 🐛 Troubleshooting

### Issue: Unicode Encoding Errors

**Problem:** Special characters not displaying correctly
**Solution:** Set encoding in terminal
```bash
# Windows PowerShell
$env:PYTHONIOENCODING='utf-8'

# Linux/Mac
export PYTHONIOENCODING=utf-8
```

### Issue: Yahoo Finance Connection Failed

**Problem:** Can't fetch real market data
**Solution:** Check internet connection and firewall
```bash
# Test connectivity
python -c "import yfinance; print(yfinance.Ticker('SPY').history(period='1d'))"
```

### Issue: Database Locked

**Problem:** SQLite database locked error
**Solution:** Close all connections and restart
```bash
# Close dashboard
# Kill all Python processes
# Restart
```

### Issue: Missing Dependencies

**Problem:** ModuleNotFoundError for pandas, numpy, etc.
**Solution:** Install dependencies
```bash
pip install numpy pandas yfinance streamlit
```

---

## 📞 Support & Next Steps

### Quick Reference

| Task | Command |
|------|---------|
| Verify System | `python verify_system.py` |
| Run Trading | `python main.py bull 30` |
| Backtest | `python backtest.py 252` |
| Dashboard | `streamlit run dashboard.py` |
| Check DB | `sqlite3 portfolio.db` |

### Next Phase: Broker Integration

To connect to a real broker:

1. Choose broker (Interactive Brokers, Alpaca, TD Ameritrade)
2. Create `broker_interface.py` wrapper
3. Replace `execution.py` calls with broker API
4. Test with paper trading first
5. Deploy to cloud (AWS/VPS)

---

## 📜 License & Attribution

Pentagon Ecosystem - Multi-Agent Autonomous Trading System
Created: 2026
Status: Production-Ready (Risk Management + Dashboard)

---

**Last Updated:** May 1, 2026  
**System Status:** ✓ All Tests Passing

### Blackboard Conflict Resolution & Netting

- **Relaxed Netting**: Previously, opposing agent trades were netted out at the Blackboard level into a single net order. This netting has been relaxed to forward and execute individual agent intents separately. This preserves distinct agent names/identities for proper logging, trade-tracking, and parameter adaptation, while still respecting core trading locks.
- **Delta-Equivalent Cross-Agent Trade Analysis**: Preserved trade intents are evaluated using a delta-equivalency framework before execution. The system calculates and logs the delta-equivalent quantity (1.0 for BUY/COVER, -1.0 for SELL/SHORT, and strike-dependent sigmoidal delta estimates for options: CALL option delta ~ `1 / (1 + (strike/price)^2)` and PUT option delta ~ `-1 / (1 + (price/strike)^2)`). This provides cross-agent comparison of position exposures.
- **Core Lock**: Prevents strategic position de-risking by agents other than the Anchor. Once the Anchor declares a BUY, the underlying position is locked, forbidding other agents from issuing SELL orders, and preventing SHORT or PUT trades unless synthetic hedging is explicitly enabled.
- **Hedge Gating**: Synthetic hedging (SHORT, PUT) is only available when a bear regime is detected (drawdown > 7% or volatility > 0.6).

### Learning System

#### SimulatorLearner (in simulator.py)
- Tracks historical outcomes per scenario: maps (scenario, params) → (MSE, final_price).
- Suggests adaptive parameters via 30/70 blend: 30% from best-performing historical params, 70% from base.
- Enables "learning-on-simulator": dynamic parameter adjustment across repeated scenario generations.

#### ShadowTrader (in learning.py)
- Replays agents through generated price histories to measure strategy performance.
- Collects metrics: NAV, realized PnL, trade count, price change per scenario.
- Runs on ensemble of 2-5 scenarios to average out variance.

#### HyperparameterAnalyzer (in learning.py)
- Baseline performance: runs strategy N times with default parameters, computes average PnL.
- Perturbation measurement: ±20% perturb each hyperparameter, re-run, measure impact.
- Sensitivity ranking: importance = |perturbed_pnl - baseline_pnl| / max_impact, normalized to [0, 1].

## Requirements

- Python 3.10+
- pandas
- numpy
- scikit-learn (optional, for KMeans fallback)

## Notes

- Designed for extensibility: agents can be replaced with real ML models, indicators can be enhanced.
- Numeric stability: History generation guards against inf/nan via direct return sampling → cumprod.
- Trade accountability: Every trade logged with cash/PnL snapshots for post-epoch analysis.
- Regime-driven: Bear/bull detection triggers hedging availability; cycle phases guide fallback logic.
- Learning-ready: Full framework for adaptive parameter discovery across scenarios.


##to do

📋 Quick Priority Checklist
Essential before live trading:

 Broker API integration complete (paper trading tested)
 Position size limits enforced (max 10% per symbol)
 Daily loss limits implemented (stop if -2% daily)
 Slippage/fees modeled in strategy
 Paper trading for 2+ weeks with real data
 Order rejection handling implemented
 Portfolio state saved to persistent storage
 Real-time alerting system working
 Manual kill-switch available (to stop all trading instantly)
 Audit log of all trades for 1 year
