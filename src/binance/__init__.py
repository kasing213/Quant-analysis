"""
Binance Integration Module
Handles WebSocket streams, REST API, trading bots, and real-time market data
"""

from .websocket_client import BinanceWebSocketClient
from .data_manager import BinanceDataManager
from .rest_client import BinanceRESTClient
from .trading_bot import TradingBot, TradingStrategy, Position, SignalType
from .bot_orchestrator import BotOrchestrator
from .bot_persistence import BotPersistence

__all__ = [
    'BinanceWebSocketClient',
    'BinanceDataManager',
    'BinanceRESTClient',
    'TradingBot',
    'TradingStrategy',
    'Position',
    'SignalType',
    'BotOrchestrator',
    'BotPersistence'
]
