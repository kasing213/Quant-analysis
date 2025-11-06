/**
 * Backtesting Dashboard Module
 * Handles backtesting functionality, results visualization, and strategy comparison
 */

class BacktestingDashboard {
    constructor() {
        this.baseUrl = '/api/v1/backtesting';
        this.runningBacktests = new Map();
        this.charts = new Map();
        this.refreshInterval = null;

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAvailableStrategies();
        this.loadAvailableSymbols();
        this.loadBacktestHistory();
        this.startPolling();
    }

    bindEvents() {
        // Strategy form submission
        const strategyForm = document.getElementById('strategy-form');
        if (strategyForm) {
            strategyForm.addEventListener('submit', (e) => this.handleStrategySubmission(e));
        }

        // Results filtering
        const filterSelect = document.getElementById('results-filter');
        if (filterSelect) {
            filterSelect.addEventListener('change', () => this.filterResults());
        }

        // Strategy comparison
        const compareBtn = document.getElementById('compare-strategies');
        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.compareStrategies());
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-backtests');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshDashboard());
        }

        // Export results
        const exportBtn = document.getElementById('export-results');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportResults());
        }
    }

    async loadAvailableStrategies() {
        try {
            const response = await fetch(`${this.baseUrl}/strategies`);
            const data = await response.json();

            this.populateStrategySelect(data.strategies);
            this.setupStrategyParameterForms(data.strategies);
        } catch (error) {
            console.error('Error loading strategies:', error);
            this.showError('Failed to load available strategies');
        }
    }

    populateStrategySelect(strategies) {
        const select = document.getElementById('strategy-select');
        if (!select) return;

        select.innerHTML = '<option value="">Select a strategy...</option>';

        strategies.forEach(strategy => {
            const option = document.createElement('option');
            option.value = strategy.name;
            option.textContent = strategy.display_name;
            option.title = strategy.description;
            select.appendChild(option);
        });

        select.addEventListener('change', (e) => {
            this.updateStrategyParameters(e.target.value, strategies);
        });
    }

    setupStrategyParameterForms(strategies) {
        this.strategiesConfig = {};
        strategies.forEach(strategy => {
            this.strategiesConfig[strategy.name] = strategy;
        });
    }

    updateStrategyParameters(strategyName, strategies) {
        const container = document.getElementById('strategy-parameters');
        if (!container) return;

        container.innerHTML = '';

        if (!strategyName) return;

        const strategy = strategies.find(s => s.name === strategyName);
        if (!strategy || !strategy.parameters) return;

        const parametersHtml = Object.entries(strategy.parameters).map(([param, config]) => `
            <div class="parameter-group">
                <label for="param-${param}">${this.formatParameterName(param)}</label>
                <input
                    type="${config.type === 'int' ? 'number' : config.type === 'float' ? 'number' : 'text'}"
                    id="param-${param}"
                    name="${param}"
                    value="${config.default}"
                    min="${config.min || ''}"
                    max="${config.max || ''}"
                    step="${config.type === 'float' ? '0.01' : '1'}"
                    class="form-control"
                />
                <small class="form-text text-muted">
                    Default: ${config.default}
                    ${config.min !== undefined ? `, Min: ${config.min}` : ''}
                    ${config.max !== undefined ? `, Max: ${config.max}` : ''}
                </small>
            </div>
        `).join('');

        container.innerHTML = `
            <h4>Strategy Parameters</h4>
            <div class="parameters-grid">
                ${parametersHtml}
            </div>
        `;
    }

    formatParameterName(param) {
        return param.replace(/_/g, ' ')
                   .replace(/\b\w/g, l => l.toUpperCase());
    }

    async loadAvailableSymbols() {
        try {
            const response = await fetch(`${this.baseUrl}/market-data/symbols`);
            const data = await response.json();

            this.populateSymbolSelect(data.symbols);
        } catch (error) {
            console.error('Error loading symbols:', error);
        }
    }

    populateSymbolSelect(symbols) {
        const container = document.getElementById('symbols-container');
        if (!container) return;

        const symbolsHtml = symbols.map(symbol => `
            <div class="symbol-option">
                <input type="checkbox" id="symbol-${symbol.symbol}" value="${symbol.symbol}" class="symbol-checkbox">
                <label for="symbol-${symbol.symbol}" title="${symbol.name} - ${symbol.sector}">
                    <span class="symbol-code">${symbol.symbol}</span>
                    <span class="symbol-name">${symbol.name}</span>
                    <span class="symbol-sector">${symbol.sector}</span>
                </label>
            </div>
        `).join('');

        container.innerHTML = symbolsHtml;

        // Add quick select buttons
        const quickSelectHtml = `
            <div class="quick-select-buttons">
                <button type="button" class="btn btn-sm btn-outline-primary" onclick="backtestingDashboard.selectSymbolGroup('tech')">Tech Stocks</button>
                <button type="button" class="btn btn-sm btn-outline-primary" onclick="backtestingDashboard.selectSymbolGroup('etf')">ETFs</button>
                <button type="button" class="btn btn-sm btn-outline-primary" onclick="backtestingDashboard.selectSymbolGroup('all')">Select All</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="backtestingDashboard.selectSymbolGroup('none')">Clear All</button>
            </div>
        `;

        container.insertAdjacentHTML('afterbegin', quickSelectHtml);
    }

    selectSymbolGroup(group) {
        const checkboxes = document.querySelectorAll('.symbol-checkbox');

        checkboxes.forEach(checkbox => {
            const symbolData = checkbox.value;

            switch(group) {
                case 'tech':
                    checkbox.checked = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META'].includes(symbolData);
                    break;
                case 'etf':
                    checkbox.checked = ['SPY', 'QQQ', 'GLD', 'TLT'].includes(symbolData);
                    break;
                case 'all':
                    checkbox.checked = true;
                    break;
                case 'none':
                    checkbox.checked = false;
                    break;
            }
        });
    }

    async handleStrategySubmission(event) {
        event.preventDefault();

        const formData = new FormData(event.target);

        // Get selected symbols
        const selectedSymbols = Array.from(document.querySelectorAll('.symbol-checkbox:checked'))
                                    .map(cb => cb.value);

        if (selectedSymbols.length === 0) {
            this.showError('Please select at least one symbol');
            return;
        }

        // Get strategy parameters
        const strategyParams = {};
        const parameterInputs = document.querySelectorAll('#strategy-parameters input');
        parameterInputs.forEach(input => {
            const value = input.type === 'number' ? parseFloat(input.value) : input.value;
            strategyParams[input.name] = value;
        });

        const backtestConfig = {
            strategy: formData.get('strategy'),
            symbols: selectedSymbols,
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date'),
            initial_capital: parseFloat(formData.get('initial_capital')),
            strategy_params: strategyParams
        };

        this.submitBacktest(backtestConfig);
    }

    async submitBacktest(config) {
        try {
            this.showLoading('Submitting backtest...');

            const response = await fetch(`${this.baseUrl}/run`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess(`Backtest submitted successfully! ID: ${data.backtest_id}`);
                this.runningBacktests.set(data.backtest_id, {
                    config: config,
                    startTime: new Date(),
                    status: 'running'
                });
                this.updateRunningBacktests();
            } else {
                this.showError(`Failed to submit backtest: ${data.detail}`);
            }
        } catch (error) {
            console.error('Error submitting backtest:', error);
            this.showError('Failed to submit backtest');
        } finally {
            this.hideLoading();
        }
    }

    async loadBacktestHistory() {
        try {
            const response = await fetch(`${this.baseUrl}/list`);
            const data = await response.json();

            this.displayBacktestHistory(data.backtests);
        } catch (error) {
            console.error('Error loading backtest history:', error);
        }
    }

    displayBacktestHistory(backtests) {
        const container = document.getElementById('backtest-history');
        if (!container) return;

        if (backtests.length === 0) {
            container.innerHTML = '<p class="text-muted">No backtests found. Run your first backtest to see results here.</p>';
            return;
        }

        const historyHtml = backtests.map(backtest => `
            <div class="backtest-item ${backtest.status}" data-backtest-id="${backtest.backtest_id}">
                <div class="backtest-header">
                    <div class="backtest-title">
                        <span class="strategy-name">${this.formatStrategyName(backtest.parameters?.strategy)}</span>
                        <span class="backtest-id">#${backtest.backtest_id}</span>
                    </div>
                    <div class="backtest-status">
                        <span class="status-badge status-${backtest.status}">${backtest.status.toUpperCase()}</span>
                        ${backtest.status === 'running' ? `<span class="progress-indicator">${backtest.progress || 0}%</span>` : ''}
                    </div>
                </div>

                <div class="backtest-details">
                    <div class="detail-item">
                        <strong>Symbols:</strong> ${backtest.parameters?.symbols?.join(', ') || 'N/A'}
                    </div>
                    <div class="detail-item">
                        <strong>Period:</strong> ${this.formatDate(backtest.parameters?.start_date)} - ${this.formatDate(backtest.parameters?.end_date)}
                    </div>
                    <div class="detail-item">
                        <strong>Capital:</strong> $${this.formatNumber(backtest.parameters?.initial_capital)}
                    </div>
                    <div class="detail-item">
                        <strong>Started:</strong> ${this.formatDateTime(backtest.started_at)}
                    </div>
                    ${backtest.completed_at ? `
                        <div class="detail-item">
                            <strong>Completed:</strong> ${this.formatDateTime(backtest.completed_at)}
                        </div>
                    ` : ''}
                </div>

                <div class="backtest-actions">
                    ${backtest.status === 'completed' ? `
                        <button class="btn btn-sm btn-primary" onclick="backtestingDashboard.viewResults('${backtest.backtest_id}')">
                            View Results
                        </button>
                        <button class="btn btn-sm btn-outline-primary" onclick="backtestingDashboard.addToComparison('${backtest.backtest_id}')">
                            Add to Compare
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-outline-danger" onclick="backtestingDashboard.deleteBacktest('${backtest.backtest_id}')">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = historyHtml;
    }

    async viewResults(backtestId) {
        try {
            this.showLoading('Loading results...');

            const response = await fetch(`${this.baseUrl}/results/${backtestId}`);
            const data = await response.json();

            if (response.ok && data.status === 'completed') {
                this.displayResults(data);
            } else {
                this.showError('Results not available or backtest not completed');
            }
        } catch (error) {
            console.error('Error loading results:', error);
            this.showError('Failed to load results');
        } finally {
            this.hideLoading();
        }
    }

    displayResults(backtestData) {
        const modal = this.createResultsModal(backtestData);
        document.body.appendChild(modal);

        // Show modal
        $(modal).modal('show');

        // Generate charts
        this.generateResultsCharts(backtestData);

        // Cleanup when modal is closed
        $(modal).on('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    createResultsModal(data) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'results-modal';
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Backtest Results - ${data.backtest_id}</h5>
                        <button type="button" class="close" data-dismiss="modal">
                            <span>&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        ${this.generateResultsContent(data)}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="backtestingDashboard.exportResults('${data.backtest_id}')">
                            Export Results
                        </button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    generateResultsContent(data) {
        const performance = data.results?.performance || {};
        const riskMetrics = data.results?.risk_metrics || {};

        return `
            <div class="results-container">
                <!-- Performance Summary -->
                <div class="row mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Performance Summary</h6>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-3">
                                        <div class="metric-item">
                                            <div class="metric-value ${performance.total_return >= 0 ? 'positive' : 'negative'}">
                                                ${this.formatPercentage(performance.total_return)}
                                            </div>
                                            <div class="metric-label">Total Return</div>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="metric-item">
                                            <div class="metric-value">${this.formatNumber(performance.sharpe_ratio, 2)}</div>
                                            <div class="metric-label">Sharpe Ratio</div>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="metric-item">
                                            <div class="metric-value negative">${this.formatPercentage(performance.max_drawdown)}</div>
                                            <div class="metric-label">Max Drawdown</div>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="metric-item">
                                            <div class="metric-value">${this.formatPercentage(performance.win_rate)}</div>
                                            <div class="metric-label">Win Rate</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Charts -->
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Equity Curve</h6>
                            </div>
                            <div class="card-body">
                                <div id="equity-curve-chart" style="height: 300px;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Drawdown</h6>
                            </div>
                            <div class="card-body">
                                <div id="drawdown-chart" style="height: 300px;"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Monthly Returns</h6>
                            </div>
                            <div class="card-body">
                                <div id="monthly-returns-chart" style="height: 300px;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Returns Distribution</h6>
                            </div>
                            <div class="card-body">
                                <div id="returns-distribution-chart" style="height: 300px;"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Detailed Metrics -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Performance Metrics</h6>
                            </div>
                            <div class="card-body">
                                <table class="table table-sm">
                                    <tbody>
                                        <tr><td>Annual Return</td><td>${this.formatPercentage(performance.annual_return)}</td></tr>
                                        <tr><td>Volatility</td><td>${this.formatPercentage(performance.volatility)}</td></tr>
                                        <tr><td>Sortino Ratio</td><td>${this.formatNumber(performance.sortino_ratio, 2)}</td></tr>
                                        <tr><td>Profit Factor</td><td>${this.formatNumber(performance.profit_factor, 2)}</td></tr>
                                        <tr><td>Total Trades</td><td>${performance.total_trades}</td></tr>
                                        <tr><td>Avg Trade Duration</td><td>${this.formatNumber(performance.avg_trade_duration, 1)} days</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Risk Metrics</h6>
                            </div>
                            <div class="card-body">
                                <table class="table table-sm">
                                    <tbody>
                                        <tr><td>VaR (95%)</td><td>${this.formatPercentage(riskMetrics.var_95)}</td></tr>
                                        <tr><td>CVaR (95%)</td><td>${this.formatPercentage(riskMetrics.cvar_95)}</td></tr>
                                        <tr><td>Skewness</td><td>${this.formatNumber(riskMetrics.skewness, 2)}</td></tr>
                                        <tr><td>Kurtosis</td><td>${this.formatNumber(riskMetrics.kurtosis, 2)}</td></tr>
                                        <tr><td>Max Consecutive Losses</td><td>${riskMetrics.max_consecutive_losses}</td></tr>
                                        <tr><td>Upside Capture</td><td>${this.formatPercentage(riskMetrics.upside_capture)}</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    generateResultsCharts(data) {
        const equityData = data.results?.equity_curve || [];
        const monthlyReturns = data.results?.monthly_returns || [];

        // Equity Curve Chart
        if (equityData.length > 0) {
            const equityTrace = {
                x: equityData.map(d => d.date),
                y: equityData.map(d => d.value),
                type: 'scatter',
                mode: 'lines',
                name: 'Portfolio Value',
                line: { color: '#007bff', width: 2 }
            };

            Plotly.newPlot('equity-curve-chart', [equityTrace], {
                title: '',
                xaxis: { title: 'Date' },
                yaxis: { title: 'Portfolio Value ($)' },
                margin: { t: 20, r: 20, b: 40, l: 60 }
            });
        }

        // Drawdown Chart
        if (equityData.length > 0) {
            const drawdownData = this.calculateDrawdown(equityData);
            const drawdownTrace = {
                x: drawdownData.map(d => d.date),
                y: drawdownData.map(d => d.drawdown),
                type: 'scatter',
                mode: 'lines',
                fill: 'tozeroy',
                name: 'Drawdown',
                line: { color: '#dc3545' },
                fillcolor: 'rgba(220, 53, 69, 0.3)'
            };

            Plotly.newPlot('drawdown-chart', [drawdownTrace], {
                title: '',
                xaxis: { title: 'Date' },
                yaxis: { title: 'Drawdown (%)' },
                margin: { t: 20, r: 20, b: 40, l: 60 }
            });
        }

        // Monthly Returns Chart
        if (monthlyReturns.length > 0) {
            const monthlyTrace = {
                x: monthlyReturns.map(d => d.month),
                y: monthlyReturns.map(d => d.return),
                type: 'bar',
                name: 'Monthly Return',
                marker: {
                    color: monthlyReturns.map(d => d.return >= 0 ? '#28a745' : '#dc3545')
                }
            };

            Plotly.newPlot('monthly-returns-chart', [monthlyTrace], {
                title: '',
                xaxis: { title: 'Month' },
                yaxis: { title: 'Return (%)' },
                margin: { t: 20, r: 20, b: 40, l: 60 }
            });
        }

        // Returns Distribution
        if (equityData.length > 0) {
            const returns = equityData.map(d => d.returns).filter(r => r !== undefined);

            const histTrace = {
                x: returns,
                type: 'histogram',
                nbinsx: 30,
                name: 'Returns Distribution',
                marker: { color: '#17a2b8', opacity: 0.7 }
            };

            Plotly.newPlot('returns-distribution-chart', [histTrace], {
                title: '',
                xaxis: { title: 'Return (%)' },
                yaxis: { title: 'Frequency' },
                margin: { t: 20, r: 20, b: 40, l: 60 }
            });
        }
    }

    calculateDrawdown(equityData) {
        let peak = 0;
        return equityData.map(point => {
            if (point.value > peak) {
                peak = point.value;
            }
            const drawdown = ((peak - point.value) / peak) * 100;
            return {
                date: point.date,
                drawdown: -drawdown // Negative for visual display
            };
        });
    }

    startPolling() {
        this.refreshInterval = setInterval(() => {
            this.checkRunningBacktests();
        }, 5000); // Check every 5 seconds
    }

    async checkRunningBacktests() {
        for (const [backtestId, info] of this.runningBacktests.entries()) {
            if (info.status !== 'running') continue;

            try {
                const response = await fetch(`${this.baseUrl}/results/${backtestId}`);
                const data = await response.json();

                if (data.status === 'completed' || data.status === 'failed') {
                    this.runningBacktests.set(backtestId, {
                        ...info,
                        status: data.status
                    });

                    if (data.status === 'completed') {
                        this.showSuccess(`Backtest ${backtestId} completed successfully!`);
                    } else {
                        this.showError(`Backtest ${backtestId} failed: ${data.error}`);
                    }

                    this.loadBacktestHistory(); // Refresh the history
                }
            } catch (error) {
                console.error(`Error checking backtest ${backtestId}:`, error);
            }
        }
    }

    // Utility methods
    formatStrategyName(strategy) {
        if (!strategy) return 'Unknown';
        return strategy.replace(/_/g, ' ')
                      .replace(/\b\w/g, l => l.toUpperCase());
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString();
    }

    formatDateTime(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString();
    }

    formatNumber(value, decimals = 0) {
        if (value === null || value === undefined) return 'N/A';
        return Number(value).toFixed(decimals);
    }

    formatPercentage(value) {
        if (value === null || value === undefined) return 'N/A';
        return `${Number(value).toFixed(2)}%`;
    }

    showError(message) {
        // Implement toast or alert system
        console.error(message);
        alert(message); // Temporary - replace with proper toast
    }

    showSuccess(message) {
        // Implement toast or alert system
        console.log(message);
        alert(message); // Temporary - replace with proper toast
    }

    showLoading(message) {
        // Implement loading spinner
        console.log(`Loading: ${message}`);
    }

    hideLoading() {
        // Hide loading spinner
        console.log('Loading complete');
    }

    async deleteBacktest(backtestId) {
        if (!confirm('Are you sure you want to delete this backtest?')) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/results/${backtestId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showSuccess('Backtest deleted successfully');
                this.loadBacktestHistory();
                this.runningBacktests.delete(backtestId);
            } else {
                this.showError('Failed to delete backtest');
            }
        } catch (error) {
            console.error('Error deleting backtest:', error);
            this.showError('Failed to delete backtest');
        }
    }

    refreshDashboard() {
        this.loadBacktestHistory();
        this.checkRunningBacktests();
    }

    // Initialize when DOM is ready
    static init() {
        window.backtestingDashboard = new BacktestingDashboard();
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', BacktestingDashboard.init);
} else {
    BacktestingDashboard.init();
}