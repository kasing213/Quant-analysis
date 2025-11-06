// Main Application Entry Point

class TradingApp {
    constructor() {
        this.isInitialized = false;
        this.modalManager = new ModalManager();
        this.notificationManager = new NotificationManager();

        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        if (this.isInitialized) return;

        try {
            console.log('Initializing Trading Dashboard...');

            // Setup error handlers
            this.setupErrorHandlers();

            // Setup notification system
            this.setupNotificationSystem();

            // Setup modals
            this.setupModals();

            // Initialize WebSocket connection
            this.initializeWebSocket();

            // Setup keyboard shortcuts
            this.setupKeyboardShortcuts();

            // Setup resize handlers
            this.setupResizeHandlers();

            // Setup pipeline selector
            this.setupPipelineSelector();

            // Mark as initialized
            this.isInitialized = true;

            console.log('Trading Dashboard initialized successfully');

        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showCriticalError('Failed to initialize dashboard. Please refresh the page.');
        }
    }

    /**
     * Setup global error handlers
     */
    setupErrorHandlers() {
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.handleError(event.reason, 'Unexpected error occurred');
            event.preventDefault();
        });

        // Handle uncaught errors
        window.addEventListener('error', (event) => {
            console.error('Uncaught error:', event.error);
            this.handleError(event.error, 'Application error occurred');
        });

        // Setup API error handling
        if (window.apiClient) {
            const originalRequest = window.apiClient.request.bind(window.apiClient);
            window.apiClient.request = async (...args) => {
                try {
                    return await originalRequest(...args);
                } catch (error) {
                    this.handleApiError(error);
                    throw error;
                }
            };
        }
    }

    /**
     * Setup notification system
     */
    setupNotificationSystem() {
        // Add notification styles to the page
        const style = document.createElement('style');
        style.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 12px 16px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 10000;
                transform: translateX(400px);
                transition: transform 0.3s ease-in-out;
                max-width: 400px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }

            .notification.show {
                transform: translateX(0);
            }

            .notification-success {
                background: #059669;
            }

            .notification-error {
                background: #dc2626;
            }

            .notification-warning {
                background: #d97706;
            }

            .notification-info {
                background: #0891b2;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Setup modals
     */
    setupModals() {
        // Trade modal functionality
        const tradeModal = document.getElementById('tradeModal');
        const closeTradeModal = document.getElementById('closeTradeModal');
        const cancelTrade = document.getElementById('cancelTrade');
        const tradeForm = document.getElementById('tradeForm');
        const orderType = document.getElementById('orderType');
        const limitPriceGroup = document.getElementById('limitPriceGroup');

        if (closeTradeModal) {
            closeTradeModal.addEventListener('click', () => this.modalManager.closeModal('tradeModal'));
        }

        if (cancelTrade) {
            cancelTrade.addEventListener('click', () => this.modalManager.closeModal('tradeModal'));
        }

        if (orderType && limitPriceGroup) {
            orderType.addEventListener('change', (e) => {
                if (e.target.value === 'LMT') {
                    limitPriceGroup.style.display = 'block';
                    document.getElementById('limitPrice').required = true;
                } else {
                    limitPriceGroup.style.display = 'none';
                    document.getElementById('limitPrice').required = false;
                }
            });
        }

        if (tradeForm) {
            tradeForm.addEventListener('submit', (e) => this.handleTradeSubmit(e));
        }

        // Close modals when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.modalManager.closeModal(e.target.id);
            }
        });

        // Close modals with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.modalManager.closeAllModals();
            }
        });
    }

    /**
     * Initialize WebSocket connection
     */
    initializeWebSocket() {
        if (window.wsClient) {
            // Connect to WebSocket
            window.wsClient.connect();

            // Subscribe to market data updates
            window.wsClient.subscribe('market_data', (data) => {
                if (window.dashboard) {
                    window.dashboard.handleMarketData(data);
                }
            });

            // Subscribe to portfolio updates
            window.wsClient.subscribe('portfolio_updates', (data) => {
                if (window.dashboard) {
                    window.dashboard.handlePortfolioUpdate(data);
                }
            });

            // Subscribe to trade updates
            window.wsClient.subscribe('trade_updates', (data) => {
                if (window.dashboard) {
                    window.dashboard.handleTradeUpdate(data);
                }
            });
        }
    }

    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not in an input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Cmd/Ctrl + R: Refresh data
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                if (window.dashboard) {
                    window.dashboard.refreshData();
                }
            }

            // Tab navigation with numbers
            if (e.key >= '1' && e.key <= '5') {
                const tabs = ['overview', 'performance', 'positions', 'trades', 'analytics'];
                const tabIndex = parseInt(e.key) - 1;
                if (tabs[tabIndex] && window.dashboard) {
                    window.dashboard.switchTab(tabs[tabIndex]);
                }
            }

            // T: Open trade modal
            if (e.key === 't' || e.key === 'T') {
                this.openTradeModal();
            }

            // D: Toggle dark mode
            if (e.key === 'd' || e.key === 'D') {
                if (window.dashboard) {
                    window.dashboard.toggleTheme();
                }
            }
        });
    }

    /**
     * Setup resize handlers
     */
    setupResizeHandlers() {
        const debouncedResize = debounce(() => {
            // Notify all components about resize
            if (window.eventEmitter) {
                window.eventEmitter.emit('window:resize');
            }

            // Resize charts
            if (window.chartManager) {
                window.chartManager.charts.forEach((_chart, containerId) => {
                    window.chartManager.resizeChart(containerId);
                });
            }
        }, 250);

        window.addEventListener('resize', debouncedResize);
    }

    /**
     * Setup pipeline selector
     */
    async setupPipelineSelector() {
        const pipelineSelect = document.getElementById('pipelineSelect');
        const pipelineBadge = document.getElementById('pipelineBadge');

        if (!pipelineSelect || !pipelineBadge) {
            console.warn('Pipeline selector elements not found');
            return;
        }

        try {
            // Load current pipeline status
            await this.loadPipelineStatus();

            // Handle pipeline changes
            pipelineSelect.addEventListener('change', async (e) => {
                await this.handlePipelineChange(e.target.value);
            });

        } catch (error) {
            console.error('Failed to setup pipeline selector:', error);
        }
    }

    /**
     * Load pipeline status
     */
    async loadPipelineStatus() {
        try {
            const response = await fetch('/api/v1/pipelines/');
            const data = await response.json();

            const pipelineSelect = document.getElementById('pipelineSelect');
            const pipelineBadge = document.getElementById('pipelineBadge');

            if (pipelineSelect && data.current) {
                pipelineSelect.value = data.current.id;
                this.updatePipelineBadge(data.current.id);
            }

            console.log('Pipeline status loaded:', data.current.label);

        } catch (error) {
            console.error('Failed to load pipeline status:', error);
        }
    }

    /**
     * Handle pipeline change
     * @param {string} pipelineId - New pipeline ID
     */
    async handlePipelineChange(pipelineId) {
        const pipelineSelect = document.getElementById('pipelineSelect');
        const originalValue = pipelineSelect.value;

        try {
            // Show loading state
            pipelineSelect.disabled = true;
            showNotification('Switching pipeline...', 'info', 0);

            // Call API to switch pipeline
            const response = await fetch('/api/v1/pipelines/select', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    pipeline_id: pipelineId
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to switch pipeline: ${response.statusText}`);
            }

            const data = await response.json();

            // Update UI
            this.updatePipelineBadge(data.id);

            // Show success message
            showNotification(`Switched to ${data.label}`, 'success', 3000);

            // Refresh dashboard data
            if (window.dashboard) {
                await window.dashboard.refreshData();
            }

            // Reconnect WebSocket if needed
            if (window.wsClient) {
                window.wsClient.reconnect();
            }

        } catch (error) {
            console.error('Failed to switch pipeline:', error);
            showNotification(`Failed to switch pipeline: ${error.message}`, 'error', 5000);

            // Revert selection
            pipelineSelect.value = originalValue;

        } finally {
            pipelineSelect.disabled = false;
        }
    }

    /**
     * Update pipeline badge
     * @param {string} pipelineId - Pipeline ID
     */
    updatePipelineBadge(pipelineId) {
        const pipelineBadge = document.getElementById('pipelineBadge');

        if (!pipelineBadge) return;

        // Map pipeline IDs to display info
        const pipelineInfo = {
            'binance_paper': { text: 'PAPER', mode: 'paper' },
            'binance_live': { text: 'LIVE', mode: 'live' }
        };

        const info = pipelineInfo[pipelineId] || { text: 'UNKNOWN', mode: 'paper' };

        pipelineBadge.textContent = info.text;
        pipelineBadge.setAttribute('data-mode', info.mode);
    }

    /**
     * Handle API errors
     * @param {Error} error - Error object
     */
    handleApiError(error) {
        const message = parseApiError(error);

        if (error.message && error.message.includes('NetworkError')) {
            showNotification('Network connection lost. Retrying...', 'warning', 5000);
        } else if (error.message && error.message.includes('401')) {
            showNotification('Authentication required. Please log in.', 'error', 10000);
        } else if (error.message && error.message.includes('500')) {
            showNotification('Server error. Please try again later.', 'error', 5000);
        } else {
            showNotification(message, 'error');
        }
    }

    /**
     * Handle general errors
     * @param {Error} error - Error object
     * @param {string} fallbackMessage - Fallback message
     */
    handleError(error, fallbackMessage) {
        const message = error?.message || fallbackMessage;
        console.error('Application error:', error);
        showNotification(message, 'error');
    }

    /**
     * Show critical error
     * @param {string} message - Error message
     */
    showCriticalError(message) {
        // Create critical error overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 99999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        `;

        overlay.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <h2 style="margin-bottom: 1rem; color: #dc2626;">⚠️ Critical Error</h2>
                <p style="margin-bottom: 1rem;">${message}</p>
                <button onclick="location.reload()" style="
                    background: #2563eb;
                    color: white;
                    border: none;
                    padding: 0.75rem 1.5rem;
                    border-radius: 0.5rem;
                    cursor: pointer;
                    font-size: 1rem;
                ">Reload Page</button>
            </div>
        `;

        document.body.appendChild(overlay);
    }

    /**
     * Handle trade form submission
     * @param {Event} e - Form submit event
     */
    async handleTradeSubmit(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const tradeData = {
            symbol: formData.get('symbol')?.toUpperCase(),
            trade_type: formData.get('type'),
            quantity: parseInt(formData.get('quantity')),
            order_type: formData.get('orderType'),
            price: formData.get('orderType') === 'LMT' ? parseFloat(formData.get('limitPrice')) : null
        };

        try {
            // Validate trade data
            if (!isValidStockSymbol(tradeData.symbol)) {
                throw new Error('Invalid crypto symbol (e.g., BTCUSDT, ETHUSDT)');
            }

            if (tradeData.quantity <= 0) {
                throw new Error('Quantity must be greater than 0');
            }

            if (tradeData.order_type === 'LMT' && (!tradeData.price || tradeData.price <= 0)) {
                throw new Error('Limit price must be greater than 0');
            }

            // Submit trade
            const result = await window.apiClient.createTrade(tradeData);

            showNotification(`Trade submitted successfully: ${tradeData.trade_type} ${tradeData.quantity} ${tradeData.symbol}`, 'success');

            // Close modal and refresh data
            this.modalManager.closeModal('tradeModal');

            if (window.dashboard) {
                await window.dashboard.loadTradesData();
                await window.dashboard.loadPositionsData();
                await window.dashboard.loadOverviewData();
            }

        } catch (error) {
            console.error('Trade submission failed:', error);
            showNotification(`Trade failed: ${parseApiError(error)}`, 'error');
        }
    }

    /**
     * Open trade modal
     * @param {string} symbol - Pre-fill symbol
     * @param {string} type - Pre-fill trade type
     */
    openTradeModal(symbol = '', type = 'BUY') {
        const modal = document.getElementById('tradeModal');
        const symbolInput = document.getElementById('tradeSymbol');
        const typeSelect = document.getElementById('tradeType');

        if (symbolInput) symbolInput.value = symbol;
        if (typeSelect) typeSelect.value = type;

        this.modalManager.openModal('tradeModal');
    }

    /**
     * Show symbol details
     * @param {string} symbol - Stock symbol
     */
    async showSymbolDetails(symbol) {
        try {
            // This would open a detailed view for the symbol
            // For now, just show a notification
            showNotification(`Loading details for ${symbol}...`, 'info');

            // In a full implementation, this would:
            // - Open a modal with detailed charts
            // - Show historical data
            // - Display fundamental analysis
            // - Show news and events

        } catch (error) {
            console.error('Failed to load symbol details:', error);
            showNotification('Failed to load symbol details', 'error');
        }
    }
}

/**
 * Modal Manager
 */
class ModalManager {
    constructor() {
        this.openModals = new Set();
    }

    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
            this.openModals.add(modalId);
            document.body.style.overflow = 'hidden';
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            this.openModals.delete(modalId);

            if (this.openModals.size === 0) {
                document.body.style.overflow = '';
            }
        }
    }

    closeAllModals() {
        this.openModals.forEach(modalId => {
            this.closeModal(modalId);
        });
    }
}

/**
 * Notification Manager
 */
class NotificationManager {
    constructor() {
        this.notifications = new Map();
        this.maxNotifications = 5;
    }

    show(message, type = 'info', duration = 3000) {
        const id = generateId();

        // Remove oldest notification if at max
        if (this.notifications.size >= this.maxNotifications) {
            const oldestId = this.notifications.keys().next().value;
            this.remove(oldestId);
        }

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.top = `${20 + (this.notifications.size * 70)}px`;

        // Add to page
        document.body.appendChild(notification);
        this.notifications.set(id, notification);

        // Trigger animation
        setTimeout(() => notification.classList.add('show'), 10);

        // Auto remove
        if (duration > 0) {
            setTimeout(() => this.remove(id), duration);
        }

        return id;
    }

    remove(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                this.notifications.delete(id);
                this.repositionNotifications();
            }, 300);
        }
    }

    repositionNotifications() {
        let index = 0;
        this.notifications.forEach(notification => {
            notification.style.top = `${20 + (index * 70)}px`;
            index++;
        });
    }
}

// Add modal styles
const modalStyles = `
    .modal {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        align-items: center;
        justify-content: center;
    }

    .modal-content {
        background: var(--bg-primary);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-xl);
        max-width: 500px;
        width: 90%;
        max-height: 90vh;
        overflow-y: auto;
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--spacing-lg);
        border-bottom: 1px solid var(--border-color);
    }

    .modal-header h3 {
        margin: 0;
        color: var(--text-primary);
    }

    .modal-close {
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: var(--text-secondary);
        padding: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .modal-close:hover {
        color: var(--text-primary);
    }

    .modal-body {
        padding: var(--spacing-lg);
    }

    .form-group {
        margin-bottom: var(--spacing-lg);
    }

    .form-group label {
        display: block;
        margin-bottom: var(--spacing-sm);
        font-weight: 500;
        color: var(--text-secondary);
    }

    .form-group input,
    .form-group select {
        width: 100%;
        padding: var(--spacing-md);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 0.875rem;
    }

    .form-group input:focus,
    .form-group select:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

    .modal-actions {
        display: flex;
        gap: var(--spacing-md);
        justify-content: flex-end;
        margin-top: var(--spacing-xl);
    }
`;

// Add styles to page
const style = document.createElement('style');
style.textContent = modalStyles;
document.head.appendChild(style);

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.tradingApp = new TradingApp();
});

// Make functions globally available
window.openTradeModal = (symbol, type) => {
    if (window.tradingApp) {
        window.tradingApp.openTradeModal(symbol, type);
    }
};

window.showSymbolDetails = (symbol) => {
    if (window.tradingApp) {
        window.tradingApp.showSymbolDetails(symbol);
    }
};

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TradingApp, ModalManager, NotificationManager };
}
