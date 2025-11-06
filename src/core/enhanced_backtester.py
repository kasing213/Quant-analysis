"""
Enhanced Backtesting Framework with Web Dashboard Integration
Comprehensive backtesting system with performance analytics and visualization support
"""

import backtrader as bt
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import logging
import json
from pathlib import Path
import sqlite3
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

@dataclass
class BacktestResult:
    """Container for backtest results"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    volatility: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: float
    best_trade: float
    worst_trade: float
    equity_curve: List[Dict]
    trades_log: List[Dict]
    monthly_returns: List[Dict]
    performance_metrics: Dict[str, Any]

class MovingAverageStrategy(bt.Strategy):
    """Simple Moving Average Crossover Strategy"""
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow_period
        )
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        if not self.position:
            if self.crossover > 0:  # Golden cross
                self.buy()
        elif self.crossover < 0:  # Death cross
            self.close()

class MeanReversionStrategy(bt.Strategy):
    """Mean Reversion Strategy using RSI and Bollinger Bands"""

    params = (
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('bb_period', 20),
        ('bb_std', 2.0),
        ('stop_loss', 0.05),
        ('take_profit', 0.10),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.bb = bt.indicators.BollingerBands(self.data.close, period=self.params.bb_period, devfactor=self.params.bb_std)
        self.order = None
        self.buy_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            # Buy signal: RSI oversold and price below lower Bollinger Band
            if (self.rsi[0] < self.params.rsi_oversold and
                self.data.close[0] < self.bb.lines.bot[0]):
                self.order = self.buy()

        else:
            current_price = self.data.close[0]
            # Sell signals
            if (self.rsi[0] > self.params.rsi_overbought or  # RSI overbought
                current_price > self.bb.lines.top[0] or      # Price above upper BB
                (self.buy_price and current_price <= self.buy_price * (1 - self.params.stop_loss)) or  # Stop loss
                (self.buy_price and current_price >= self.buy_price * (1 + self.params.take_profit))):  # Take profit
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
            elif order.issell():
                self.buy_price = None
        self.order = None

class MomentumStrategy(bt.Strategy):
    """Momentum Strategy using MACD and Volume"""

    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('volume_ma_period', 20),
        ('volume_threshold', 1.5),  # Volume must be 1.5x average
        ('stop_loss', 0.06),
        ('take_profit', 0.18),
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(self.data.close,
                                      period_me1=self.params.macd_fast,
                                      period_me2=self.params.macd_slow,
                                      period_signal=self.params.macd_signal)
        self.volume_ma = bt.indicators.SMA(self.data.volume, period=self.params.volume_ma_period)
        self.order = None
        self.buy_price = None

    def next(self):
        if self.order:
            return

        volume_condition = self.data.volume[0] > (self.volume_ma[0] * self.params.volume_threshold)

        if not self.position:
            # Buy signal: MACD crossover above signal line with high volume
            if (self.macd.macd[0] > self.macd.signal[0] and
                self.macd.macd[-1] <= self.macd.signal[-1] and
                volume_condition):
                self.order = self.buy()

        else:
            current_price = self.data.close[0]
            # Sell signals
            if (self.macd.macd[0] < self.macd.signal[0] or  # MACD below signal
                (self.buy_price and current_price <= self.buy_price * (1 - self.params.stop_loss)) or
                (self.buy_price and current_price >= self.buy_price * (1 + self.params.take_profit))):
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
            elif order.issell():
                self.buy_price = None
        self.order = None

class EnhancedAnalyzer(bt.Analyzer):
    """Enhanced analyzer for comprehensive performance metrics"""

    def __init__(self):
        self.trades = []
        self.equity_curve = []
        self.peak = 0
        self.drawdown = 0
        self.max_drawdown = 0

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                'entry_date': trade.dtopen,
                'exit_date': trade.dtclose,
                'entry_price': trade.price,
                'exit_price': trade.pnl / trade.size + trade.price,
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_net': trade.pnlcomm,
                'duration': (trade.dtclose - trade.dtopen).days,
                'commission': trade.commission
            })

    def next(self):
        portfolio_value = self.strategy.broker.getvalue()
        self.equity_curve.append({
            'date': self.data.datetime.date(0).isoformat(),
            'value': portfolio_value,
            'returns': (portfolio_value / self.strategy.broker.startingcash - 1) * 100
        })

        # Calculate drawdown
        if portfolio_value > self.peak:
            self.peak = portfolio_value

        self.drawdown = (self.peak - portfolio_value) / self.peak
        if self.drawdown > self.max_drawdown:
            self.max_drawdown = self.drawdown

    def get_analysis(self):
        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'max_drawdown': self.max_drawdown
        }

class QuantBacktester:
    """Enhanced quantitative backtesting framework"""

    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        self.cerebro = bt.Cerebro()
        self.initial_capital = initial_capital
        self.commission = commission
        self.results = None
        self.enhanced_analyzer = None

        # Set up broker
        self.cerebro.broker.setcash(initial_capital)
        self.cerebro.broker.setcommission(commission=commission)

        # Add analyzers
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
        self.enhanced_analyzer = EnhancedAnalyzer()
        self.cerebro.addanalyzer(self.enhanced_analyzer, _name='enhanced')

    def add_data(self, symbol: str, start_date: datetime, end_date: datetime,
                 timeframe: str = '1d') -> bool:
        """Add data feed for a symbol"""

        try:
            # Download data from Yahoo Finance
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, interval=timeframe)

            if data.empty:
                logger.warning(f"No data available for {symbol}")
                return False

            # Prepare data for backtrader
            data.index = pd.to_datetime(data.index)
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Create backtrader data feed
            data_feed = bt.feeds.PandasData(
                dataname=data,
                name=symbol,
                plot=False
            )

            self.cerebro.adddata(data_feed)
            logger.info(f"Added data for {symbol}: {len(data)} bars")
            return True

        except Exception as e:
            logger.error(f"Error adding data for {symbol}: {e}")
            return False

    def add_strategy(self, strategy_class, **params):
        """Add a trading strategy"""
        self.cerebro.addstrategy(strategy_class, **params)

    def run(self) -> Dict[str, Any]:
        """Run the backtest"""

        logger.info("Starting backtest...")
        self.results = self.cerebro.run()

        if not self.results:
            raise Exception("Backtest failed to produce results")

        logger.info("Backtest completed successfully")
        return self.get_comprehensive_results()

    def get_comprehensive_results(self) -> Dict[str, Any]:
        """Get comprehensive backtest results"""

        if not self.results:
            return {}

        strat = self.results[0]

        # Extract analyzer results
        trades_analysis = strat.analyzers.trades.get_analysis()
        sharpe_analysis = strat.analyzers.sharpe.get_analysis()
        returns_analysis = strat.analyzers.returns.get_analysis()
        drawdown_analysis = strat.analyzers.drawdown.get_analysis()
        timereturn_analysis = strat.analyzers.timereturn.get_analysis()
        enhanced_analysis = strat.analyzers.enhanced.get_analysis()

        # Calculate performance metrics
        final_value = self.cerebro.broker.getvalue()
        total_return = (final_value / self.initial_capital - 1) * 100

        # Calculate annual return
        start_date = min([dt.date() for dt in timereturn_analysis.keys()]) if timereturn_analysis else datetime.now().date()
        end_date = max([dt.date() for dt in timereturn_analysis.keys()]) if timereturn_analysis else datetime.now().date()
        years = (end_date - start_date).days / 365.25
        annual_return = ((final_value / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0

        # Trade statistics
        total_trades = trades_analysis.get('total', {}).get('total', 0)
        won_trades = trades_analysis.get('won', {}).get('total', 0)
        lost_trades = trades_analysis.get('lost', {}).get('total', 0)
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0

        # Profit factor
        gross_profit = trades_analysis.get('won', {}).get('pnl', {}).get('total', 0)
        gross_loss = abs(trades_analysis.get('lost', {}).get('pnl', {}).get('total', 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Enhanced metrics from custom analyzer
        enhanced_data = enhanced_analysis
        equity_curve = enhanced_data.get('equity_curve', [])
        trades_log = enhanced_data.get('trades', [])

        # Calculate additional metrics
        if equity_curve:
            returns_series = pd.Series([point['returns'] for point in equity_curve])
            volatility = returns_series.std() * np.sqrt(252)  # Annualized volatility

            # Sortino ratio (downside deviation)
            downside_returns = returns_series[returns_series < 0]
            downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
            sortino_ratio = (annual_return - 2) / downside_std if downside_std > 0 else 0  # Assuming 2% risk-free rate
        else:
            volatility = 0
            sortino_ratio = 0

        # Average trade duration
        avg_duration = np.mean([trade['duration'] for trade in trades_log]) if trades_log else 0

        # Best and worst trades
        best_trade = max([trade['pnl'] for trade in trades_log]) if trades_log else 0
        worst_trade = min([trade['pnl'] for trade in trades_log]) if trades_log else 0

        return {
            'performance': {
                'initial_capital': self.initial_capital,
                'final_capital': final_value,
                'total_return': total_return,
                'annual_return': annual_return,
                'sharpe_ratio': sharpe_analysis.get('sharperatio', 0) or 0,
                'sortino_ratio': sortino_ratio,
                'max_drawdown': drawdown_analysis.get('max', {}).get('drawdown', 0),
                'volatility': volatility,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': total_trades,
                'avg_trade_duration': avg_duration,
                'best_trade': best_trade,
                'worst_trade': worst_trade
            },
            'trades': trades_log,
            'equity_curve': equity_curve,
            'monthly_returns': self._calculate_monthly_returns(timereturn_analysis),
            'yearly_returns': self._calculate_yearly_returns(timereturn_analysis),
            'drawdown_analysis': self._calculate_drawdown_periods(equity_curve),
            'risk_metrics': self._calculate_risk_metrics(equity_curve)
        }

    def _calculate_monthly_returns(self, timereturn_analysis: Dict) -> List[Dict]:
        """Calculate monthly returns breakdown"""

        monthly_returns = []

        if not timereturn_analysis:
            return monthly_returns

        # Group returns by month
        monthly_data = {}
        for date, return_value in timereturn_analysis.items():
            month_key = f"{date.year}-{date.month:02d}"
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(return_value)

        # Calculate monthly returns
        for month, returns in monthly_data.items():
            monthly_return = (np.prod([1 + r for r in returns]) - 1) * 100
            monthly_returns.append({
                'month': month,
                'return': monthly_return,
                'trading_days': len(returns)
            })

        return sorted(monthly_returns, key=lambda x: x['month'])

    def _calculate_yearly_returns(self, timereturn_analysis: Dict) -> List[Dict]:
        """Calculate yearly returns breakdown"""

        yearly_returns = []

        if not timereturn_analysis:
            return yearly_returns

        # Group returns by year
        yearly_data = {}
        for date, return_value in timereturn_analysis.items():
            year = date.year
            if year not in yearly_data:
                yearly_data[year] = []
            yearly_data[year].append(return_value)

        # Calculate yearly returns
        for year, returns in yearly_data.items():
            yearly_return = (np.prod([1 + r for r in returns]) - 1) * 100
            yearly_returns.append({
                'year': year,
                'return': yearly_return,
                'trading_days': len(returns)
            })

        return sorted(yearly_returns, key=lambda x: x['year'])

    def _calculate_drawdown_periods(self, equity_curve: List[Dict]) -> List[Dict]:
        """Calculate detailed drawdown periods"""

        if not equity_curve:
            return []

        drawdown_periods = []
        peak = 0
        trough = 0
        in_drawdown = False
        dd_start = None

        for i, point in enumerate(equity_curve):
            value = point['value']
            date = point['date']

            if value > peak:
                # New peak - end any current drawdown
                if in_drawdown:
                    drawdown_periods.append({
                        'start_date': dd_start,
                        'end_date': equity_curve[i-1]['date'],
                        'peak_value': peak,
                        'trough_value': trough,
                        'drawdown_pct': ((peak - trough) / peak) * 100,
                        'duration_days': i - drawdown_periods[-1]['start_index'] if drawdown_periods else 0
                    })
                    in_drawdown = False

                peak = value
                trough = value
            else:
                # Potential drawdown
                if not in_drawdown:
                    in_drawdown = True
                    dd_start = date

                if value < trough:
                    trough = value

        # Handle ongoing drawdown
        if in_drawdown:
            drawdown_periods.append({
                'start_date': dd_start,
                'end_date': equity_curve[-1]['date'],
                'peak_value': peak,
                'trough_value': trough,
                'drawdown_pct': ((peak - trough) / peak) * 100,
                'duration_days': len(equity_curve) - len(drawdown_periods)
            })

        return drawdown_periods

    def _calculate_risk_metrics(self, equity_curve: List[Dict]) -> Dict[str, float]:
        """Calculate additional risk metrics"""

        if not equity_curve:
            return {}

        returns = [point['returns'] for point in equity_curve]
        returns_series = pd.Series(returns)

        # Value at Risk (95% and 99%)
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)

        # Conditional VaR (Expected Shortfall)
        cvar_95 = returns_series[returns_series <= var_95].mean()
        cvar_99 = returns_series[returns_series <= var_99].mean()

        # Skewness and Kurtosis
        skewness = returns_series.skew()
        kurtosis = returns_series.kurtosis()

        # Maximum consecutive losses
        consecutive_losses = 0
        max_consecutive_losses = 0

        for ret in returns:
            if ret < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0

        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'skewness': skewness,
            'kurtosis': kurtosis,
            'max_consecutive_losses': max_consecutive_losses,
            'upside_capture': len([r for r in returns if r > 0]) / len(returns) * 100,
            'downside_capture': len([r for r in returns if r < 0]) / len(returns) * 100
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        results = self.get_comprehensive_results()
        return results.get('performance', {})

    def get_trades_analysis(self) -> List[Dict]:
        """Get trades analysis"""
        results = self.get_comprehensive_results()
        return results.get('trades', [])

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get risk metrics"""
        results = self.get_comprehensive_results()
        return results.get('risk_metrics', {})

    def get_equity_curve(self) -> List[Dict]:
        """Get equity curve data"""
        results = self.get_comprehensive_results()
        return results.get('equity_curve', [])

    def get_drawdown_analysis(self) -> List[Dict]:
        """Get drawdown analysis"""
        results = self.get_comprehensive_results()
        return results.get('drawdown_analysis', [])

    def get_monthly_returns(self) -> List[Dict]:
        """Get monthly returns"""
        results = self.get_comprehensive_results()
        return results.get('monthly_returns', [])

    def get_yearly_returns(self) -> List[Dict]:
        """Get yearly returns"""
        results = self.get_comprehensive_results()
        return results.get('yearly_returns', [])

    def save_results(self, filepath: str):
        """Save backtest results to file"""

        if not self.results:
            raise Exception("No results to save. Run backtest first.")

        results = self.get_comprehensive_results()

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Results saved to {filepath}")

    def plot_results(self, save_path: Optional[str] = None, figsize: Tuple[int, int] = (15, 10)):
        """Plot comprehensive backtest results"""

        if not self.results:
            raise Exception("No results to plot. Run backtest first.")

        results = self.get_comprehensive_results()
        equity_curve = results.get('equity_curve', [])

        if not equity_curve:
            logger.warning("No equity curve data to plot")
            return

        # Extract data for plotting
        dates = [datetime.fromisoformat(point['date']) for point in equity_curve]
        values = [point['value'] for point in equity_curve]
        returns = [point['returns'] for point in equity_curve]

        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle('Backtest Results Dashboard', fontsize=16, fontweight='bold')

        # 1. Equity Curve
        ax1.plot(dates, values, linewidth=2, color='blue')
        ax1.axhline(y=self.initial_capital, color='red', linestyle='--', alpha=0.7, label='Initial Capital')
        ax1.set_title('Portfolio Equity Curve')
        ax1.set_ylabel('Portfolio Value ($)')
        ax1.grid(True, alpha=0.3)
        ax1.legend()

        # 2. Daily Returns
        ax2.plot(dates, returns, linewidth=1, color='green', alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_title('Daily Returns (%)')
        ax2.set_ylabel('Return (%)')
        ax2.grid(True, alpha=0.3)

        # 3. Returns Histogram
        ax3.hist(returns, bins=50, alpha=0.7, color='purple', edgecolor='black')
        ax3.axvline(x=np.mean(returns), color='red', linestyle='--', label=f'Mean: {np.mean(returns):.2f}%')
        ax3.set_title('Returns Distribution')
        ax3.set_xlabel('Return (%)')
        ax3.set_ylabel('Frequency')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Drawdown
        peak_values = []
        peak = values[0]
        for value in values:
            if value > peak:
                peak = value
            peak_values.append(peak)

        drawdowns = [(peak - value) / peak * 100 for peak, value in zip(peak_values, values)]

        ax4.fill_between(dates, drawdowns, 0, alpha=0.3, color='red')
        ax4.plot(dates, drawdowns, linewidth=1, color='darkred')
        ax4.set_title('Drawdown (%)')
        ax4.set_ylabel('Drawdown (%)')
        ax4.grid(True, alpha=0.3)
        ax4.invert_yaxis()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")

        return fig

# Factory function for different strategies
def create_strategy_backtester(strategy_type: str, **kwargs) -> QuantBacktester:
    """Create a backtester with a specific strategy"""

    backtester = QuantBacktester(**kwargs)

    if strategy_type == "moving_average":
        strategy_class = MovingAverageStrategy
    elif strategy_type == "mean_reversion":
        strategy_class = MeanReversionStrategy
    elif strategy_type == "momentum":
        strategy_class = MomentumStrategy
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return backtester, strategy_class

# Example usage function
def run_sample_backtest():
    """Run a sample backtest for demonstration"""

    # Create backtester
    backtester = QuantBacktester(initial_capital=100000)

    # Add data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 2)  # 2 years of data

    symbols = ['AAPL', 'MSFT', 'GOOGL']
    for symbol in symbols:
        backtester.add_data(symbol, start_date, end_date)

    # Add strategy
    backtester.add_strategy(MovingAverageStrategy, fast_period=10, slow_period=30)

    # Run backtest
    results = backtester.run()

    # Print summary
    performance = results['performance']
    print(f"\n{'='*50}")
    print("BACKTEST RESULTS SUMMARY")
    print(f"{'='*50}")
    print(f"Initial Capital: ${performance['initial_capital']:,.2f}")
    print(f"Final Capital: ${performance['final_capital']:,.2f}")
    print(f"Total Return: {performance['total_return']:.2f}%")
    print(f"Annual Return: {performance['annual_return']:.2f}%")
    print(f"Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {performance['max_drawdown']:.2f}%")
    print(f"Win Rate: {performance['win_rate']:.2f}%")
    print(f"Total Trades: {performance['total_trades']}")
    print(f"{'='*50}")

    return backtester

if __name__ == "__main__":
    # Run sample backtest
    backtester = run_sample_backtest()

    # Plot results
    backtester.plot_results(save_path="sample_backtest_results.png")