// Utility Functions for Dashboard

/**
 * Format currency values
 * @param {number} value - The value to format
 * @param {string} currency - Currency code (default: USD)
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted currency string
 */
function formatCurrency(value, currency = 'USD', decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '$0.00';
    }

    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

/**
 * Format percentage values
 * @param {number} value - The value to format (as decimal, e.g., 0.05 for 5%)
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted percentage string
 */
function formatPercentage(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0.00%';
    }

    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

/**
 * Format large numbers with K, M, B suffixes
 * @param {number} value - The value to format
 * @param {number} decimals - Number of decimal places (default: 1)
 * @returns {string} Formatted number string
 */
function formatLargeNumber(value, decimals = 1) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0';
    }

    const absValue = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (absValue >= 1e9) {
        return sign + (absValue / 1e9).toFixed(decimals) + 'B';
    } else if (absValue >= 1e6) {
        return sign + (absValue / 1e6).toFixed(decimals) + 'M';
    } else if (absValue >= 1e3) {
        return sign + (absValue / 1e3).toFixed(decimals) + 'K';
    }

    return sign + absValue.toFixed(decimals);
}

/**
 * Format date for display
 * @param {Date|string} date - The date to format
 * @param {string} format - Format type ('short', 'medium', 'long', 'time')
 * @returns {string} Formatted date string
 */
function formatDate(date, format = 'short') {
    if (!date) return '';

    const dateObj = typeof date === 'string' ? new Date(date) : date;

    const options = {
        short: { month: 'short', day: 'numeric', year: 'numeric' },
        medium: { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' },
        long: { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' },
        time: { hour: '2-digit', minute: '2-digit', second: '2-digit' }
    };

    return new Intl.DateTimeFormat('en-US', options[format] || options.short).format(dateObj);
}

/**
 * Calculate percentage change between two values
 * @param {number} current - Current value
 * @param {number} previous - Previous value
 * @returns {number} Percentage change as decimal
 */
function calculatePercentageChange(current, previous) {
    if (!previous || previous === 0) return 0;
    return (current - previous) / previous;
}

/**
 * Get change color class based on value
 * @param {number} value - The value to evaluate
 * @returns {string} CSS class name
 */
function getChangeColorClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
}

/**
 * Debounce function to limit API calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function to limit execution frequency
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let lastFunc;
    let lastRan;
    return function() {
        const context = this;
        const args = arguments;
        if (!lastRan) {
            func.apply(context, args);
            lastRan = Date.now();
        } else {
            clearTimeout(lastFunc);
            lastFunc = setTimeout(function() {
                if ((Date.now() - lastRan) >= limit) {
                    func.apply(context, args);
                    lastRan = Date.now();
                }
            }, limit - (Date.now() - lastRan));
        }
    };
}

/**
 * Generate a unique ID
 * @returns {string} Unique identifier
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Validate crypto symbol format (Binance pairs)
 * @param {string} symbol - Crypto symbol to validate (e.g., BTCUSDT, ETHUSDT)
 * @returns {boolean} True if valid
 */
function isValidStockSymbol(symbol) {
    if (!symbol || typeof symbol !== 'string') return false;
    const cleaned = symbol.trim().toUpperCase();
    // Updated regex to support crypto pairs like BTCUSDT, ETHUSDT, etc.
    return /^[A-Z]{3,12}USDT?$|^[A-Z]{3,8}BTC$|^[A-Z]{3,8}ETH$|^[A-Z]{2,10}$/.test(cleaned);
}

/**
 * Parse API error response
 * @param {Object} error - Error object
 * @returns {string} User-friendly error message
 */
function parseApiError(error) {
    if (error.response && error.response.data) {
        if (error.response.data.detail) {
            return error.response.data.detail;
        }
        if (error.response.data.message) {
            return error.response.data.message;
        }
    }

    if (error.message) {
        return error.message;
    }

    return 'An unexpected error occurred. Please try again.';
}

/**
 * Show notification to user
 * @param {string} message - Message to display
 * @param {string} type - Notification type ('success', 'error', 'warning', 'info')
 * @param {number} duration - Duration in milliseconds (default: 3000)
 */
function showNotification(message, type = 'info', duration = 3000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // Add to page
    document.body.appendChild(notification);

    // Trigger animation
    setTimeout(() => notification.classList.add('show'), 10);

    // Remove after duration
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => document.body.removeChild(notification), 300);
    }, duration);
}

/**
 * Handle async operations with loading state
 * @param {Function} asyncFunction - Async function to execute
 * @param {HTMLElement} element - Element to show loading state on
 * @returns {Promise} Promise result
 */
async function withLoadingState(asyncFunction, element) {
    if (element) {
        element.classList.add('loading');
    }

    try {
        const result = await asyncFunction();
        return result;
    } catch (error) {
        console.error('Operation failed:', error);
        throw error;
    } finally {
        if (element) {
            element.classList.remove('loading');
        }
    }
}

/**
 * Deep clone an object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj);
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
    return obj;
}

/**
 * Calculate portfolio metrics
 * @param {Array} positions - Array of position objects
 * @returns {Object} Portfolio metrics
 */
function calculatePortfolioMetrics(positions) {
    if (!positions || positions.length === 0) {
        return {
            totalValue: 0,
            totalCost: 0,
            totalPnL: 0,
            totalPnLPercent: 0,
            dayPnL: 0,
            dayPnLPercent: 0
        };
    }

    let totalValue = 0;
    let totalCost = 0;
    let dayPnL = 0;

    positions.forEach(position => {
        const marketValue = position.quantity * position.current_price;
        const costBasis = position.quantity * position.avg_cost;
        const dayChange = position.quantity * (position.current_price - position.previous_close);

        totalValue += marketValue;
        totalCost += costBasis;
        dayPnL += dayChange;
    });

    const totalPnL = totalValue - totalCost;
    const totalPnLPercent = totalCost > 0 ? totalPnL / totalCost : 0;
    const dayPnLPercent = totalValue > 0 ? dayPnL / (totalValue - dayPnL) : 0;

    return {
        totalValue,
        totalCost,
        totalPnL,
        totalPnLPercent,
        dayPnL,
        dayPnLPercent
    };
}

/**
 * Calculate moving average
 * @param {Array} data - Array of numbers
 * @param {number} period - Period for moving average
 * @returns {Array} Array of moving averages
 */
function calculateMovingAverage(data, period) {
    const result = [];
    for (let i = period - 1; i < data.length; i++) {
        const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
        result.push(sum / period);
    }
    return result;
}

/**
 * Local storage helpers
 */
const Storage = {
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('Storage get error:', error);
            return defaultValue;
        }
    },

    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('Storage set error:', error);
            return false;
        }
    },

    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('Storage remove error:', error);
            return false;
        }
    },

    clear() {
        try {
            localStorage.clear();
            return true;
        } catch (error) {
            console.error('Storage clear error:', error);
            return false;
        }
    }
};

/**
 * Event emitter for component communication
 */
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    off(event, callback) {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter(cb => cb !== callback);
    }

    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error('Event callback error:', error);
            }
        });
    }
}

// Create global event emitter instance
window.eventEmitter = new EventEmitter();

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatCurrency,
        formatPercentage,
        formatLargeNumber,
        formatDate,
        calculatePercentageChange,
        getChangeColorClass,
        debounce,
        throttle,
        generateId,
        isValidStockSymbol,
        parseApiError,
        showNotification,
        withLoadingState,
        deepClone,
        calculatePortfolioMetrics,
        calculateMovingAverage,
        Storage,
        EventEmitter
    };
}