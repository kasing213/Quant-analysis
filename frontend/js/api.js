// API Client for Dashboard

const DEFAULT_API_PORT = '8000';
const FRONTEND_ONLY_PORTS = new Set(['3000', '3001', '5173']);

const normalizeBaseUrl = (value) => value.endsWith('/') ? value.slice(0, -1) : value;

const resolveApiPort = (port) => {
    if (!port || FRONTEND_ONLY_PORTS.has(port)) {
        return DEFAULT_API_PORT;
    }
    return port;
};

const resolveApiBaseUrl = () => {
    if (window.API_BASE_URL) {
        return normalizeBaseUrl(window.API_BASE_URL);
    }

    const { protocol, hostname, port } = window.location;
    const apiPort = resolveApiPort(port);
    return `${protocol}//${hostname}:${apiPort}`;
};

const resolveWebSocketUrl = () => {
    if (window.WS_BASE_URL) {
        return window.WS_BASE_URL;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const { hostname, port } = window.location;
    const wsPort = resolveApiPort(port);
    return `${protocol}//${hostname}:${wsPort}/ws`;
};

class ApiClient {
    constructor(baseUrl = resolveApiBaseUrl()) {
        this.baseUrl = baseUrl;
        this.apiVersion = '/api/v1';
        this.timeout = 10000;
        this.retries = 3;
        this.retryDelay = 1000;
    }

    /**
     * Make HTTP request with error handling and retries
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @param {number} retryCount - Current retry count
     * @returns {Promise} Response data
     */
    async request(endpoint, options = {}, retryCount = 0) {
        const url = `${this.baseUrl}${endpoint}`;

        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            timeout: this.timeout,
            ...options
        };

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);

            const response = await fetch(url, {
                ...defaultOptions,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`);
            }

            const data = await response.json();
            return data;

        } catch (error) {
            console.error(`API request failed: ${url}`, error);

            // Retry logic
            if (retryCount < this.retries && this.shouldRetry(error)) {
                console.log(`Retrying request (${retryCount + 1}/${this.retries})...`);
                await this.delay(this.retryDelay * (retryCount + 1));
                return this.request(endpoint, options, retryCount + 1);
            }

            throw error;
        }
    }

    /**
     * Check if error should trigger a retry
     * @param {Error} error - Error object
     * @returns {boolean} Should retry
     */
    shouldRetry(error) {
        // Retry on network errors, timeouts, and 5xx server errors
        return error.name === 'AbortError' ||
               error.message.includes('fetch') ||
               error.message.includes('500') ||
               error.message.includes('502') ||
               error.message.includes('503') ||
               error.message.includes('504');
    }

    /**
     * Delay helper for retries
     * @param {number} ms - Milliseconds to delay
     * @returns {Promise} Promise that resolves after delay
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @returns {Promise} Response data
     */
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, this.baseUrl);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined) {
                url.searchParams.append(key, params[key]);
            }
        });

        return this.request(url.pathname + url.search);
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise} Response data
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise} Response data
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @returns {Promise} Response data
     */
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    // Portfolio API methods
    async getPortfolioSummary() {
        return this.get(`${this.apiVersion}/portfolio/summary`);
    }

    async getPortfolioPerformance(period = '1M') {
        return this.get(`${this.apiVersion}/portfolio/performance`, { period });
    }

    async getPortfolioPositions() {
        return this.get(`${this.apiVersion}/positions`);
    }

    async getPosition(symbol) {
        return this.get(`${this.apiVersion}/positions/${symbol}`);
    }

    // Trades API methods
    async getTrades(limit = 100, offset = 0, symbol = null, trade_type = null) {
        const params = { limit, offset };
        if (symbol) params.symbol = symbol;
        if (trade_type) params.trade_type = trade_type;

        return this.get(`${this.apiVersion}/trades`, params);
    }

    async createTrade(tradeData) {
        return this.post(`${this.apiVersion}/trades`, tradeData);
    }

    async getTrade(tradeId) {
        return this.get(`${this.apiVersion}/trades/${tradeId}`);
    }

    async updateTrade(tradeId, tradeData) {
        return this.put(`${this.apiVersion}/trades/${tradeId}`, tradeData);
    }

    async deleteTrade(tradeId) {
        return this.delete(`${this.apiVersion}/trades/${tradeId}`);
    }

    // Market data methods
    async getMarketData(symbols) {
        try {
            const symbolsParam = symbols.join(',');
            const response = await this.get(`${this.apiVersion}/market/quotes`, { symbols: symbolsParam });
            return response.quotes;
        } catch (error) {
            console.error('Failed to get market data:', error);
            throw error;
        }
    }

    async getQuote(symbol) {
        return this.get(`${this.apiVersion}/market/quote/${symbol}`);
    }

    async getAvailableSymbols() {
        return this.get(`${this.apiVersion}/market/symbols`);
    }

    async getHistoricalData(symbol, period = '1M', interval = '1d') {
        try {
            const response = await this.get(`${this.apiVersion}/market/historical/${symbol}`, {
                period,
                interval
            });
            return response;
        } catch (error) {
            console.error('Failed to get historical data:', error);
            throw error;
        }
    }

    // Health check methods
    async getHealthStatus() {
        return this.get('/health');
    }

    async getDatabaseHealth() {
        return this.get('/health/database');
    }

    async getDetailedHealth() {
        return this.get('/health/detailed');
    }

    // Analytics methods
    async getPortfolioAnalytics() {
        try {
            // Fetch real analytics from backend endpoints
            const [riskMetrics, performanceMetrics, positions] = await Promise.all([
                this.getRiskMetrics().catch(() => null),
                this.getPerformanceMetrics().catch(() => null),
                this.getPortfolioPositions().catch(() => [])
            ]);

            // Calculate portfolio metrics from positions
            const portfolioMetrics = calculatePortfolioMetrics(positions);

            return {
                portfolio: portfolioMetrics,
                risk: riskMetrics?.risk_metrics || this.getDefaultRiskMetrics(),
                performance: performanceMetrics?.performance_metrics || this.getDefaultPerformanceMetrics(),
                positions: positions.length,
                trades_count: performanceMetrics?.total_trades || 0
            };
        } catch (error) {
            console.error('Failed to get portfolio analytics:', error);
            return this.getDefaultAnalytics();
        }
    }

    async getRiskMetrics() {
        return this.get(`${this.apiVersion}/portfolio/analytics/risk-metrics`);
    }

    async getPerformanceMetrics() {
        return this.get(`${this.apiVersion}/portfolio/analytics/performance-metrics`);
    }

    async getDrawdownAnalysis() {
        return this.get(`${this.apiVersion}/portfolio/analytics/drawdown-analysis`);
    }

    async getPositionSizeRecommendation(symbol, riskPercent = 2.0) {
        return this.get(`${this.apiVersion}/portfolio/analytics/position-size-recommendation`, {
            symbol,
            risk_percent: riskPercent
        });
    }

    getDefaultRiskMetrics() {
        return {
            portfolio_beta: 0,
            sharpe_ratio: 0,
            sortino_ratio: 0,
            calmar_ratio: 0,
            max_drawdown: 0,
            current_drawdown: 0,
            volatility: 0,
            var_95: 0,
            cvar_95: 0,
            concentration_risk: 0
        };
    }

    getDefaultPerformanceMetrics() {
        return {
            total_return: 0,
            total_return_percent: 0,
            annualized_return: 0,
            win_rate: 0,
            avg_win: 0,
            avg_loss: 0,
            profit_factor: 0,
            total_trades: 0,
            winning_trades: 0,
            losing_trades: 0
        };
    }

    getDefaultAnalytics() {
        return {
            portfolio: {
                totalValue: 0,
                totalCost: 0,
                totalPnL: 0,
                totalPnLPercent: 0,
                dayPnL: 0,
                dayPnLPercent: 0
            },
            risk: this.getDefaultRiskMetrics(),
            performance: this.getDefaultPerformanceMetrics(),
            positions: 0,
            trades_count: 0
        };
    }

    // Pipeline management methods
    async getPipelineStatus() {
        return this.get(`${this.apiVersion}/pipelines/`);
    }

    async selectPipeline(pipelineId) {
        return this.post(`${this.apiVersion}/pipelines/select`, { pipeline_id: pipelineId });
    }

    async validatePipeline() {
        return this.get(`${this.apiVersion}/pipelines/validate`);
    }

    async getPipelineConfig() {
        return this.get(`${this.apiVersion}/pipelines/config`);
    }
}

// WebSocket client for real-time updates
class WebSocketClient {
    constructor(url = resolveWebSocketUrl()) {
        this.url = url;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
        this.messageHandlers = new Map();
        this.isConnected = false;
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.emit('disconnected');
                this.reconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };

        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.reconnect();
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }

    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        console.log(`Reconnecting WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

        setTimeout(() => {
            this.connect();
        }, this.reconnectInterval);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    subscribe(channel, handler) {
        if (!this.messageHandlers.has(channel)) {
            this.messageHandlers.set(channel, []);
        }
        this.messageHandlers.get(channel).push(handler);

        // Send subscription message
        this.send({
            type: 'subscribe',
            channel: channel
        });
    }

    unsubscribe(channel, handler) {
        if (this.messageHandlers.has(channel)) {
            const handlers = this.messageHandlers.get(channel);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }

            if (handlers.length === 0) {
                this.messageHandlers.delete(channel);
                // Send unsubscription message
                this.send({
                    type: 'unsubscribe',
                    channel: channel
                });
            }
        }
    }

    handleMessage(data) {
        const { channel, type, payload } = data;

        if (this.messageHandlers.has(channel)) {
            this.messageHandlers.get(channel).forEach(handler => {
                try {
                    handler(payload, type);
                } catch (error) {
                    console.error('Message handler error:', error);
                }
            });
        }

        // Emit to global event emitter as well
        if (window.eventEmitter) {
            window.eventEmitter.emit(`ws:${channel}`, payload);
        }
    }

    emit(event, data) {
        if (window.eventEmitter) {
            window.eventEmitter.emit(`ws:${event}`, data);
        }
    }
}

// Create global API client instance
window.apiClient = new ApiClient();
window.wsClient = new WebSocketClient();

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ApiClient, WebSocketClient };
}
