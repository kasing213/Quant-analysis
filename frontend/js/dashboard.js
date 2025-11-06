// Dashboard Controller

class Dashboard {
    constructor() {
        this.activeTab = 'overview';
        this.refreshInterval = null;
        this.autoRefreshEnabled = true;
        this.refreshRate = 30000; // 30 seconds
        this.watchlist = null; // Will be initialized from API
        this.availableSymbols = []; // Available symbols from market data API
        this.defaultWatchlist = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT']; // Fallback if API fails
        this.darkMode = Storage.get('darkMode', false);
        this.soundAlerts = Storage.get('soundAlerts', false);

        this.initializeWatchlist();
        this.initializeEventListeners();
        this.initializeTheme();
        this.loadDashboard();
        this.startAutoRefresh();
    }

    /**
     * Initialize watchlist from API or local storage
     */
    async initializeWatchlist() {
        try {
            // Try to fetch available symbols from the API
            const response = await window.apiClient.getAvailableSymbols();
            if (response && response.symbols && response.symbols.length > 0) {
                this.availableSymbols = response.symbols;

                // Get user's saved watchlist or use first 4 available symbols as default
                const savedWatchlist = Storage.get('watchlist', null);
                if (savedWatchlist && Array.isArray(savedWatchlist) && savedWatchlist.length > 0) {
                    // Validate saved watchlist against available symbols
                    this.watchlist = savedWatchlist.filter(symbol =>
                        this.availableSymbols.includes(symbol)
                    );

                    // If all symbols were filtered out, use defaults
                    if (this.watchlist.length === 0) {
                        this.watchlist = this.availableSymbols.slice(0, 4);
                        Storage.set('watchlist', this.watchlist);
                    }
                } else {
                    // Use first 4 available symbols as default
                    this.watchlist = this.availableSymbols.slice(0, 4);
                    Storage.set('watchlist', this.watchlist);
                }

                console.log(`Initialized watchlist from API: ${this.watchlist.join(', ')}`);
            } else {
                throw new Error('No symbols available from API');
            }
        } catch (error) {
            console.warn('Failed to fetch symbols from API, using fallback:', error);

            // Fallback to saved watchlist or default
            this.watchlist = Storage.get('watchlist', this.defaultWatchlist);
            this.availableSymbols = this.watchlist;
        }
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            });
        });

        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }

        // Watchlist management
        const addStockBtn = document.getElementById('addStockBtn');
        const addStockInput = document.getElementById('addStockInput');

        if (addStockBtn && addStockInput) {
            addStockBtn.addEventListener('click', () => this.addToWatchlist());
            addStockInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.addToWatchlist();
            });
        }

        // Settings
        const autoRefreshCheckbox = document.getElementById('autoRefresh');
        const soundAlertsCheckbox = document.getElementById('soundAlerts');
        const darkModeCheckbox = document.getElementById('darkMode');

        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.checked = this.autoRefreshEnabled;
            autoRefreshCheckbox.addEventListener('change', (e) => {
                this.autoRefreshEnabled = e.target.checked;
                Storage.set('autoRefresh', this.autoRefreshEnabled);

                if (this.autoRefreshEnabled) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        if (soundAlertsCheckbox) {
            soundAlertsCheckbox.checked = this.soundAlerts;
            soundAlertsCheckbox.addEventListener('change', (e) => {
                this.soundAlerts = e.target.checked;
                Storage.set('soundAlerts', this.soundAlerts);
            });
        }

        if (darkModeCheckbox) {
            darkModeCheckbox.checked = this.darkMode;
            darkModeCheckbox.addEventListener('change', (e) => {
                this.darkMode = e.target.checked;
                this.toggleTheme();
            });
        }

        // Pipeline switcher
        const pipelineSelect = document.getElementById('pipelineSelect');
        const switchPipelineBtn = document.getElementById('switchPipelineBtn');

        if (pipelineSelect && switchPipelineBtn) {
            pipelineSelect.addEventListener('change', (e) => {
                switchPipelineBtn.disabled = !e.target.value;
            });

            switchPipelineBtn.addEventListener('click', () => this.switchPipeline());
        }

        // Performance controls
        const performancePeriod = document.getElementById('performancePeriod');
        const benchmarkSelect = document.getElementById('benchmarkSelect');

        if (performancePeriod) {
            performancePeriod.addEventListener('change', () => this.updatePerformanceChart());
        }

        if (benchmarkSelect) {
            benchmarkSelect.addEventListener('change', () => this.updatePerformanceChart());
        }

        // Trade modal
        this.initializeTradeModal();

        // WebSocket events
        if (window.eventEmitter) {
            window.eventEmitter.on('ws:connected', () => this.updateConnectionStatus(true));
            window.eventEmitter.on('ws:disconnected', () => this.updateConnectionStatus(false));
            window.eventEmitter.on('ws:market_data', (data) => this.handleMarketData(data));
            window.eventEmitter.on('ws:portfolio_update', (data) => this.handlePortfolioUpdate(data));
        }
    }

    /**
     * Handle real-time market data updates
     * @param {Object} data - Market data payload
     */
    handleMarketData(data) {
        if (data && data.payload) {
            this.renderWatchlist(data.payload);
            this.renderMarketDataGrid(data.payload);

            // Play sound alert if enabled and price moved significantly
            if (this.soundAlerts) {
                this.checkPriceAlerts(data.payload);
            }
        }
    }

    /**
     * Handle portfolio updates
     * @param {Object} data - Portfolio update data
     */
    handlePortfolioUpdate(data) {
        if (data) {
            this.updatePortfolioMetrics(data);
            if (this.activeTab === 'positions') {
                this.loadPositionsData();
            }
        }
    }

    /**
     * Handle trade updates
     * @param {Object} data - Trade update data
     */
    handleTradeUpdate(data) {
        if (data && this.activeTab === 'trades') {
            this.loadTradesData();
        }

        // Show notification for trade updates
        if (data && data.status) {
            const message = `Trade ${data.status}: ${data.trade_type} ${data.quantity} ${data.symbol}`;
            showNotification(message, data.status === 'filled' ? 'success' : 'info');
        }
    }

    /**
     * Check for price alerts
     * @param {Object} marketData - Market data
     */
    checkPriceAlerts(marketData) {
        // Simple price alert for demo - could be enhanced with user-defined alerts
        Object.values(marketData).forEach(quote => {
            if (Math.abs(quote.change_percent) > 0.05) { // 5% move
                this.playAlertSound();
            }
        });
    }

    /**
     * Play alert sound
     */
    playAlertSound() {
        // Create a simple beep sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);

        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.1);
    }

    /**
     * Initialize theme
     */
    initializeTheme() {
        if (this.darkMode) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }

        if (window.chartManager) {
            window.chartManager.setTheme(this.darkMode ? 'dark' : 'light');
        }
    }

    /**
     * Toggle theme
     */
    toggleTheme() {
        this.darkMode = !this.darkMode;
        Storage.set('darkMode', this.darkMode);
        this.initializeTheme();
    }

    /**
     * Switch tabs
     * @param {string} tabName - Tab name to switch to
     */
    switchTab(tabName) {
        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update active tab content
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        document.getElementById(tabName).classList.add('active');

        this.activeTab = tabName;

        // Load tab-specific data
        this.loadTabData(tabName);
    }

    /**
     * Load dashboard data
     */
    async loadDashboard() {
        try {
            await this.updateConnectionStatus(false);

            // Load initial data for all tabs
            await Promise.all([
                this.loadOverviewData(),
                this.loadPerformanceData(),
                this.loadPositionsData(),
                this.loadTradesData(),
                this.loadAnalyticsData(),
                this.loadPipelineStatus()
            ]);

            // Update connection status
            await this.testConnection();

        } catch (error) {
            console.error('Failed to load dashboard:', error);
            showNotification('Failed to load dashboard data', 'error');
        }
    }

    /**
     * Load tab-specific data
     * @param {string} tabName - Tab name
     */
    async loadTabData(tabName) {
        switch (tabName) {
            case 'overview':
                await this.loadOverviewData();
                break;
            case 'performance':
                await this.loadPerformanceData();
                break;
            case 'positions':
                await this.loadPositionsData();
                break;
            case 'trades':
                await this.loadTradesData();
                break;
            case 'analytics':
                await this.loadAnalyticsData();
                break;
        }
    }

    /**
     * Load overview tab data
     */
    async loadOverviewData() {
        try {
            // Load portfolio summary
            const portfolioData = await window.apiClient.getPortfolioSummary().catch(() => null);
            this.updatePortfolioMetrics(portfolioData);

            // Load market data for watchlist
            await this.updateWatchlistData();

            // Load portfolio chart
            await this.updatePortfolioChart();

            // Load allocation chart
            await this.updateAllocationChart();

        } catch (error) {
            console.error('Failed to load overview data:', error);
        }
    }

    /**
     * Load performance tab data
     */
    async loadPerformanceData() {
        try {
            await this.updatePerformanceChart();
            await this.updatePerformanceMetrics();
        } catch (error) {
            console.error('Failed to load performance data:', error);
        }
    }

    /**
     * Load positions tab data
     */
    async loadPositionsData() {
        try {
            const positions = await window.apiClient.getPortfolioPositions().catch(() => []);
            this.updatePositionsTable(positions);
        } catch (error) {
            console.error('Failed to load positions data:', error);
            this.updatePositionsTable([]);
        }
    }

    /**
     * Load trades tab data
     */
    async loadTradesData() {
        try {
            const tradesData = await window.apiClient.getTrades(100).catch(() => ({ trades: [] }));
            this.updateTradesTable(tradesData.trades || []);
        } catch (error) {
            console.error('Failed to load trades data:', error);
            this.updateTradesTable([]);
        }
    }

    /**
     * Load analytics tab data
     */
    async loadAnalyticsData() {
        try {
            const analytics = await window.apiClient.getPortfolioAnalytics();
            this.updateRiskMetrics(analytics.risk);
            this.updatePerformanceAnalytics(analytics.performance);
            this.updateAnalyticsCharts(analytics);
        } catch (error) {
            console.error('Failed to load analytics data:', error);
        }
    }

    /**
     * Update risk metrics display
     * @param {Object} riskData - Risk metrics data
     */
    updateRiskMetrics(riskData) {
        const riskContainer = document.getElementById('riskMetrics');
        if (!riskContainer) return;

        const metrics = [
            { label: 'Portfolio Beta', value: riskData.portfolio_beta, format: 'number' },
            { label: 'Sharpe Ratio', value: riskData.sharpe_ratio, format: 'number' },
            { label: 'Max Drawdown', value: riskData.max_drawdown, format: 'percentage' },
            { label: 'VaR (95%)', value: riskData.var_95, format: 'currency' },
            { label: 'Concentration Risk', value: riskData.concentration_risk, format: 'percentage' }
        ];

        riskContainer.innerHTML = metrics.map(metric => `
            <div class="metric-row">
                <span class="metric-label">${metric.label}</span>
                <span class="metric-value">${this.formatMetricValue(metric.value, metric.format)}</span>
            </div>
        `).join('');
    }

    /**
     * Update performance analytics display
     * @param {Object} performanceData - Performance analytics data
     */
    updatePerformanceAnalytics(performanceData) {
        const performanceContainer = document.getElementById('performanceAnalytics');
        if (!performanceContainer) return;

        const metrics = [
            { label: 'Win Rate', value: performanceData.win_rate, format: 'percentage' },
            { label: 'Average Win', value: performanceData.avg_win, format: 'currency' },
            { label: 'Average Loss', value: performanceData.avg_loss, format: 'currency' },
            { label: 'Profit Factor', value: performanceData.profit_factor, format: 'number' },
            { label: 'Total Return', value: performanceData.total_return, format: 'currency' }
        ];

        performanceContainer.innerHTML = metrics.map(metric => `
            <div class="metric-row">
                <span class="metric-label">${metric.label}</span>
                <span class="metric-value">${this.formatMetricValue(metric.value, metric.format)}</span>
            </div>
        `).join('');
    }

    /**
     * Update analytics charts
     * @param {Object} analytics - Analytics data
     */
    updateAnalyticsCharts(analytics) {
        // Update Sharpe ratio chart
        this.updateSharpeChart();

        // Update drawdown chart
        this.updateDrawdownChart();

        // Add correlation heatmap if we have positions
        this.updateCorrelationChart();

        // Add rolling volatility chart
        this.updateVolatilityChart();
    }

    /**
     * Update Sharpe ratio chart
     */
    async updateSharpeChart() {
        const chartContainer = 'sharpeChart';

        try {
            window.chartManager.showLoading(chartContainer);

            // Generate sample Sharpe ratio data
            const data = window.chartManager.generateSampleData(90);
            window.chartManager.createSharpeChart(chartContainer, data);

        } catch (error) {
            console.error('Failed to update Sharpe chart:', error);
            window.chartManager.showError(chartContainer, error.message);
        }
    }

    /**
     * Update drawdown chart
     */
    async updateDrawdownChart() {
        const chartContainer = 'drawdownChart';

        try {
            window.chartManager.showLoading(chartContainer);

            // Generate sample drawdown data
            const data = window.chartManager.generateSampleData(90);
            window.chartManager.createDrawdownChart(chartContainer, data);

        } catch (error) {
            console.error('Failed to update drawdown chart:', error);
            window.chartManager.showError(chartContainer, error.message);
        }
    }

    /**
     * Update correlation chart
     */
    async updateCorrelationChart() {
        const chartContainer = 'correlationChart';

        try {
            if (document.getElementById(chartContainer)) {
                window.chartManager.showLoading(chartContainer);

                // Generate sample correlation data
                const correlationData = window.chartManager.generateCorrelationData(this.watchlist.slice(0, 6));
                window.chartManager.createCorrelationHeatmap(chartContainer, correlationData);
            }

        } catch (error) {
            console.error('Failed to update correlation chart:', error);
            if (document.getElementById(chartContainer)) {
                window.chartManager.showError(chartContainer, error.message);
            }
        }
    }

    /**
     * Update volatility chart
     */
    async updateVolatilityChart() {
        const chartContainer = 'volatilityChart';

        try {
            if (document.getElementById(chartContainer)) {
                window.chartManager.showLoading(chartContainer);

                // Generate sample volatility data
                const data = window.chartManager.generateSampleData(90);
                window.chartManager.createRollingStatsChart(chartContainer, data, 'volatility');
            }

        } catch (error) {
            console.error('Failed to update volatility chart:', error);
            if (document.getElementById(chartContainer)) {
                window.chartManager.showError(chartContainer, error.message);
            }
        }
    }

    /**
     * Format metric value based on type
     * @param {number} value - Value to format
     * @param {string} format - Format type
     * @returns {string} Formatted value
     */
    formatMetricValue(value, format) {
        if (value === null || value === undefined || isNaN(value)) {
            return 'N/A';
        }

        switch (format) {
            case 'currency':
                return formatCurrency(value);
            case 'percentage':
                return formatPercentage(value);
            case 'number':
                return value.toFixed(2);
            default:
                return value.toString();
        }
    }

    /**
     * Update portfolio metrics
     * @param {Object} data - Portfolio data
     */
    updatePortfolioMetrics(data) {
        const defaultData = {
            total_value: 0,
            daily_pnl: 0,
            total_return: 0,
            cash_balance: 0,
            positions_count: 0,
            daily_return: 0,
            total_return_percent: 0
        };

        const portfolioData = data || defaultData;

        // Update main metrics
        this.updateElement('portfolioValue', formatCurrency(portfolioData.total_value));
        this.updateElement('activePositions', portfolioData.positions_count?.toString() || '0');
        this.updateElement('todayPnL', formatCurrency(portfolioData.daily_pnl));
        this.updateElement('cashBalance', formatCurrency(portfolioData.cash_balance));

        // Update changes with color coding
        this.updateChangeElement('portfolioChange', portfolioData.daily_return || 0);
        this.updateChangeElement('pnlChange', portfolioData.daily_return || 0);
        this.updateChangeElement('cashChange', 0); // Assuming no cash change tracking

        // Update sidebar stats
        this.updateElement('totalValue', formatCurrency(portfolioData.total_value));
        this.updateElement('dailyPnL', formatCurrency(portfolioData.daily_pnl));
        this.updateElement('totalReturn', formatPercentage(portfolioData.total_return_percent || 0));
    }

    /**
     * Update watchlist data
     */
    async updateWatchlistData() {
        try {
            const marketData = await window.apiClient.getMarketData(this.watchlist);
            this.renderWatchlist(marketData);
            this.renderMarketDataGrid(marketData);
        } catch (error) {
            console.error('Failed to update watchlist data:', error);
        }
    }

    /**
     * Render watchlist
     * @param {Object} marketData - Market data for symbols
     */
    renderWatchlist(marketData) {
        const watchlistContainer = document.getElementById('watchlist');
        if (!watchlistContainer) return;

        watchlistContainer.innerHTML = '';

        this.watchlist.forEach(symbol => {
            const data = marketData[symbol] || { price: 0, change_percent: 0 };
            const changeClass = getChangeColorClass(data.change_percent);

            const item = document.createElement('div');
            item.className = 'watchlist-item';
            item.innerHTML = `
                <div>
                    <div class="watchlist-symbol">${symbol}</div>
                </div>
                <div>
                    <div class="watchlist-price">${formatCurrency(data.price)}</div>
                    <div class="watchlist-change ${changeClass}">
                        ${formatPercentage(data.change_percent)}
                    </div>
                </div>
            `;

            item.addEventListener('click', () => this.showSymbolDetails(symbol));
            watchlistContainer.appendChild(item);
        });
    }

    /**
     * Render market data grid
     * @param {Object} marketData - Market data for symbols
     */
    renderMarketDataGrid(marketData) {
        const gridContainer = document.getElementById('marketDataGrid');
        if (!gridContainer) return;

        gridContainer.innerHTML = '';

        Object.entries(marketData).forEach(([symbol, data]) => {
            const changeClass = getChangeColorClass(data.change_percent);

            const item = document.createElement('div');
            item.className = 'market-data-item';
            item.innerHTML = `
                <div>
                    <div class="market-data-symbol">${symbol}</div>
                </div>
                <div>
                    <div class="market-data-price">${formatCurrency(data.price)}</div>
                    <div class="market-data-change ${changeClass}">
                        ${data.change_percent >= 0 ? '+' : ''}${formatPercentage(data.change_percent)}
                    </div>
                </div>
            `;

            gridContainer.appendChild(item);
        });
    }

    /**
     * Update portfolio chart
     */
    async updatePortfolioChart() {
        const chartContainer = 'portfolioChart';

        try {
            window.chartManager.showLoading(chartContainer);

            // For now, use sample data
            const data = window.chartManager.generateSampleData(90);
            window.chartManager.createPortfolioChart(chartContainer, data);

        } catch (error) {
            console.error('Failed to update portfolio chart:', error);
            window.chartManager.showError(chartContainer, error.message);
        }
    }

    /**
     * Update allocation chart
     */
    async updateAllocationChart() {
        const chartContainer = 'allocationChart';

        try {
            window.chartManager.showLoading(chartContainer);

            const positions = await window.apiClient.getPortfolioPositions().catch(() => []);

            if (positions.length === 0) {
                window.chartManager.showNoDataMessage(chartContainer, 'No positions to display');
                return;
            }

            const allocationData = positions.map(pos => ({
                symbol: pos.symbol,
                value: pos.quantity * pos.current_price
            }));

            window.chartManager.createAllocationChart(chartContainer, allocationData);

        } catch (error) {
            console.error('Failed to update allocation chart:', error);
            window.chartManager.showError(chartContainer, error.message);
        }
    }

    /**
     * Update performance chart
     */
    async updatePerformanceChart() {
        const chartContainer = 'performanceChart';
        const period = document.getElementById('performancePeriod')?.value || '3M';

        try {
            window.chartManager.showLoading(chartContainer);

            // Generate sample performance data
            const portfolioData = window.chartManager.generateSampleData(90);
            const benchmarkData = window.chartManager.generateSampleData(90).map(d => ({
                ...d,
                cumulative_return: d.cumulative_return * 0.8 // Benchmark performs slightly worse
            }));

            window.chartManager.createPerformanceChart(chartContainer, {
                portfolio: portfolioData,
                benchmark: benchmarkData
            });

        } catch (error) {
            console.error('Failed to update performance chart:', error);
            window.chartManager.showError(chartContainer, error.message);
        }
    }

    /**
     * Update positions table
     * @param {Array} positions - Positions data
     */
    updatePositionsTable(positions) {
        const tbody = document.querySelector('#positionsTable tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (positions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        No positions found
                    </td>
                </tr>
            `;
            return;
        }

        positions.forEach(position => {
            const marketValue = position.quantity * position.current_price;
            const costBasis = position.quantity * position.avg_cost;
            const unrealizedPnL = marketValue - costBasis;
            const unrealizedPnLPercent = costBasis > 0 ? unrealizedPnL / costBasis : 0;
            const changeClass = getChangeColorClass(unrealizedPnLPercent);

            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="symbol-cell">${position.symbol}</td>
                <td>${position.quantity}</td>
                <td>${formatCurrency(position.avg_cost)}</td>
                <td>${formatCurrency(position.current_price)}</td>
                <td>${formatCurrency(marketValue)}</td>
                <td class="${changeClass}">${formatCurrency(unrealizedPnL)}</td>
                <td class="${changeClass}">${formatPercentage(unrealizedPnLPercent)}</td>
                <td class="actions-cell">
                    <button class="btn-sm btn-primary" onclick="dashboard.openTradeModal('${position.symbol}', 'SELL')">Sell</button>
                    <button class="btn-sm btn-secondary" onclick="dashboard.showSymbolDetails('${position.symbol}')">Details</button>
                </td>
            `;

            tbody.appendChild(row);
        });
    }

    /**
     * Update trades table
     * @param {Array} trades - Trades data
     */
    updateTradesTable(trades) {
        const tbody = document.querySelector('#tradesTable tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (trades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        No trades found
                    </td>
                </tr>
            `;
            return;
        }

        trades.forEach(trade => {
            const tradeTypeClass = trade.trade_type.toLowerCase() === 'buy' ? 'trade-type-buy' : 'trade-type-sell';
            const statusClass = `trade-status ${trade.status.toLowerCase()}`;
            const pnlClass = getChangeColorClass(trade.pnl || 0);

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatDate(trade.timestamp, 'medium')}</td>
                <td class="symbol-cell">${trade.symbol}</td>
                <td class="${tradeTypeClass}">${trade.trade_type}</td>
                <td>${trade.quantity}</td>
                <td>${formatCurrency(trade.price)}</td>
                <td>${formatCurrency(trade.quantity * trade.price)}</td>
                <td><span class="${statusClass}">${trade.status}</span></td>
                <td class="${pnlClass}">${formatCurrency(trade.pnl || 0)}</td>
            `;

            tbody.appendChild(row);
        });
    }

    /**
     * Add stock to watchlist
     */
    addToWatchlist() {
        const input = document.getElementById('addStockInput');
        if (!input) return;

        const symbol = input.value.trim().toUpperCase();

        if (!isValidStockSymbol(symbol)) {
            showNotification('Please enter a valid crypto symbol (e.g., BTCUSDT, ETHUSDT)', 'error');
            return;
        }

        // Validate against available symbols if we have them
        if (this.availableSymbols.length > 0 && !this.availableSymbols.includes(symbol)) {
            showNotification(`Symbol ${symbol} is not available. Available symbols: ${this.availableSymbols.slice(0, 10).join(', ')}${this.availableSymbols.length > 10 ? '...' : ''}`, 'error');
            return;
        }

        if (this.watchlist.includes(symbol)) {
            showNotification('Symbol already in watchlist', 'warning');
            return;
        }

        this.watchlist.push(symbol);
        Storage.set('watchlist', this.watchlist);
        input.value = '';

        this.updateWatchlistData();
        showNotification(`${symbol} added to watchlist`, 'success');
    }

    /**
     * Remove stock from watchlist
     * @param {string} symbol - Symbol to remove
     */
    removeFromWatchlist(symbol) {
        const index = this.watchlist.indexOf(symbol);
        if (index > -1) {
            this.watchlist.splice(index, 1);
            Storage.set('watchlist', this.watchlist);
            this.updateWatchlistData();
            showNotification(`${symbol} removed from watchlist`, 'success');
        }
    }

    /**
     * Update connection status
     * @param {boolean} connected - Connection status
     */
    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');

        if (statusDot && statusText) {
            if (connected) {
                statusDot.className = 'status-dot connected';
                statusText.textContent = 'Connected';
            } else {
                statusDot.className = 'status-dot disconnected';
                statusText.textContent = 'Disconnected';
            }
        }
    }

    /**
     * Test API connection
     */
    async testConnection() {
        try {
            await window.apiClient.getHealthStatus();
            this.updateConnectionStatus(true);
        } catch (error) {
            this.updateConnectionStatus(false);
        }
    }

    /**
     * Start auto refresh
     */
    startAutoRefresh() {
        if (!this.autoRefreshEnabled) return;

        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, this.refreshRate);
    }

    /**
     * Stop auto refresh
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Refresh dashboard data
     */
    async refreshData() {
        const refreshBtn = document.getElementById('refreshBtn');

        try {
            if (refreshBtn) {
                refreshBtn.classList.add('loading');
                refreshBtn.innerHTML = '<div class="spinner"></div> Refreshing...';
            }

            await this.loadTabData(this.activeTab);
            await this.testConnection();

            showNotification('Data refreshed successfully', 'success', 2000);

        } catch (error) {
            console.error('Failed to refresh data:', error);
            showNotification('Failed to refresh data', 'error');
        } finally {
            if (refreshBtn) {
                refreshBtn.classList.remove('loading');
                refreshBtn.innerHTML = '🔄 Refresh';
            }
        }
    }

    /**
     * Helper methods
     */
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    updateChangeElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            const formattedValue = formatPercentage(value);
            const prefix = value >= 0 ? '+' : '';
            element.textContent = prefix + formattedValue;
            element.className = `metric-change ${getChangeColorClass(value)}`;
        }
    }

    /**
     * Load pipeline status and populate dropdown
     */
    async loadPipelineStatus() {
        try {
            const status = await window.apiClient.getPipelineStatus();

            if (status && status.current) {
                // Update current pipeline display
                const currentPipelineEl = document.getElementById('currentPipeline');
                if (currentPipelineEl) {
                    currentPipelineEl.textContent = status.current.label || status.current.id;
                }

                // Populate pipeline dropdown
                const pipelineSelect = document.getElementById('pipelineSelect');
                if (pipelineSelect && status.options) {
                    // Clear existing options except the first one
                    pipelineSelect.innerHTML = '<option value="">Select Pipeline...</option>';

                    // Add available pipelines
                    status.options.forEach(option => {
                        const optionEl = document.createElement('option');
                        optionEl.value = option.id;
                        optionEl.textContent = option.label || option.id;

                        // Mark current pipeline as disabled
                        if (option.id === status.current.id) {
                            optionEl.disabled = true;
                            optionEl.textContent += ' (Current)';
                        }

                        pipelineSelect.appendChild(optionEl);
                    });
                }
            }
        } catch (error) {
            console.warn('Failed to load pipeline status:', error);
            const currentPipelineEl = document.getElementById('currentPipeline');
            if (currentPipelineEl) {
                currentPipelineEl.textContent = 'Unavailable';
            }
        }
    }

    /**
     * Switch to a different pipeline
     */
    async switchPipeline() {
        const pipelineSelect = document.getElementById('pipelineSelect');
        const switchBtn = document.getElementById('switchPipelineBtn');
        const warningEl = document.getElementById('pipelineWarning');

        if (!pipelineSelect || !pipelineSelect.value) {
            showNotification('Please select a pipeline', 'error');
            return;
        }

        const selectedPipeline = pipelineSelect.value;
        const selectedOption = pipelineSelect.options[pipelineSelect.selectedIndex].text;

        // Confirm with user
        const confirmed = confirm(
            `Switch to pipeline: ${selectedOption}?\n\n` +
            'Note: Server restart is required for changes to take full effect.\n' +
            'Some services may become temporarily unavailable.'
        );

        if (!confirmed) {
            return;
        }

        try {
            if (switchBtn) {
                switchBtn.disabled = true;
                switchBtn.textContent = 'Switching...';
            }

            // Validate pipeline first
            const validation = await window.apiClient.validatePipeline();
            if (!validation.valid && validation.errors && validation.errors.length > 0) {
                console.warn('Pipeline validation warnings:', validation.errors);
                showNotification(
                    `Pipeline has warnings: ${validation.errors.join(', ')}. Some services may not work.`,
                    'warning',
                    5000
                );
            }

            // Switch pipeline
            const result = await window.apiClient.selectPipeline(selectedPipeline);

            showNotification(
                `Switched to pipeline: ${result.label || result.id}. Server restart recommended.`,
                'success',
                5000
            );

            // Show warning
            if (warningEl) {
                warningEl.style.display = 'block';
            }

            // Reload pipeline status
            await this.loadPipelineStatus();

            // Reset dropdown
            pipelineSelect.value = '';

        } catch (error) {
            console.error('Failed to switch pipeline:', error);
            showNotification(`Failed to switch pipeline: ${error.message}`, 'error');
        } finally {
            if (switchBtn) {
                switchBtn.disabled = false;
                switchBtn.textContent = 'Switch Pipeline';
            }
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Dashboard };
}