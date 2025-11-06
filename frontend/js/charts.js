// Charts Module for Dashboard

class ChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultColors = [
            '#2563eb', '#059669', '#dc2626', '#d97706', '#7c3aed',
            '#0891b2', '#be185d', '#059669', '#7c2d12', '#166534'
        ];
        this.theme = 'light';
    }

    /**
     * Set chart theme
     * @param {string} theme - 'light' or 'dark'
     */
    setTheme(theme) {
        this.theme = theme;
        // Update all existing charts
        this.charts.forEach(chart => {
            if (chart.type === 'plotly') {
                this.updatePlotlyTheme(chart.instance, chart.containerId);
            }
        });
    }

    /**
     * Get theme-appropriate colors
     */
    getThemeColors() {
        if (this.theme === 'dark') {
            return {
                background: '#1e293b',
                paper: '#334155',
                text: '#f8fafc',
                grid: '#475569',
                axis: '#cbd5e1'
            };
        } else {
            return {
                background: '#ffffff',
                paper: '#f8fafc',
                text: '#0f172a',
                grid: '#e2e8f0',
                axis: '#64748b'
            };
        }
    }

    /**
     * Create portfolio performance chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - Portfolio performance data
     */
    createPortfolioChart(containerId, data) {
        const colors = this.getThemeColors();

        const trace = {
            x: data.map(d => d.date),
            y: data.map(d => d.value),
            type: 'scatter',
            mode: 'lines',
            name: 'Portfolio Value',
            line: {
                color: this.defaultColors[0],
                width: 3
            },
            hovertemplate: '<b>%{x}</b><br>Value: $%{y:,.0f}<extra></extra>'
        };

        const layout = {
            title: {
                text: 'Portfolio Performance',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: 'Portfolio Value ($)',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '$,.0f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create asset allocation pie chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - Allocation data
     */
    createAllocationChart(containerId, data) {
        const colors = this.getThemeColors();

        if (!data || data.length === 0) {
            this.showNoDataMessage(containerId, 'No positions data available');
            return;
        }

        const trace = {
            type: 'pie',
            labels: data.map(d => d.symbol),
            values: data.map(d => d.value),
            hole: 0.4,
            hovertemplate: '<b>%{label}</b><br>Value: $%{value:,.0f}<br>%{percent}<extra></extra>',
            textinfo: 'label+percent',
            textposition: 'outside',
            marker: {
                colors: this.defaultColors.slice(0, data.length)
            }
        };

        const layout = {
            title: {
                text: 'Asset Allocation',
                font: { color: colors.text, size: 16 }
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 30, l: 30 },
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create performance comparison chart
     * @param {string} containerId - Container element ID
     * @param {Object} data - Performance data with portfolio and benchmark
     */
    createPerformanceChart(containerId, data) {
        const colors = this.getThemeColors();

        const traces = [];

        if (data.portfolio) {
            traces.push({
                x: data.portfolio.map(d => d.date),
                y: data.portfolio.map(d => d.cumulative_return * 100),
                type: 'scatter',
                mode: 'lines',
                name: 'Portfolio',
                line: {
                    color: this.defaultColors[0],
                    width: 3
                },
                hovertemplate: '<b>Portfolio</b><br>%{x}<br>Return: %{y:.2f}%<extra></extra>'
            });
        }

        if (data.benchmark) {
            traces.push({
                x: data.benchmark.map(d => d.date),
                y: data.benchmark.map(d => d.cumulative_return * 100),
                type: 'scatter',
                mode: 'lines',
                name: 'Benchmark',
                line: {
                    color: this.defaultColors[1],
                    width: 2,
                    dash: 'dash'
                },
                hovertemplate: '<b>Benchmark</b><br>%{x}<br>Return: %{y:.2f}%<extra></extra>'
            });
        }

        const layout = {
            title: {
                text: 'Performance vs Benchmark',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: 'Cumulative Return (%)',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '.2f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            legend: {
                x: 0,
                y: 1,
                bgcolor: 'rgba(0,0,0,0)'
            }
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, traces, layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create Sharpe ratio chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - Sharpe ratio data over time
     */
    createSharpeChart(containerId, data) {
        const colors = this.getThemeColors();

        const trace = {
            x: data.map(d => d.date),
            y: data.map(d => d.sharpe_ratio),
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Sharpe Ratio',
            line: {
                color: this.defaultColors[2],
                width: 2
            },
            marker: {
                size: 4,
                color: this.defaultColors[2]
            },
            hovertemplate: '<b>%{x}</b><br>Sharpe Ratio: %{y:.3f}<extra></extra>'
        };

        // Add horizontal line at Sharpe = 1
        const benchmarkLine = {
            x: [data[0]?.date, data[data.length - 1]?.date],
            y: [1, 1],
            type: 'scatter',
            mode: 'lines',
            name: 'Benchmark (1.0)',
            line: {
                color: colors.axis,
                width: 1,
                dash: 'dash'
            },
            showlegend: false,
            hoverinfo: 'skip'
        };

        const layout = {
            title: {
                text: 'Rolling Sharpe Ratio (252 days)',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: 'Sharpe Ratio',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '.2f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [trace, benchmarkLine], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create drawdown chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - Drawdown data
     */
    createDrawdownChart(containerId, data) {
        const colors = this.getThemeColors();

        const trace = {
            x: data.map(d => d.date),
            y: data.map(d => d.drawdown * 100),
            type: 'scatter',
            mode: 'lines',
            name: 'Drawdown',
            fill: 'tonexty',
            fillcolor: 'rgba(220, 38, 38, 0.2)',
            line: {
                color: this.defaultColors[3],
                width: 2
            },
            hovertemplate: '<b>%{x}</b><br>Drawdown: %{y:.2f}%<extra></extra>'
        };

        // Zero line
        const zeroLine = {
            x: [data[0]?.date, data[data.length - 1]?.date],
            y: [0, 0],
            type: 'scatter',
            mode: 'lines',
            name: 'Zero',
            line: {
                color: colors.axis,
                width: 1
            },
            showlegend: false,
            hoverinfo: 'skip'
        };

        const layout = {
            title: {
                text: 'Portfolio Drawdown',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: 'Drawdown (%)',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '.2f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [zeroLine, trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create candlestick chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - OHLCV data
     * @param {string} symbol - Stock symbol
     */
    createCandlestickChart(containerId, data, symbol) {
        const colors = this.getThemeColors();

        const trace = {
            x: data.map(d => d.date),
            open: data.map(d => d.open),
            high: data.map(d => d.high),
            low: data.map(d => d.low),
            close: data.map(d => d.close),
            type: 'candlestick',
            name: symbol,
            increasing: { line: { color: this.defaultColors[1] } },
            decreasing: { line: { color: this.defaultColors[2] } }
        };

        const layout = {
            title: {
                text: `${symbol} Price Chart`,
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                rangeslider: { visible: false }
            },
            yaxis: {
                title: 'Price ($)',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '$,.2f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        };

        Plotly.newPlot(containerId, [trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Update chart data
     * @param {string} containerId - Container element ID
     * @param {Object} newData - New data to update
     */
    updateChart(containerId, newData) {
        const chart = this.charts.get(containerId);
        if (!chart) return;

        if (chart.type === 'plotly') {
            // Update Plotly chart
            const update = {};

            if (newData.x) update.x = [newData.x];
            if (newData.y) update.y = [newData.y];
            if (newData.open) update.open = [newData.open];
            if (newData.high) update.high = [newData.high];
            if (newData.low) update.low = [newData.low];
            if (newData.close) update.close = [newData.close];

            Plotly.restyle(containerId, update);
        }
    }

    /**
     * Resize chart
     * @param {string} containerId - Container element ID
     */
    resizeChart(containerId) {
        const chart = this.charts.get(containerId);
        if (!chart) return;

        if (chart.type === 'plotly') {
            Plotly.Plots.resize(containerId);
        }
    }

    /**
     * Remove chart
     * @param {string} containerId - Container element ID
     */
    removeChart(containerId) {
        const chart = this.charts.get(containerId);
        if (!chart) return;

        if (chart.type === 'plotly') {
            Plotly.purge(containerId);
        }

        this.charts.delete(containerId);
    }

    /**
     * Show loading state
     * @param {string} containerId - Container element ID
     */
    showLoading(containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="chart-loading">
                    <div class="spinner"></div>
                    Loading chart data...
                </div>
            `;
        }
    }

    /**
     * Show error message
     * @param {string} containerId - Container element ID
     * @param {string} message - Error message
     */
    showError(containerId, message) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="chart-error">
                    <div>⚠️</div>
                    <div>Error loading chart</div>
                    <div style="font-size: 0.75rem; margin-top: 8px;">${message}</div>
                </div>
            `;
        }
    }

    /**
     * Show no data message
     * @param {string} containerId - Container element ID
     * @param {string} message - No data message
     */
    showNoDataMessage(containerId, message = 'No data available') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="chart-no-data">
                    <div class="icon">📊</div>
                    <div>${message}</div>
                </div>
            `;
        }
    }

    /**
     * Update Plotly theme
     * @param {HTMLElement} element - Chart element
     * @param {string} containerId - Container ID
     */
    updatePlotlyTheme(element, containerId) {
        const colors = this.getThemeColors();

        const update = {
            'plot_bgcolor': colors.background,
            'paper_bgcolor': colors.paper,
            'font.color': colors.text,
            'xaxis.color': colors.axis,
            'yaxis.color': colors.axis,
            'xaxis.gridcolor': colors.grid,
            'yaxis.gridcolor': colors.grid
        };

        Plotly.relayout(containerId, update);
    }

    /**
     * Create correlation heatmap
     * @param {string} containerId - Container element ID
     * @param {Array} correlationData - Correlation matrix data
     */
    createCorrelationHeatmap(containerId, correlationData) {
        const colors = this.getThemeColors();

        if (!correlationData || correlationData.length === 0) {
            this.showNoDataMessage(containerId, 'No correlation data available');
            return;
        }

        const symbols = correlationData.map(d => d.symbol);
        const correlationMatrix = correlationData.map(d => d.correlations);

        const trace = {
            z: correlationMatrix,
            x: symbols,
            y: symbols,
            type: 'heatmap',
            colorscale: [
                [0, '#dc2626'],      // Red for negative correlation
                [0.5, '#f8fafc'],    // White for no correlation
                [1, '#059669']       // Green for positive correlation
            ],
            zmid: 0,
            zmin: -1,
            zmax: 1,
            hovertemplate: '<b>%{y} vs %{x}</b><br>Correlation: %{z:.3f}<extra></extra>',
            showscale: true,
            colorbar: {
                title: 'Correlation',
                titleside: 'right'
            }
        };

        const layout = {
            title: {
                text: 'Asset Correlation Matrix',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Assets',
                color: colors.axis,
                side: 'bottom'
            },
            yaxis: {
                title: 'Assets',
                color: colors.axis
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 60, r: 100, b: 60, l: 80 }
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create volume profile chart
     * @param {string} containerId - Container element ID
     * @param {Array} volumeData - Volume profile data
     */
    createVolumeProfile(containerId, volumeData) {
        const colors = this.getThemeColors();

        const priceTrace = {
            x: volumeData.map(d => d.date),
            y: volumeData.map(d => d.price),
            type: 'scatter',
            mode: 'lines',
            name: 'Price',
            yaxis: 'y1',
            line: {
                color: this.defaultColors[0],
                width: 2
            }
        };

        const volumeTrace = {
            x: volumeData.map(d => d.date),
            y: volumeData.map(d => d.volume),
            type: 'bar',
            name: 'Volume',
            yaxis: 'y2',
            marker: {
                color: volumeData.map(d => d.price_change >= 0 ? this.defaultColors[1] : this.defaultColors[2]),
                opacity: 0.6
            }
        };

        const layout = {
            title: {
                text: 'Price and Volume Analysis',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid
            },
            yaxis: {
                title: 'Price ($)',
                color: colors.axis,
                gridcolor: colors.grid,
                side: 'left'
            },
            yaxis2: {
                title: 'Volume',
                color: colors.axis,
                overlaying: 'y',
                side: 'right',
                showgrid: false
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 80, b: 50, l: 80 },
            legend: {
                x: 0,
                y: 1,
                bgcolor: 'rgba(0,0,0,0)'
            }
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [priceTrace, volumeTrace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create volatility surface chart
     * @param {string} containerId - Container element ID
     * @param {Array} volatilityData - Volatility surface data
     */
    createVolatilitySurface(containerId, volatilityData) {
        const colors = this.getThemeColors();

        const trace = {
            z: volatilityData.volatility_matrix,
            x: volatilityData.strikes,
            y: volatilityData.expiries,
            type: 'surface',
            colorscale: 'Viridis',
            hovertemplate: '<b>Strike: %{x}</b><br>Expiry: %{y}<br>Volatility: %{z:.2%}<extra></extra>',
            showscale: true,
            colorbar: {
                title: 'Implied Volatility',
                titleside: 'right'
            }
        };

        const layout = {
            title: {
                text: 'Implied Volatility Surface',
                font: { color: colors.text, size: 16 }
            },
            scene: {
                xaxis: {
                    title: 'Strike Price',
                    color: colors.axis
                },
                yaxis: {
                    title: 'Days to Expiry',
                    color: colors.axis
                },
                zaxis: {
                    title: 'Implied Volatility',
                    color: colors.axis
                },
                bgcolor: colors.background
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 30 }
        };

        const config = {
            responsive: true,
            displayModeBar: true
        };

        Plotly.newPlot(containerId, [trace], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create rolling statistics chart
     * @param {string} containerId - Container element ID
     * @param {Array} data - Time series data
     * @param {string} metric - Metric to display (volatility, beta, etc.)
     */
    createRollingStatsChart(containerId, data, metric = 'volatility') {
        const colors = this.getThemeColors();

        const traces = [];

        // Main metric trace
        traces.push({
            x: data.map(d => d.date),
            y: data.map(d => d[metric]),
            type: 'scatter',
            mode: 'lines',
            name: metric.charAt(0).toUpperCase() + metric.slice(1),
            line: {
                color: this.defaultColors[0],
                width: 2
            },
            hovertemplate: '<b>%{x}</b><br>' + metric + ': %{y:.4f}<extra></extra>'
        });

        // Add confidence bands if available
        if (data[0] && data[0][`${metric}_upper`]) {
            traces.push({
                x: data.map(d => d.date),
                y: data.map(d => d[`${metric}_upper`]),
                type: 'scatter',
                mode: 'lines',
                name: 'Upper Band',
                line: { color: 'transparent' },
                showlegend: false,
                hoverinfo: 'skip'
            });

            traces.push({
                x: data.map(d => d.date),
                y: data.map(d => d[`${metric}_lower`]),
                type: 'scatter',
                mode: 'lines',
                name: 'Lower Band',
                fill: 'tonexty',
                fillcolor: 'rgba(37, 99, 235, 0.1)',
                line: { color: 'transparent' },
                showlegend: false,
                hoverinfo: 'skip'
            });
        }

        const layout = {
            title: {
                text: `Rolling ${metric.charAt(0).toUpperCase() + metric.slice(1)} (30-day window)`,
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Date',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: metric.charAt(0).toUpperCase() + metric.slice(1),
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                tickformat: '.4f'
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: true,
            legend: {
                x: 0,
                y: 1,
                bgcolor: 'rgba(0,0,0,0)'
            }
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, traces, layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Create options chain visualization
     * @param {string} containerId - Container element ID
     * @param {Object} optionsData - Options chain data
     */
    createOptionsChain(containerId, optionsData) {
        const colors = this.getThemeColors();

        const callTrace = {
            x: optionsData.strikes,
            y: optionsData.call_volumes,
            type: 'bar',
            name: 'Call Volume',
            marker: {
                color: this.defaultColors[1],
                opacity: 0.7
            },
            hovertemplate: '<b>Strike: %{x}</b><br>Call Volume: %{y}<extra></extra>'
        };

        const putTrace = {
            x: optionsData.strikes,
            y: optionsData.put_volumes.map(v => -v), // Negative for puts
            type: 'bar',
            name: 'Put Volume',
            marker: {
                color: this.defaultColors[2],
                opacity: 0.7
            },
            hovertemplate: '<b>Strike: %{x}</b><br>Put Volume: %{y}<extra></extra>'
        };

        // Current price line
        const currentPriceLine = {
            x: [optionsData.current_price, optionsData.current_price],
            y: [Math.min(...optionsData.put_volumes.map(v => -v)), Math.max(...optionsData.call_volumes)],
            type: 'scatter',
            mode: 'lines',
            name: 'Current Price',
            line: {
                color: colors.text,
                width: 2,
                dash: 'dash'
            },
            hovertemplate: '<b>Current Price: %{x}</b><extra></extra>'
        };

        const layout = {
            title: {
                text: 'Options Volume by Strike',
                font: { color: colors.text, size: 16 }
            },
            xaxis: {
                title: 'Strike Price',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true
            },
            yaxis: {
                title: 'Volume (Calls +, Puts -)',
                color: colors.axis,
                gridcolor: colors.grid,
                showgrid: true,
                zeroline: true,
                zerolinecolor: colors.axis
            },
            plot_bgcolor: colors.background,
            paper_bgcolor: colors.paper,
            font: { color: colors.text },
            margin: { t: 50, r: 30, b: 50, l: 80 },
            showlegend: true,
            legend: {
                x: 0,
                y: 1,
                bgcolor: 'rgba(0,0,0,0)'
            },
            barmode: 'relative'
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        Plotly.newPlot(containerId, [putTrace, callTrace, currentPriceLine], layout, config);

        this.charts.set(containerId, {
            type: 'plotly',
            instance: document.getElementById(containerId),
            containerId
        });
    }

    /**
     * Generate sample data for testing
     * @param {number} days - Number of days
     * @returns {Array} Sample data array
     */
    generateSampleData(days = 30) {
        const data = [];
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - days);

        let value = 100000;
        let maxValue = value;

        for (let i = 0; i < days; i++) {
            const date = new Date(startDate);
            date.setDate(date.getDate() + i);

            value += (Math.random() - 0.5) * 2000; // Random walk
            value = Math.max(50000, value); // Minimum value
            maxValue = Math.max(maxValue, value);

            const returns = i > 0 ? (value - data[i-1].value) / data[i-1].value : 0;
            const volatility = 0.1 + Math.random() * 0.3; // 10-40% volatility
            const drawdown = (value - maxValue) / maxValue;

            data.push({
                date: date.toISOString().split('T')[0],
                value: value,
                returns: returns,
                cumulative_return: (value - 100000) / 100000,
                drawdown: drawdown,
                volatility: volatility,
                sharpe_ratio: 0.5 + Math.random() * 1.5, // Random Sharpe between 0.5-2.0
                beta: 0.8 + Math.random() * 0.8, // Beta between 0.8-1.6
                volume: Math.floor(Math.random() * 1000000) + 100000
            });
        }

        return data;
    }

    /**
     * Generate sample correlation data
     * @param {Array} symbols - Array of symbols
     * @returns {Array} Correlation matrix data
     */
    generateCorrelationData(symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']) {
        return symbols.map(symbol => ({
            symbol,
            correlations: symbols.map(() => (Math.random() - 0.5) * 2) // Random correlations between -1 and 1
        }));
    }

    /**
     * Generate sample volatility surface data
     * @returns {Object} Volatility surface data
     */
    generateVolatilitySurface() {
        const strikes = Array.from({length: 20}, (_, i) => 80 + i * 5); // Strikes from 80 to 175
        const expiries = Array.from({length: 12}, (_, i) => 30 + i * 30); // Expiries from 30 to 360 days

        const volatility_matrix = expiries.map(() =>
            strikes.map(() => 0.15 + Math.random() * 0.25) // Volatility between 15% and 40%
        );

        return {
            strikes,
            expiries,
            volatility_matrix
        };
    }

    /**
     * Generate sample options chain data
     * @param {number} currentPrice - Current stock price
     * @returns {Object} Options chain data
     */
    generateOptionsChain(currentPrice = 150) {
        const strikes = Array.from({length: 21}, (_, i) => currentPrice - 50 + i * 5);
        const call_volumes = strikes.map(strike => {
            const distance = Math.abs(strike - currentPrice);
            return Math.max(0, 1000 - distance * 50 + Math.random() * 500);
        });
        const put_volumes = strikes.map(strike => {
            const distance = Math.abs(strike - currentPrice);
            return Math.max(0, 800 - distance * 40 + Math.random() * 400);
        });

        return {
            strikes,
            call_volumes,
            put_volumes,
            current_price: currentPrice
        };
    }
}

// Create global chart manager instance
window.chartManager = new ChartManager();

// Auto-resize charts on window resize
window.addEventListener('resize', debounce(() => {
    window.chartManager.charts.forEach((chart, containerId) => {
        window.chartManager.resizeChart(containerId);
    });
}, 250));

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartManager };
}