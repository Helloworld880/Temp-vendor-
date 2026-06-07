// Vendor Dashboard JavaScript functionality

class VendorDashboard {
    constructor() {
        this.apiBaseUrl = '/api';
        this.currentView = 'overview';
        this.charts = {};
        this.initializeDashboard();
    }

    // Initialize dashboard functionality
    initializeDashboard() {
        this.setupEventListeners();
        this.loadInitialData();
        this.setupRealTimeUpdates();
        this.initializeCharts();
    }

    // Setup event listeners for interactive elements
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                this.handleNavigation(e.target.dataset.view);
            });
        });

        // Search functionality
        const searchInput = document.getElementById('vendor-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }

        // Filter controls
        document.querySelectorAll('.filter-control').forEach(control => {
            control.addEventListener('change', (e) => {
                this.applyFilters();
            });
        });

        // Export buttons
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleExport(e.target.dataset.format, e.target.dataset.type);
            });
        });

        // Refresh data
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshData();
            });
        }

        // Mobile menu toggle
        const mobileMenuBtn = document.getElementById('mobile-menu-btn');
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => {
                this.toggleMobileMenu();
            });
        }

        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }
    }

    // Handle navigation between views
    handleNavigation(view) {
        this.currentView = view;
        
        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-view="${view}"]`).classList.add('active');

        // Load view-specific data
        this.loadViewData(view);
        
        // Update URL without page reload
        history.pushState({ view }, '', `?view=${view}`);
    }

    // Load initial dashboard data
    async loadInitialData() {
        try {
            const [summary, alerts, performance] = await Promise.all([
                this.fetchData('/analytics?type=overview'),
                this.fetchData('/alerts?limit=5'),
                this.fetchData('/performance')
            ]);

            this.updateSummaryMetrics(summary);
            this.updateAlerts(alerts);
            this.updatePerformanceCharts(performance);
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    // Load data for specific view
    async loadViewData(view) {
        try {
            let data;
            switch (view) {
                case 'performance':
                    data = await this.fetchData('/performance?detailed=true');
                    this.renderPerformanceView(data);
                    break;
                case 'risk':
                    data = await this.fetchData('/analytics?type=risk');
                    this.renderRiskView(data);
                    break;
                case 'financial':
                    data = await this.fetchData('/financial');
                    this.renderFinancialView(data);
                    break;
                case 'compliance':
                    data = await this.fetchData('/compliance');
                    this.renderComplianceView(data);
                    break;
                default:
                    // Overview is handled by loadInitialData
                    break;
            }
        } catch (error) {
            console.error(`Error loading ${view} data:`, error);
            this.showError(`Failed to load ${view} data`);
        }
    }

    // Fetch data from API
    async fetchData(endpoint) {
        const response = await fetch(`${this.apiBaseUrl}${endpoint}`);
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        return await response.json();
    }

    // Update summary metrics on dashboard
    updateSummaryMetrics(data) {
        const metrics = {
            'total-vendors': data.total_vendors,
            'avg-performance': `${data.average_performance.toFixed(1)}%`,
            'high-risk-count': data.high_risk_count,
            'cost-savings': `$${this.formatNumber(data.cost_savings)}`
        };

        Object.entries(metrics).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    }

    // Update alerts section
    updateAlerts(alerts) {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;

        alertsContainer.innerHTML = alerts.map(alert => `
            <div class="alert-card ${alert.severity.toLowerCase()}">
                <div class="alert-header">
                    <span class="alert-type">${alert.type}</span>
                    <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
                </div>
                <div class="alert-message">${alert.message}</div>
                <div class="alert-actions">
                    <button class="btn-sm" onclick="dashboard.acknowledgeAlert('${alert.id}')">
                        Acknowledge
                    </button>
                </div>
            </div>
        `).join('');
    }

    // Update performance charts
    updatePerformanceCharts(performanceData) {
        if (this.charts.performanceTrend) {
            this.updateTrendChart(performanceData.trends);
        }

        if (this.charts.performanceDistribution) {
            this.updateDistributionChart(performanceData.distribution);
        }

        if (this.charts.riskMatrix) {
            this.updateRiskMatrix(performanceData.risk_assessment);
        }
    }

    // Initialize charts
    initializeCharts() {
        // Performance trend chart
        this.charts.performanceTrend = new Chart(
            document.getElementById('performance-trend-chart'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Average Performance',
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            }
        );

        // Performance distribution chart
        this.charts.performanceDistribution = new Chart(
            document.getElementById('performance-distribution-chart'),
            {
                type: 'bar',
                data: {
                    labels: ['0-20', '21-40', '41-60', '61-80', '81-100'],
                    datasets: [{
                        label: 'Vendor Count',
                        data: [0, 0, 0, 0, 0],
                        backgroundColor: '#2ecc71'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            }
        );
    }

    // Update trend chart with new data
    updateTrendChart(trendData) {
        const chart = this.charts.performanceTrend;
        chart.data.labels = trendData.map(item => item.date);
        chart.data.datasets[0].data = trendData.map(item => item.average_score);
        chart.update();
    }

    // Update distribution chart
    updateDistributionChart(distributionData) {
        const chart = this.charts.performanceDistribution;
        chart.data.datasets[0].data = distributionData;
        chart.update();
    }

    // Handle vendor search
    handleSearch(query) {
        const vendors = document.querySelectorAll('.vendor-item');
        vendors.forEach(vendor => {
            const name = vendor.querySelector('.vendor-name').textContent.toLowerCase();
            if (name.includes(query.toLowerCase())) {
                vendor.style.display = '';
            } else {
                vendor.style.display = 'none';
            }
        });
    }

    // Apply filters to vendor list
    applyFilters() {
        const categoryFilter = document.getElementById('category-filter').value;
        const riskFilter = document.getElementById('risk-filter').value;
        const statusFilter = document.getElementById('status-filter').value;

        // Implementation would filter vendor list based on selected filters
        this.filterVendors({ category: categoryFilter, risk: riskFilter, status: statusFilter });
    }

    // Filter vendors based on criteria
    async filterVendors(filters) {
        try {
            const queryString = new URLSearchParams(filters).toString();
            const data = await this.fetchData(`/vendors?${queryString}`);
            this.renderVendorList(data);
        } catch (error) {
            console.error('Error filtering vendors:', error);
        }
    }

    // Handle data export
    async handleExport(format, type) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/export?type=${type}&format=${format}`);
            if (!response.ok) throw new Error('Export failed');
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `vendor_${type}_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export error:', error);
            this.showError('Export failed');
        }
    }

    // Refresh all data
    async refreshData() {
        const refreshBtn = document.getElementById('refresh-btn');
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="loading-spinner"></i> Refreshing...';

        try {
            await this.loadInitialData();
            if (this.currentView !== 'overview') {
                await this.loadViewData(this.currentView);
            }
            this.showSuccess('Data refreshed successfully');
        } catch (error) {
            this.showError('Refresh failed');
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="refresh-icon"></i> Refresh';
        }
    }

    // Acknowledge alert
    async acknowledgeAlert(alertId) {
        try {
            await fetch(`${this.apiBaseUrl}/alerts/${alertId}/acknowledge`, {
                method: 'POST'
            });
            this.loadInitialData(); // Reload alerts
        } catch (error) {
            console.error('Error acknowledging alert:', error);
        }
    }

    // Setup real-time updates
    setupRealTimeUpdates() {
        // WebSocket connection for real-time updates
        if (typeof io !== 'undefined') {
            const socket = io();
            
            socket.on('alert', (alert) => {
                this.showNotification(alert);
                this.loadInitialData(); // Refresh alerts
            });

            socket.on('performance_update', (update) => {
                this.updatePerformanceMetrics(update);
            });
        }

        // Polling fallback
        setInterval(() => {
            this.checkForUpdates();
        }, 30000); // Every 30 seconds
    }

    // Check for updates via polling
    async checkForUpdates() {
        try {
            const updates = await this.fetchData('/updates?since=' + this.lastUpdate);
            if (updates.hasUpdates) {
                this.loadInitialData();
                this.lastUpdate = updates.timestamp;
            }
        } catch (error) {
            console.error('Error checking for updates:', error);
        }
    }

    // Toggle mobile menu
    toggleMobileMenu() {
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.toggle('mobile-open');
    }

    // Toggle theme
    toggleTheme() {
        document.body.classList.toggle('dark-theme');
        const isDark = document.body.classList.contains('dark-theme');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        
        // Update charts for theme
        this.updateChartsTheme();
    }

    // Update charts for current theme
    updateChartsTheme() {
        const isDark = document.body.classList.contains('dark-theme');
        const textColor = isDark ? '#f7fafc' : '#2d3748';
        const gridColor = isDark ? '#4a5568' : '#e2e8f0';

        Object.values(this.charts).forEach(chart => {
            chart.options.scales.x.ticks.color = textColor;
            chart.options.scales.y.ticks.color = textColor;
            chart.options.scales.x.grid.color = gridColor;
            chart.options.scales.y.grid.color = gridColor;
            chart.update();
        });
    }

    // Utility function to format numbers
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    // Utility function to format time
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    // Show notification
    showNotification(message, type = 'info') {
        // Implementation would show a toast notification
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    // Show error message
    showError(message) {
        this.showNotification(message, 'error');
    }

    // Show success message
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new VendorDashboard();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VendorDashboard;
}