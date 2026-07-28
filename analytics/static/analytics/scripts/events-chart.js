// static/analytics/scripts/events-chart.js

(function() {
    'use strict';

    function loadChart() {
        var eventsData = window.__analytics_events;
        var ctx = document.getElementById('eventsChart');

        if (!ctx) {
            return;
        }

        if (!eventsData) {
            console.warn('[EventsChart] window.__analytics_events not found – nothing to render.');
            return;
        }

        var datasets = [{
            label: 'Events',
            data: eventsData.data || [],
            borderColor: '#f6c84c',
            backgroundColor: 'rgba(246,200,76,0.08)',
            fill: true,
            tension: 0.3,
            pointBackgroundColor: '#f6c84c',
        }];

        if (eventsData.compareActive) {
            datasets.push({
                label: 'Previous period',
                data: eventsData.previousData || [],
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88,166,255,0.05)',
                borderDash: [6, 4],
                tension: 0.3,
                pointBackgroundColor: 'rgba(88,166,255,0.7)',
                pointRadius: 2,
                pointHoverRadius: 4,
                borderWidth: 2,
            });
        }

        new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: eventsData.labels || [],
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    subtitle: {
                        display: true,
                        text: eventsData.dateRangeLabel || '',
                        color: '#8b949e',
                        font: { size: 12 }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#8b949e' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#8b949e', precision: 0 },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
    }

    loadChart();

    if (typeof window._eventsChartCleanup !== 'undefined') {
        window._eventsChartCleanup();
    }
    window._eventsChartCleanup = function() {
        // Nothing to clean up (no interval)
    };
})();