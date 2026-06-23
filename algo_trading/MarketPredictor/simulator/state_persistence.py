"""
Persistent State Management - Save and restore portfolio state to/from storage

Supports:
- JSON file-based storage (development)
- PostgreSQL database (production-ready, schema-driven)
- Automatic crash recovery
- Portfolio snapshots and history
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import os
import psycopg2
from psycopg2.extras import RealDictCursor

from core.utils.config import DBConfig

logger = logging.getLogger(__name__)


class PortfolioSnapshot:
    """Represents a point-in-time portfolio state"""
    
    def __init__(self, timestamp: datetime, nav: float, cash: float, 
                 positions: Dict, realized_pnl: float, trade_count: int):
        self.timestamp = timestamp
        self.nav = nav
        self.cash = cash
        self.positions = positions
        self.realized_pnl = realized_pnl
        self.trade_count = trade_count
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'nav': self.nav,
            'cash': self.cash,
            'positions': self.positions,
            'realized_pnl': self.realized_pnl,
            'trade_count': self.trade_count,
        }


class StateManager:
    """
    Manages persistent storage of portfolio state.
    
    Supports both JSON (simple) and PostgreSQL (production) backends.
    Note: SQLite requests are automatically redirected to PostgreSQL.
    """
    
    # Class-level cache: None = unknown, True = offline, False = online
    _db_offline = None
    
    def __init__(self, backend: str = 'postgres', db_path: str = None, json_path: str = 'portfolio_state.json'):
        # For backward compatibility, if sqlite is requested, redirect to postgres
        if backend in ('sqlite', 'postgres'):
            self.backend = 'postgres'
            self._init_postgres()
        elif backend == 'json':
            self.backend = 'json'
            self.json_path = json_path
        else:
            raise ValueError(f"Unknown backend: {backend}")
        
        logger.info(f"StateManager initialized with {self.backend} backend")
        
    def _get_connection(self):
        """Establish connection to PostgreSQL and set the target search path schema"""
        params = DBConfig.get_connection_params()
        params["connect_timeout"] = 3
        conn = psycopg2.connect(**params)
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {DBConfig.DB_SCHEMA};")
            cursor.execute(f"SET search_path TO {DBConfig.DB_SCHEMA};")
        conn.commit()
        return conn
    
    def _init_postgres(self):
        """Initialize PostgreSQL database schema and indexes"""
        if StateManager._db_offline is True:
            self.db_connected = False
            logger.warning("PostgreSQL database connection marked as offline (skipped reconnect)")
            return
            
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Portfolio snapshots table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    nav DOUBLE PRECISION NOT NULL,
                    cash DOUBLE PRECISION NOT NULL,
                    realized_pnl DOUBLE PRECISION NOT NULL,
                    positions_json JSONB NOT NULL,
                    trade_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Trades table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    symbol VARCHAR(12) NOT NULL,
                    side VARCHAR(12) NOT NULL,
                    quantity DOUBLE PRECISION NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    pnl DOUBLE PRECISION,
                    realized_pnl DOUBLE PRECISION,
                    cash DOUBLE PRECISION,
                    trade_type VARCHAR(20) DEFAULT 'simulation',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Upgrade existing table dynamically if it already exists
                cursor.execute("""
                ALTER TABLE trades ADD COLUMN IF NOT EXISTS trade_type VARCHAR(20) DEFAULT 'simulation';
                """)
                cursor.execute("""
                ALTER TABLE trades ADD COLUMN IF NOT EXISTS agent_name VARCHAR(50) DEFAULT 'system';
                """)
                
                # Agent parameters table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_parameters (
                    agent_name VARCHAR(50) PRIMARY KEY,
                    parameters_json JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # 1. Prune obsolete agent parameters
                cursor.execute("""
                DELETE FROM agent_parameters 
                WHERE agent_name IN ('The Explorer', 'The Meta-Opt', 'The Treasurer')
                """)

                # 2. Initialize default parameters for the new agents if they do not exist
                default_nlp_params = {
                    "pos_threshold": 0.50,
                    "neg_threshold": 0.50,
                    "trade_qty": 10.0,
                    "trade_conf": 0.80,
                    "sentiment_decay": 0.90
                }
                default_quant_params = {
                    "max_debt_ratio": 2.0,
                    "min_growth_rate": 0.05,
                    "pe_undervalued": 15.0,
                    "trade_qty": 15.0,
                    "trade_conf": 0.85
                }
                default_cap_manager_params = {
                    "drawdown_threshold": 10000.0,
                    "drawdown_limit": 40000.0,
                    "min_scale": 0.1,
                    "sharpe_window": 30.0,
                    "sharpe_high": 0.2,
                    "sharpe_low": -0.2,
                    "buy_qty": 3.0,
                    "buy_conf": 0.65,
                    "sell_qty": 2.0,
                    "sell_conf": 0.60
                }

                for agent_name, params in [
                    ("The NLP Explorer", default_nlp_params),
                    ("The Quant Explorer", default_quant_params),
                    ("The Capital Manager", default_cap_manager_params)
                ]:
                    cursor.execute("""
                    INSERT INTO agent_parameters (agent_name, parameters_json, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (agent_name) DO NOTHING
                    """, (agent_name, json.dumps(params)))


                
                # Risk events table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    rule VARCHAR(50) NOT NULL,
                    severity VARCHAR(12) NOT NULL,
                    message TEXT,
                    action VARCHAR(12),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Learning events table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    symbol VARCHAR(12) NOT NULL,
                    user_id VARCHAR(50) NOT NULL,
                    input_details JSONB NOT NULL,
                    output_details JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Model parameters table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_parameters (
                    symbol VARCHAR(12) PRIMARY KEY,
                    parameters_json JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON portfolio_snapshots(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_events_timestamp ON learning_events(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_events_type ON learning_events(event_type)")
                
            conn.commit()
            conn.close()
            self.db_connected = True
            StateManager._db_offline = False
            logger.info("PostgreSQL database initialized successfully")
            
            # Auto-sync local backups to PostgreSQL
            self.sync_local_backups_to_db()
        except Exception as e:
            self.db_connected = False
            StateManager._db_offline = True
            logger.warning(f"PostgreSQL database connection/initialization offline: {e}")

    def sync_local_backups_to_db(self):
        """Sync local JSON parameter files to PostgreSQL database if online"""
        if not getattr(self, 'db_connected', False):
            return
            
        # 1. Sync agent parameters
        try:
            agent_path = Path("agent_parameters.json")
            if agent_path.exists():
                with open(agent_path, 'r') as f:
                    agent_data = json.load(f)
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    # Clean up database obsolete records
                    cursor.execute("""
                    DELETE FROM agent_parameters 
                    WHERE agent_name IN ('The Explorer', 'The Meta-Opt', 'The Treasurer')
                    """)
                    for agent_name, params in agent_data.items():
                        if agent_name in ('The Explorer', 'The Meta-Opt', 'The Treasurer'):
                            continue
                        cursor.execute("""
                        INSERT INTO agent_parameters (agent_name, parameters_json, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (agent_name) DO UPDATE 
                        SET parameters_json = EXCLUDED.parameters_json, updated_at = CURRENT_TIMESTAMP
                        """, (agent_name, json.dumps(params)))
                conn.commit()
                conn.close()
                logger.info("Auto-sync complete: Local agent parameters pushed to PostgreSQL.")
        except Exception as e:
            logger.error(f"Failed to auto-sync local agent parameters to PostgreSQL: {e}")

        # 2. Sync learner states (model parameters)
        try:
            model_path = Path("model_parameters.json")
            if model_path.exists():
                with open(model_path, 'r') as f:
                    model_data = json.load(f)
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    for symbol, state_dict in model_data.items():
                        cursor.execute("""
                        INSERT INTO model_parameters (symbol, parameters_json, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (symbol) DO UPDATE 
                        SET parameters_json = EXCLUDED.parameters_json, updated_at = CURRENT_TIMESTAMP
                        """, (symbol, json.dumps(state_dict)))
                conn.commit()
                conn.close()
                logger.info("Auto-sync complete: Local model parameters pushed to PostgreSQL.")
        except Exception as e:
            logger.error(f"Failed to auto-sync local model parameters to PostgreSQL: {e}")
    
    def save(self, portfolio, nav: float = None) -> bool:
        """Save portfolio state to persistent storage"""
        try:
            positions_dict = {
                symbol: {
                    'quantity': pos.quantity,
                    'avg_price': pos.avg_price,
                    'symbol': pos.symbol,
                }
                for symbol, pos in portfolio.positions.items()
            }
            
            timestamp = datetime.now()
            if nav is None:
                nav = portfolio.net_asset_value({})
            
            if self.backend == 'json':
                return self._save_json(timestamp, nav, portfolio.cash, 
                                      positions_dict, portfolio.realized_pnl)
            elif self.backend == 'postgres':
                return self._save_postgres(timestamp, nav, portfolio.cash,
                                         positions_dict, portfolio.realized_pnl,
                                         len(portfolio.trade_history))
        except Exception as e:
            logger.error(f"Failed to save portfolio state: {e}")
            return False
    
    def _save_json(self, timestamp: datetime, nav: float, cash: float,
                   positions: Dict, realized_pnl: float) -> bool:
        """Save to JSON file"""
        try:
            data = {
                'timestamp': timestamp.isoformat(),
                'nav': nav,
                'cash': cash,
                'positions': positions,
                'realized_pnl': realized_pnl,
                'backup_timestamp': datetime.now().isoformat(),
            }
            
            if Path(self.json_path).exists():
                backup_path = f"{self.json_path}.bak"
                Path(self.json_path).rename(backup_path)
            
            with open(self.json_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Portfolio saved to {self.json_path}")
            return True
        except Exception as e:
            logger.error(f"JSON save failed: {e}")
            return False
    
    def _save_postgres(self, timestamp: datetime, nav: float, cash: float,
                      positions: Dict, realized_pnl: float, trade_count: int) -> bool:
        """Save to PostgreSQL database"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                positions_json = json.dumps(positions)
                cursor.execute("""
                INSERT INTO portfolio_snapshots 
                (timestamp, nav, cash, realized_pnl, positions_json, trade_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (timestamp, nav, cash, realized_pnl, positions_json, trade_count))
            conn.commit()
            conn.close()
            logger.info(f"Portfolio snapshot saved to PostgreSQL (NAV: ${nav:,.2f})")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL save failed: {e}")
            return False
    
    def load(self) -> Optional[Dict]:
        """Load latest portfolio state from persistent storage"""
        try:
            if self.backend == 'json':
                return self._load_json()
            elif self.backend == 'postgres':
                return self._load_postgres()
        except Exception as e:
            logger.error(f"Failed to load portfolio state: {e}")
            return None
    
    def _load_json(self) -> Optional[Dict]:
        """Load from JSON file"""
        try:
            if not Path(self.json_path).exists():
                logger.info(f"No existing state file at {self.json_path}")
                return None
            
            with open(self.json_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Portfolio loaded from {self.json_path} (NAV: ${data['nav']:,.2f})")
            return data
        except Exception as e:
            logger.error(f"JSON load failed: {e}")
            return None
    
    def _load_postgres(self) -> Optional[Dict]:
        """Load latest snapshot from PostgreSQL"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT timestamp, nav, cash, realized_pnl, positions_json, trade_count
                FROM portfolio_snapshots
                ORDER BY timestamp DESC
                LIMIT 1
                """)
                row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.info("No portfolio snapshots found in database")
                return None
            
            timestamp, nav, cash, realized_pnl, positions, trade_count = row
            
            # psycopg2 automatically decodes jsonb columns to python structures, but check string type just in case
            if isinstance(positions, str):
                positions = json.loads(positions)
            
            logger.info(f"Portfolio loaded from PostgreSQL (NAV: ${nav:,.2f}, Trades: {trade_count})")
            
            return {
                'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                'nav': nav,
                'cash': cash,
                'positions': positions,
                'realized_pnl': realized_pnl,
                'trade_count': trade_count,
            }
        except Exception as e:
            logger.error(f"PostgreSQL load failed: {e}")
            return None
    
    def save_trade(self, symbol: str, side: str, quantity: float, price: float,
                   pnl: float, realized_pnl: float, cash: float, trade_type: str = 'simulation', agent_name: str = 'system'):
        """Record a trade execution"""
        if self.backend != 'postgres':
            return
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO trades (timestamp, symbol, side, quantity, price, pnl, realized_pnl, cash, trade_type, agent_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (datetime.now(), symbol, side, quantity, price, pnl, realized_pnl, cash, trade_type, agent_name))
            conn.commit()
            conn.close()
            logger.debug(f"Trade recorded ({trade_type}) by {agent_name}: {side} {quantity} {symbol} @ ${price:.2f}")
        except Exception as e:
            logger.error(f"Failed to save trade to PostgreSQL: {e}")
    
    def save_risk_event(self, rule: str, severity: str, message: str, action: str):
        """Record a risk management event"""
        if self.backend != 'postgres':
            return
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO risk_events (timestamp, rule, severity, message, action)
                VALUES (%s, %s, %s, %s, %s)
                """, (datetime.now(), rule, severity, message, action))
            conn.commit()
            conn.close()
            logger.info(f"Risk event recorded in PostgreSQL: [{severity}] {rule}")
        except Exception as e:
            logger.error(f"Failed to save risk event to PostgreSQL: {e}")
            
    def save_learning_event(self, event_type: str, symbol: str, user_id: str, input_details: Dict, output_details: Dict):
        """Record a learning module / prediction event"""
        if self.backend != 'postgres':
            return
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO learning_events (timestamp, event_type, symbol, user_id, input_details, output_details)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    datetime.now(), 
                    event_type, 
                    symbol, 
                    user_id, 
                    json.dumps(input_details), 
                    json.dumps(output_details)
                ))
            conn.commit()
            conn.close()
            logger.debug(f"Learning event recorded in PostgreSQL: {event_type} for {symbol} (user: {user_id})")
        except Exception as e:
            logger.error(f"Failed to save learning event to PostgreSQL: {e}")
            
    def get_learning_events(self, limit: int = 100) -> List[Dict]:
        """Get recent learning events"""
        if self.backend != 'postgres':
            return []
        
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                SELECT id, timestamp, event_type, symbol, user_id, input_details, output_details
                FROM learning_events
                ORDER BY timestamp DESC
                LIMIT %s
                """, (limit,))
                rows = cursor.fetchall()
            conn.close()
            
            events = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].isoformat()
                if isinstance(row_dict['input_details'], str):
                    row_dict['input_details'] = json.loads(row_dict['input_details'])
                if isinstance(row_dict['output_details'], str):
                    row_dict['output_details'] = json.loads(row_dict['output_details'])
                events.append(row_dict)
            return events
        except Exception as e:
            logger.error(f"Failed to get learning events from PostgreSQL: {e}")
            return []
    
    def get_history(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """Get portfolio history from the last N days"""
        if self.backend != 'postgres':
            return []
        
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                SELECT timestamp, nav, cash, realized_pnl, positions_json, trade_count
                FROM portfolio_snapshots
                WHERE timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY timestamp DESC
                LIMIT %s
                """, (days, limit))
                rows = cursor.fetchall()
            conn.close()
            
            history = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].isoformat()
                if isinstance(row_dict['positions_json'], str):
                    row_dict['positions'] = json.loads(row_dict['positions_json'])
                else:
                    row_dict['positions'] = row_dict['positions_json']
                history.append(row_dict)
            
            logger.info(f"Retrieved {len(history)} snapshots from last {days} days from PostgreSQL")
            return history
        except Exception as e:
            logger.error(f"Failed to get history from PostgreSQL: {e}")
            return []
    
    def get_trades(self, symbol: str = None, days: int = 1, limit: int = 100, trade_type: str = None) -> List[Dict]:
        """Get trade history"""
        if self.backend != 'postgres':
            return []
        
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if symbol:
                    if trade_type:
                        cursor.execute("""
                        SELECT timestamp, symbol, side, quantity, price, pnl, trade_type, agent_name
                        FROM trades
                        WHERE symbol = %s AND trade_type = %s AND timestamp >= NOW() -  INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """, (symbol, trade_type, days, limit))
                    else:
                        cursor.execute("""
                        SELECT timestamp, symbol, side, quantity, price, pnl, trade_type, agent_name
                        FROM trades
                        WHERE symbol = %s AND timestamp >= NOW() -  INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """, (symbol, days, limit))
                else:
                    if trade_type:
                        cursor.execute("""
                        SELECT timestamp, symbol, side, quantity, price, pnl, trade_type, agent_name
                        FROM trades
                        WHERE trade_type = %s AND timestamp >= NOW() - INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """, (trade_type, days, limit))
                    else:
                        cursor.execute("""
                        SELECT timestamp, symbol, side, quantity, price, pnl, trade_type, agent_name
                        FROM trades
                        WHERE timestamp >= NOW() - INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """, (days, limit))
                rows = cursor.fetchall()
            conn.close()
            
            trades = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].isoformat()
                trades.append(row_dict)
            logger.info(f"Retrieved {len(trades)} trades from PostgreSQL")
            return trades
        except Exception as e:
            logger.error(f"Failed to get trades from PostgreSQL: {e}")
            return []
    
    def cleanup_old_data(self, days: int = 90):
        """Delete snapshots older than N days to keep database lean"""
        if self.backend != 'postgres':
            return
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                DELETE FROM portfolio_snapshots
                WHERE timestamp < NOW() - INTERVAL '%s days'
                """, (days,))
                deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted} old snapshots (older than {days} days) in PostgreSQL")
        except Exception as e:
            logger.error(f"PostgreSQL cleanup failed: {e}")

    def save_learner_state(self, symbol: str, state_dict: Dict) -> bool:
        """Save learner optimizer state to PostgreSQL or JSON file fallback"""
        if self.backend == 'postgres' and getattr(self, 'db_connected', False):
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("""
                    INSERT INTO model_parameters (symbol, parameters_json, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (symbol) DO UPDATE 
                    SET parameters_json = EXCLUDED.parameters_json, updated_at = CURRENT_TIMESTAMP
                    """, (symbol, json.dumps(state_dict)))
                conn.commit()
                conn.close()
                logger.info(f"Learner state for {symbol} saved to PostgreSQL")
                return True
            except Exception as e:
                logger.error(f"Failed to save learner state to PostgreSQL: {e}")
                # Fall back to json
        
        # Local JSON fallback
        try:
            data = {}
            path = Path("model_parameters.json")
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
            data[symbol] = state_dict
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Learner state for {symbol} saved to JSON (local fallback)")
            return True
        except Exception as e:
            logger.error(f"Failed to save learner state to JSON: {e}")
            return False

    def load_learner_state(self, symbol: str) -> Optional[Dict]:
        """Load learner optimizer state from PostgreSQL or JSON file fallback"""
        if self.backend == 'postgres' and getattr(self, 'db_connected', False):
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("""
                    SELECT parameters_json FROM model_parameters WHERE symbol = %s
                    """, (symbol,))
                    row = cursor.fetchone()
                conn.close()
                if row:
                    params = row[0]
                    if isinstance(params, str):
                        params = json.loads(params)
                    return params
            except Exception as e:
                logger.error(f"Failed to load learner state from PostgreSQL: {e}")
                # Fall back to json
        
        # Local JSON fallback
        try:
            path = Path("model_parameters.json")
            if not path.exists():
                return None
            with open(path, 'r') as f:
                data = json.load(f)
            return data.get(symbol)
        except Exception as e:
            logger.error(f"Failed to load learner state from JSON: {e}")
            return None

    def save_agent_parameters(self, agent_name: str, parameters: Dict) -> bool:
        """Save agent adaptive parameters to PostgreSQL or JSON file fallback"""
        if self.backend == 'postgres' and getattr(self, 'db_connected', False):
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("""
                    INSERT INTO agent_parameters (agent_name, parameters_json, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (agent_name) DO UPDATE 
                    SET parameters_json = EXCLUDED.parameters_json, updated_at = CURRENT_TIMESTAMP
                    """, (agent_name, json.dumps(parameters)))
                conn.commit()
                conn.close()
                logger.info(f"Agent parameters for {agent_name} saved to PostgreSQL")
                return True
            except Exception as e:
                logger.error(f"Failed to save agent parameters to PostgreSQL: {e}")
                # Fall back to json
                
        # JSON fallback
        try:
            data = {}
            path = Path("agent_parameters.json")
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
            data[agent_name] = parameters
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Agent parameters for {agent_name} saved to JSON (local fallback)")
            return True
        except Exception as e:
            logger.error(f"Failed to save agent parameters to JSON: {e}")
            return False

    def load_agent_parameters(self, agent_name: str) -> Optional[Dict]:
        """Load agent adaptive parameters from PostgreSQL or JSON file fallback"""
        if self.backend == 'postgres' and getattr(self, 'db_connected', False):
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("""
                    SELECT parameters_json FROM agent_parameters WHERE agent_name = %s
                    """, (agent_name,))
                    row = cursor.fetchone()
                conn.close()
                if row:
                    params = row[0]
                    if isinstance(params, str):
                        params = json.loads(params)
                    return params
            except Exception as e:
                logger.error(f"Failed to load agent parameters from PostgreSQL: {e}")
                # Fall back to json
                
        # JSON fallback
        try:
            path = Path("agent_parameters.json")
            if not path.exists():
                return None
            with open(path, 'r') as f:
                data = json.load(f)
            return data.get(agent_name)
        except Exception as e:
            logger.error(f"Failed to load agent parameters from JSON: {e}")
            return None
