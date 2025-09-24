"""
Advanced Backtesting Framework
Provides comprehensive backtesting capabilities using backtrader with custom strategies
"""

import backtrader as bt
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for Streamlit compatibility

class MovingAverageStrategy(bt.Strategy):
    """Simple Moving Average Crossover Strategy"""

    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('stop_loss', 0.05),  # 5% stop loss
        ('take_profit', 0.15),  # 15% take profit
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.order = None
        self.buy_price = None

    def next(self):
        if self.order:  # Check if order is pending
            return

        if not self.position:  # Not in market
            if self.crossover > 0:  # Fast MA crosses above slow MA
                self.order = self.buy()

        else:  # In market
            if self.crossover < 0:  # Fast MA crosses below slow MA
                self.order = self.sell()
            elif self.buy_price:
                # Check stop loss and take profit
                current_price = self.data.close[0]
                if (current_price <= self.buy_price * (1 - self.params.stop_loss) or
                    current_price >= self.buy_price * (1 + self.params.take_profit)):
                    self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
            else:
                self.buy_price = None

        self.order = None

class RSIMeanReversionStrategy(bt.Strategy):
    """RSI Mean Reversion Strategy"""

    params = (
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('stop_loss', 0.03),
        ('take_profit', 0.08),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.order = None
        self.buy_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.rsi < self.params.rsi_oversold:  # Oversold
                self.order = self.buy()
        else:
            if (self.rsi > self.params.rsi_overbought or
                (self.buy_price and self.data.close[0] <= self.buy_price * (1 - self.params.stop_loss)) or
                (self.buy_price and self.data.close[0] >= self.buy_price * (1 + self.params.take_profit))):
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
            else:
                self.buy_price = None

        self.order = None

class BollingerBandsStrategy(bt.Strategy):
    """Bollinger Bands Mean Reversion Strategy"""

    params = (
        ('period', 20),
        ('devfactor', 2.0),
        ('stop_loss', 0.04),
        ('take_profit', 0.10),
    )

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor
        )
        self.order = None
        self.buy_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.data.close[0] < self.boll.lines.bot[0]:  # Price below lower band
                self.order = self.buy()
        else:
            if (self.data.close[0] > self.boll.lines.top[0] or  # Price above upper band
                (self.buy_price and self.data.close[0] <= self.buy_price * (1 - self.params.stop_loss)) or
                (self.buy_price and self.data.close[0] >= self.buy_price * (1 + self.params.take_profit))):
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
            else:
                self.buy_price = None

        self.order = None

class BacktestResults:
    """Container for backtest results and analysis"""

    def __init__(self, cerebro, strategy_name: str):
        self.cerebro = cerebro
        self.strategy_name = strategy_name
        self.strats = cerebro.runstrategies
        self.start_value = cerebro.broker.startingcash
        self.end_value = cerebro.broker.getvalue()
        self.analyzers = {}

        # Extract analyzer results
        if self.strats and len(self.strats[0]) > 0:
            strat = self.strats[0][0]
            for name, analyzer in strat.analyzers.getitems():
                self.analyzers[name] = analyzer.get_analysis()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        metrics = {
            'Strategy': self.strategy_name,
            'Starting Value': self.start_value,
            'Ending Value': self.end_value,
            'Total Return': ((self.end_value - self.start_value) / self.start_value) * 100,
            'Total Return $': self.end_value - self.start_value,
        }

        # Add analyzer results
        if 'sharpe' in self.analyzers:
            sharpe = self.analyzers['sharpe']
            metrics['Sharpe Ratio'] = sharpe.get('sharperatio', 'N/A')

        if 'drawdown' in self.analyzers:
            dd = self.analyzers['drawdown']
            metrics['Max Drawdown %'] = dd.get('max', {}).get('drawdown', 'N/A')
            metrics['Max Drawdown $'] = dd.get('max', {}).get('moneydown', 'N/A')

        if 'returns' in self.analyzers:
            returns = self.analyzers['returns']
            metrics['Total Returns'] = returns.get('rtot', 'N/A')
            metrics['Average Return'] = returns.get('ravg', 'N/A')

        if 'trades' in self.analyzers:
            trades = self.analyzers['trades']
            metrics['Total Trades'] = trades.get('total', {}).get('total', 0)
            metrics['Winning Trades'] = trades.get('won', {}).get('total', 0)
            metrics['Losing Trades'] = trades.get('lost', {}).get('total', 0)

            total_trades = metrics['Total Trades']
            if total_trades > 0:
                metrics['Win Rate %'] = (metrics['Winning Trades'] / total_trades) * 100

            if 'pnl' in trades.get('won', {}):
                metrics['Avg Win $'] = trades['won']['pnl'].get('average', 'N/A')
            if 'pnl' in trades.get('lost', {}):
                metrics['Avg Loss $'] = trades['lost']['pnl'].get('average', 'N/A')

        return metrics

