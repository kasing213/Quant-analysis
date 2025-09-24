# 📊 Portfolio Tracker with Advanced Backtesting

A comprehensive portfolio management and backtesting platform built with Python, Streamlit, and Interactive Brokers integration.

![Python](https://img.shields.io/badge/python-v3.12+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-latest-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🚀 Features

### Portfolio Management
- **Real-time Portfolio Tracking**: Monitor positions and P&L in real-time
- **Interactive Brokers Integration**: Live data feeds and trading capabilities
- **Paper Trading Mode**: Risk-free testing environment
- **Performance Analytics**: Comprehensive portfolio analysis and metrics

### Advanced Backtesting
- **Multiple Strategies**: Moving Average, RSI Mean Reversion, Bollinger Bands
- **Interactive Parameter Tuning**: Real-time strategy optimization
- **Risk Management**: Configurable stop losses and take profits
- **Performance Analysis**: Sharpe ratio, drawdown, win rates, and more
- **Strategy Comparison**: Side-by-side performance analysis
- **Visual Charts**: Comprehensive backtesting visualizations

### Technical Capabilities
- **Data Sources**: Yahoo Finance with Interactive Brokers fallback
- **Real-time Updates**: Live price feeds and portfolio synchronization
- **Robust Error Handling**: Graceful degradation when services unavailable
- **Scalable Architecture**: Modular design for easy extension

## 🛠️ Installation

### Prerequisites
- Python 3.12+
- Interactive Brokers TWS or IB Gateway (optional, for live data)

### Setup
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/portfolio-backtesting-tracker.git
cd portfolio-backtesting-tracker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🚀 Quick Start

### Launch Portfolio Tracker
```bash
# Activate virtual environment
source .venv/bin/activate

# Start the application
streamlit run portfolio_tracker.py
```

Navigate to `http://localhost:8501` to access the application.

### Application Tabs
1. **📊 Positions**: Current portfolio holdings and P&L
2. **📈 Performance**: Portfolio performance charts and analytics
3. **📋 Trades**: Trading history and transaction analysis
4. **🎯 Analytics**: Advanced portfolio analytics and insights
5. **🔍 Backtesting**: Strategy backtesting and optimization

## 💡 Backtesting Strategies

### Moving Average Crossover
- **Signal**: Fast MA crosses above/below Slow MA
- **Parameters**: Fast period, Slow period
- **Best For**: Trending markets

### RSI Mean Reversion
- **Signal**: RSI oversold (<30) / overbought (>70)
- **Parameters**: RSI period, overbought/oversold levels
- **Best For**: Range-bound markets

### Bollinger Bands
- **Signal**: Price touches upper/lower bands
- **Parameters**: Period, standard deviation factor
- **Best For**: Volatile markets with mean reversion

## 📊 Example Usage

### Basic Backtesting
```python
from core.backtester import PortfolioBacktester, MovingAverageStrategy

# Initialize backtester
backtester = PortfolioBacktester(initial_cash=100000)

# Run backtest
result = backtester.run_backtest(
    symbol='AAPL',
    strategy_class=MovingAverageStrategy,
    strategy_params={'fast_period': 10, 'slow_period': 30},
    start_date='2022-01-01',
    end_date='2024-01-01'
)

# View results
metrics = result.get_performance_metrics()
print(f"Total Return: {metrics['Total Return']:.2f}%")
print(f"Sharpe Ratio: {metrics['Sharpe Ratio']:.3f}")
```

## 🔧 Configuration

### Interactive Brokers Setup
1. Install and configure TWS or IB Gateway
2. Enable API connections in TWS settings
3. Configure paper trading account (recommended for testing)

See `IB_SETUP.md` for detailed setup instructions.

### Environment Variables
Create a `.env` file:
```env
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
PAPER_TRADING=true
```

## 📁 Project Structure

```
portfolio-backtesting-tracker/
├── core/
│   ├── backtester.py        # Backtesting framework
│   ├── ib_client.py         # Interactive Brokers client
│   ├── portfolio_manager.py # Portfolio management
│   ├── data_manager.py      # Data feeds and processing
│   └── analytics.py         # Performance analytics
├── portfolio_tracker.py    # Main Streamlit application
├── requirements.txt         # Python dependencies
├── SESSION_SUMMARY.md       # Development session notes
└── README.md               # This file
```

## 🎯 Performance Metrics

The backtesting system provides comprehensive performance analysis:

- **Return Metrics**: Total return, annualized return, CAGR
- **Risk Metrics**: Sharpe ratio, Sortino ratio, maximum drawdown
- **Trading Metrics**: Win rate, profit factor, average trade
- **Statistical Analysis**: Standard deviation, skewness, kurtosis

## 🔄 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📈 Roadmap

- [ ] Additional backtesting strategies (MACD, Stochastic)
- [ ] Portfolio optimization algorithms
- [ ] Multi-timeframe analysis
- [ ] Options trading support
- [ ] Cryptocurrency integration
- [ ] Machine learning strategies

## ⚠️ Disclaimer

This software is for educational and research purposes only. Past performance does not guarantee future results. Always consult with qualified financial advisors before making investment decisions.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/) for the web interface
- [Backtrader](https://www.backtrader.com/) for backtesting framework
- [Interactive Brokers API](https://interactivebrokers.github.io/tws-api/) for live data
- [Yahoo Finance](https://pypi.org/project/yfinance/) for historical data

---

**Happy Trading! 📈**