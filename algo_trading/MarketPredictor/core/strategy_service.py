"""
Strategy Service - gRPC server exposing MarketPredictor learning module
This service runs alongside the Java backend and provides trading signals
"""

import grpc
from concurrent import futures
import json
import logging
import os
import sys
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Setup path overrides
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import MarketPredictor modules
try:
    from strategies.heuristic.marketstate import MarketState, CyclePhase
    from simulator.simulator import DigitalTwin
    from strategies.heuristic.agents import Berserker, Sentinel, Anchor, CapitalManager
    from strategies.explorer.nlp_model import NLPExplorer
    from strategies.explorer.company_evaluator import QuantExplorer
    from strategies.heuristic.blackboard import Blackboard
    from strategies.heuristic.protocol import SyntheticHedgeProtocol
    from core.execution import Portfolio
    from core.predictor import IntervalPredictor
    from simulator.state_persistence import StateManager
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    sys.exit(1)

# Import gRPC stubs
try:
    import strategy_service_pb2
    import strategy_service_pb2_grpc
except ImportError:
    logger.error("Failed to import gRPC stubs. Run protoc compilation first.")
    sys.exit(1)


class StrategyServiceImpl(strategy_service_pb2_grpc.StrategyServiceServicer):
    """Implementation of Strategy Service for gRPC"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Dictionary of symbol -> DigitalTwin
        self.simulators = {}
        self.agents = [
            Berserker(),
            NLPExplorer(),
            QuantExplorer(),
            Sentinel(),
            Anchor(),
            CapitalManager()
        ]
        self.blackboard = Blackboard()
        self.protocol = SyntheticHedgeProtocol(self.blackboard)
        self.state_manager = StateManager(backend='postgres')
        self.logger.info("Strategy service initialized with 6 agents and StateManager (PostgreSQL)")
        
        # Upstox Real-Time Market Feed Integration disabled in Python strategy service.
        # Ticks are pushed from the Java WebSocket client directly via gRPC.
        pass
    
    def _get_or_create_simulator(self, symbol: str) -> DigitalTwin:
        """Get existing DigitalTwin simulator for a symbol, or create/fetch history dynamically"""
        if symbol not in self.simulators:
            self.logger.info(f"Initializing DigitalTwin simulator for symbol: {symbol}")
            try:
                # Fetch 100 days of real market data to seed the simulator
                history = DigitalTwin.fetch_real_market_data(symbol, days=100)
                if history is None or history.empty:
                    # Fallback to synthetic if fetch fails
                    self.logger.warning(f"Could not fetch real history for {symbol}, generating synthetic seed")
                    import pandas as pd
                    import numpy as np
                    dates = pd.date_range(end=datetime.utcnow(), periods=100)
                    np_random = np.random.default_rng(42)
                    returns = pd.Series(np_random.normal(0.0005, 0.01, size=100))
                    prices = 100 * (1 + returns).cumprod()
                    returns = prices.pct_change().fillna(0)
                    history = pd.DataFrame({
                        "timestamp": dates,
                        "symbol": symbol,
                        "price": prices,
                        "returns": returns
                    })
                
                self.simulators[symbol] = DigitalTwin(history)
                self.logger.info(f"DigitalTwin simulator for {symbol} initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize simulator for {symbol}: {e}")
                raise
        return self.simulators[symbol]
    
    def ComputeSignals(self, request, context):
        try:
            state_msg = request.market_state
            symbol = state_msg.symbol
            
            # Ensure simulator is initialized for this symbol
            self._get_or_create_simulator(symbol)
            
            # Map CyclePhase string to Enum
            try:
                phase_enum = CyclePhase[state_msg.cycle_phase.upper()]
            except KeyError:
                phase_enum = CyclePhase.CHOP
                
            # Create MarketState object
            market_state = MarketState(
                symbol=symbol,
                price=state_msg.price,
                volatility=state_msg.volatility,
                cycle_phase=phase_enum,
                timestamp=datetime.fromtimestamp(state_msg.timestamp_ms / 1000)
            )
            
            # Update protocol and blackboard
            self.protocol.update(market_state)
            
            # Collect signals from all agents
            signals = []
            for agent in self.agents:
                agent.update(market_state)
                intents = agent.decide(market_state)
                
                for intent in intents:
                    signal = strategy_service_pb2.TradeSignalMessage(
                        agent_name=agent.name,
                        symbol=intent.symbol,
                        side=intent.side,
                        quantity=int(intent.quantity),
                        confidence=intent.confidence,
                        reason=intent.reason,
                        order_type="MARKET",
                        price=0.0,
                        timestamp_ms=int(datetime.now().timestamp() * 1000)
                    )
                    signals.append(signal)
            
            self.logger.info(f"gRPC ComputeSignals: Generated {len(signals)} signals for {symbol}")
            
            # Save learning event
            input_details = {
                "price": state_msg.price,
                "volatility": state_msg.volatility,
                "cycle_phase": state_msg.cycle_phase,
                "mode": request.mode
            }
            output_details = {
                "signals": [
                    {
                        "agent_name": s.agent_name,
                        "side": s.side,
                        "quantity": s.quantity,
                        "confidence": s.confidence,
                        "reason": s.reason
                    }
                    for s in signals
                ],
                "status": "SUCCESS"
            }
            self.state_manager.save_learning_event(
                event_type="COMPUTE_SIGNALS",
                symbol=symbol,
                user_id="java_backend_system",
                input_details=input_details,
                output_details=output_details
            )

            return strategy_service_pb2.SignalResponse(
                signals=signals,
                status="SUCCESS"
            )
            
        except Exception as e:
            self.logger.error(f"Error in ComputeSignals gRPC: {e}", exc_info=True)
            return strategy_service_pb2.SignalResponse(
                status="ERROR",
                error_message=str(e)
            )
    
    def RecordTradeOutcome(self, request, context):
        try:
            symbol = request.symbol
            scenario = request.scenario if request.scenario else "live"
            agent_name = request.agent_name if request.agent_name else "system"
            
            self.logger.info(f"gRPC RecordTradeOutcome received for {symbol}: agent={agent_name}, side={request.side}, price={request.execution_price}, pnl={request.pnl}")
            
            # Find the agent and trigger parameter adaptation
            agent_found = False
            for agent in self.agents:
                if agent.name == agent_name:
                    agent.update_from_outcome(symbol, request.side, request.quantity, request.execution_price, request.pnl)
                    agent_found = True
                    break
            
            # Save learning event representing the trade outcome
            input_details = {
                "order_id": request.order_id,
                "side": request.side,
                "quantity": request.quantity,
                "execution_price": request.execution_price,
                "pnl": request.pnl,
                "scenario": scenario
            }
            output_details = {
                "model_adaptation": "TRIGGERED" if agent_found else "DEFERRED",
                "message": f"Recorded outcome to database and updated {agent_name} parameters." if agent_found else f"Recorded outcome, agent {agent_name} not found for adaptation."
            }
            self.state_manager.save_learning_event(
                event_type="TRADE_OUTCOME",
                symbol=symbol,
                user_id=agent_name,
                input_details=input_details,
                output_details=output_details
            )

            # Persist real/simulated broker trade separately to the trades table with agent_name
            self.state_manager.save_trade(
                symbol=symbol,
                side=request.side,
                quantity=request.quantity,
                price=request.execution_price,
                pnl=request.pnl,
                realized_pnl=0.0,
                cash=0.0,
                trade_type=scenario,
                agent_name=agent_name
            )
            
            return strategy_service_pb2.TradeOutcomeResponse(success=True)
            
        except Exception as e:
            self.logger.error(f"Error in RecordTradeOutcome gRPC: {e}", exc_info=True)
            return strategy_service_pb2.TradeOutcomeResponse(
                success=False,
                error_message=str(e)
            )
            
    def GetLearnerState(self, request, context):
        try:
            symbol = request.symbol
            simulator = self._get_or_create_simulator(symbol)
            state_dict = simulator.learner.to_dict()
            state_json = json.dumps(state_dict, default=str)
            return strategy_service_pb2.LearnerStateResponse(state_json=state_json)
        except Exception as e:
            self.logger.error(f"Error in GetLearnerState gRPC: {e}", exc_info=True)
            return strategy_service_pb2.LearnerStateResponse(state_json="{}")
            
    def TrainOnSymbol(self, request, context):
        try:
            symbol = request.symbol
            days = request.days if request.days > 0 else 30
            self.logger.info(f"gRPC TrainOnSymbol initiated for {symbol} over {days} days")
            
            # Get or create simulator
            simulator = self._get_or_create_simulator(symbol)
            
            # Fetch fresh real market data to calibrate GJR-GARCH / Jump Diffusion parameters
            data_df = DigitalTwin.fetch_real_market_data(symbol, days=days)
            if data_df is None or data_df.empty:
                raise ValueError(f"Could not fetch historical data for {symbol} from Yahoo Finance")
                
            # Calibrate model by generating states from real historical data
            states = simulator.generate_from_real_data(symbol, days=days, data_df=data_df)
            
            # Save learner state
            simulator.save_learner()
            
            state_dict = simulator.learner.to_dict()
            state_json = json.dumps(state_dict, default=str)
            
            self.logger.info(f"gRPC TrainOnSymbol complete for {symbol}. Calibrated {len(states)} historical states.")
            
            # Save learning event
            input_details = {
                "days": days,
                "symbol": symbol
            }
            output_details = {
                "success": True,
                "states_calibrated": len(states),
                "learner_state": state_dict
            }
            self.state_manager.save_learning_event(
                event_type="MODEL_TRAINING",
                symbol=symbol,
                user_id="admin",
                input_details=input_details,
                output_details=output_details
            )

            return strategy_service_pb2.TrainingResponse(
                success=True,
                message=f"Calibrated successfully on {len(states)} historical days of {symbol}.",
                learner_state_json=state_json
            )
            
        except Exception as e:
            self.logger.error(f"Error in TrainOnSymbol gRPC: {e}", exc_info=True)
            return strategy_service_pb2.TrainingResponse(
                success=False,
                message=str(e),
                learner_state_json="{}"
            )

    def FetchLiveQuote(self, request, context):
        try:
            symbol = request.symbol
            self.logger.info(f"gRPC FetchLiveQuote requested for {symbol}")
            
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            
            price = None
            open_p = 0.0
            high = 0.0
            low = 0.0
            volume = 0
            
            try:
                # fast_info is extremely fast and has near-real-time data
                info = ticker.fast_info
                price = info.lastPrice if hasattr(info, 'lastPrice') and info.lastPrice is not None else None
                if price is not None:
                    open_p = info.open if hasattr(info, 'open') and info.open is not None else price
                    high = info.dayHigh if hasattr(info, 'dayHigh') and info.dayHigh is not None else price
                    low = info.dayLow if hasattr(info, 'dayLow') and info.dayLow is not None else price
                    volume = int(info.lastVolume) if hasattr(info, 'lastVolume') and info.lastVolume is not None else 0
            except Exception as e:
                self.logger.warning(f"Failed to fetch fast_info for {symbol}, falling back to history: {e}")
                
            if price is None:
                # Fallback to history(period="1d") which is highly robust
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    open_p = hist['Open'].iloc[-1] if 'Open' in hist.columns else price
                    high = hist['High'].iloc[-1] if 'High' in hist.columns else price
                    low = hist['Low'].iloc[-1] if 'Low' in hist.columns else price
                    volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0
                else:
                    raise ValueError(f"No pricing data available for symbol {symbol}")
            
            # Simulate a tight bid/ask spread (0.1% or 10 basis points spread)
            bid = price * 0.9995
            ask = price * 1.0005
            
            timestamp_ms = int(datetime.utcnow().timestamp() * 1000)
            
            self.logger.info(f"gRPC FetchLiveQuote complete for {symbol}: price={price}, volume={volume}")
            return strategy_service_pb2.QuoteResponse(
                symbol=symbol,
                price=float(price),
                bid=float(bid),
                ask=float(ask),
                open=float(open_p),
                high=float(high),
                low=float(low),
                volume=int(volume),
                timestamp_ms=timestamp_ms,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in FetchLiveQuote gRPC: {e}", exc_info=True)
            return strategy_service_pb2.QuoteResponse(
                symbol=request.symbol,
                success=False,
                error_message=str(e)
            )

    def PredictInterval(self, request, context):
        try:
            symbol = request.symbol
            interval = request.interval
            self.logger.info(f"gRPC PredictInterval requested for {symbol} with interval {interval}")
            
            # Use IntervalPredictor to calculate prediction
            prediction = IntervalPredictor.predict(symbol, interval)
            
            # Save learning event
            input_details = {
                "interval": interval,
                "symbol": symbol
            }
            output_details = {
                "current_price": prediction["current_price"],
                "predicted_price": prediction["predicted_price"],
                "signal": prediction["signal"],
                "confidence": prediction["confidence"],
                "autosell_price": prediction["autosell_price"],
                "reason": prediction["reason"],
                "success": prediction["success"],
                "error_message": prediction["error_message"]
            }
            self.state_manager.save_learning_event(
                event_type="PREDICT_INTERVAL",
                symbol=symbol,
                user_id="app_user",
                input_details=input_details,
                output_details=output_details
            )

            # Map Python dict to strategy_service_pb2.IntervalPredictionResponse
            return strategy_service_pb2.IntervalPredictionResponse(
                symbol=prediction["symbol"],
                interval=prediction["interval"],
                current_price=prediction["current_price"],
                predicted_price=prediction["predicted_price"],
                signal=prediction["signal"],
                confidence=prediction["confidence"],
                autosell_price=prediction["autosell_price"],
                reason=prediction["reason"],
                success=prediction["success"],
                error_message=prediction["error_message"]
            )
            
        except Exception as e:
            self.logger.error(f"Error in PredictInterval gRPC: {e}", exc_info=True)
            return strategy_service_pb2.IntervalPredictionResponse(
                symbol=request.symbol,
                interval=request.interval,
                success=False,
                error_message=str(e)
            )


# Initialize Flask app for health checks
app = Flask(__name__)
strategy_service = None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'UP',
        'service': 'strategy-service',
        'timestamp': datetime.utcnow().isoformat(),
        'active_simulators': list(strategy_service.simulators.keys()) if strategy_service else [],
        'agents': 6,
        'gRPC': 'enabled'
    })


def start_grpc_server(port=50051):
    """Start gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    strategy_service_pb2_grpc.add_StrategyServiceServicer_to_server(
        strategy_service,
        server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"gRPC Server started on port {port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC Server shutting down...")
        server.stop(0)


def start_flask_server(port=5000):
    """Start Flask server for health checks and debugging"""
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    # Initialize strategy service
    strategy_service = StrategyServiceImpl()
    
    # Start gRPC server in separate thread
    grpc_port = int(os.getenv('GRPC_PORT', '50051'))
    flask_port = int(os.getenv('FLASK_PORT', '5000'))
    
    grpc_thread = Thread(target=start_grpc_server, args=(grpc_port,), daemon=True)
    grpc_thread.start()
    
    # Start Flask in main thread
    logger.info(f"Starting Flask health check server on port {flask_port}")
    start_flask_server(flask_port)