class PortfolioBacktester:
    """Main backtesting engine"""

    def __init__(self, initial_cash: float = 100000, commission: float = 0.001):
        self.initial_cash = initial_cash
        self.commission = commission
        self.results = []

    def get_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Download historical data using yfinance"""
        try:
            data = yf.download(symbol, start=start_date, end=end_date)
            if data.empty:
                raise ValueError(f"No data found for symbol {symbol}")
            return data
        except Exception as e:
            raise ValueError(f"Error downloading data for {symbol}: {e}")

    def run_backtest(self, symbol: str, strategy_class, strategy_params: Dict = None,
                    start_date: str = None, end_date: str = None) -> BacktestResults:
        """Run a single backtest"""

        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d')

        # Get data
        data = self.get_data(symbol, start_date, end_date)

        # Create Cerebro engine
        cerebro = bt.Cerebro()

        # Add data feed
        data_feed = bt.feeds.PandasData(dataname=data)
        cerebro.adddata(data_feed)

        # Add strategy
        if strategy_params:
            cerebro.addstrategy(strategy_class, **strategy_params)
        else:
            cerebro.addstrategy(strategy_class)

        # Set broker parameters
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission)

        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

        # Run backtest
        results = cerebro.run()

        # Create results object
        backtest_result = BacktestResults(cerebro, strategy_class.__name__)
        self.results.append(backtest_result)

        return backtest_result

    def run_strategy_comparison(self, symbol: str, strategies: List[Tuple],
                               start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Compare multiple strategies on the same symbol"""

        comparison_results = []

        for strategy_info in strategies:
            if len(strategy_info) == 2:
                strategy_class, strategy_params = strategy_info
            else:
                strategy_class = strategy_info[0]
                strategy_params = {}

            try:
                result = self.run_backtest(symbol, strategy_class, strategy_params,
                                         start_date, end_date)
                metrics = result.get_performance_metrics()
                comparison_results.append(metrics)
            except Exception as e:
                print(f"Error running {strategy_class.__name__}: {e}")

        return pd.DataFrame(comparison_results)

    def plot_results(self, symbol: str, save_path: str = None) -> str:
        """Plot backtest results"""
        if not self.results:
            return None

        # Get the latest result
        result = self.results[-1]

        # Plot using matplotlib
        fig = result.cerebro.plot(style='candlestick', barup='green', bardown='red')[0][0]

        if save_path:
            fig.savefig(save_path, dpi=100, bbox_inches='tight')
            return save_path
        else:
            import tempfile
            temp_path = tempfile.mktemp(suffix='.png')
            fig.savefig(temp_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            return temp_path

def run_sample_backtest():
    """Run a sample backtest for demonstration"""

    backtester = PortfolioBacktester(initial_cash=100000)

    # Define strategies to compare
    strategies = [
        (MovingAverageStrategy, {'fast_period': 10, 'slow_period': 30}),
        (MovingAverageStrategy, {'fast_period': 5, 'slow_period': 20}),
        (RSIMeanReversionStrategy, {'rsi_period': 14, 'rsi_overbought': 70, 'rsi_oversold': 30}),
        (BollingerBandsStrategy, {'period': 20, 'devfactor': 2.0}),
    ]

    # Run comparison
    symbol = 'AAPL'
    start_date = '2022-01-01'
    end_date = '2024-01-01'

    print(f"Running backtest comparison for {symbol} from {start_date} to {end_date}")

    comparison_df = backtester.run_strategy_comparison(symbol, strategies, start_date, end_date)

    print("\nStrategy Comparison Results:")
    print("=" * 80)
    print(comparison_df.to_string(index=False))

    return comparison_df, backtester

if __name__ == "__main__":
    # Run sample backtest
    results_df, backtester = run_sample_backtest()