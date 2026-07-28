// analytics/static/analytics/scripts/server/memory.js

(function() {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;

    if (!API_URL) {
        console.warn('[Analytics] Server API URL not defined. Memory chart will not work.');
        return;
    }

    let memoryChart;

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function initChart() {
        const ctx = document.getElementById('memoryChart');
        if (!ctx) return;

        memoryChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Used RAM', 'Available RAM', 'Used Swap'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#ff6384', '#36a2eb', '#ff9f40'],
                    borderWidth: 2,
                    borderColor: '#161b22',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#c9d1d9', font: { size: 12 } }
                    },
                    tooltip: {
                        titleColor: '#c9d1d9',
                        bodyColor: '#8b949e',
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        borderWidth: 1
                    }
                },
                cutout: '70%',
            }
        });
    }

    function updateMemory() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const mem = data.memory;
                document.getElementById('ram-percent').textContent = (mem.percent || 0) + '%';
                document.getElementById('ram-used').textContent = formatBytes(mem.used || 0);
                document.getElementById('ram-total').textContent = formatBytes(mem.total || 0);
                document.getElementById('swap-percent').textContent = (mem.swap_total > 0 ? mem.swap_percent || 0 : 0) + '%';
                document.getElementById('swap-used').textContent = formatBytes(mem.swap_used || 0);
                document.getElementById('swap-total').textContent = formatBytes(mem.swap_total || 0);

                if (memoryChart) {
                    memoryChart.data.datasets[0].data = [mem.used || 0, mem.available || 0, mem.swap_used || 0];
                    memoryChart.update();
                }
            })
            .catch(console.error);
    }

    document.addEventListener('DOMContentLoaded', function() {
        initChart();
        updateMemory();
        setInterval(updateMemory, 3000);
    });
})();