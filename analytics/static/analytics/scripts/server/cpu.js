// analytics/static/analytics/scripts/server/cpu.js
(function() {
    const API_URL = window.SERVER_API_METRICS_URL || '/analytics/api/server/metrics/';
    const HISTORY_URL = window.SERVER_API_HISTORY_URL || '/analytics/api/server/history/';

    function updateCPU() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                document.getElementById('cpu-overall').textContent = data.cpu.percent + '%';
                document.getElementById('cpu-cores').textContent = data.cpu.count;
                if (data.cpu.load_avg) {
                    document.getElementById('load-avg').textContent = data.cpu.load_avg.join(' / ');
                }

                const coreLabels = data.cpu.per_core.map((_, i) => `Core ${i+1}`);
                cpuCoreChart.data.labels = coreLabels;
                cpuCoreChart.data.datasets[0].data = data.cpu.per_core;
                cpuCoreChart.update();

                fetch(HISTORY_URL)
                    .then(res => res.json())
                    .then(history => {
                        const labels = history.map(item => new Date(item.time).toLocaleTimeString());
                        const cpuData = history.map(item => item.cpu);
                        cpuHistoryChart.data.labels = labels;
                        cpuHistoryChart.data.datasets[0].data = cpuData;
                        cpuHistoryChart.update();
                    });
            })
            .catch(console.error);
    }

    let cpuCoreChart, cpuHistoryChart;

    function initCharts() {
        // CPU per core (bar)
        const ctxCore = document.getElementById('cpuCoreChart').getContext('2d');
        cpuCoreChart = new Chart(ctxCore, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU %',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        titleColor: '#c9d1d9',
                        bodyColor: '#8b949e',
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#8b949e', font: { size: 11 } }
                    }
                }
            }
        });

        // CPU history (line)
        const ctxHistory = document.getElementById('cpuHistoryChart').getContext('2d');
        cpuHistoryChart = new Chart(ctxHistory, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU %',
                    data: [],
                    borderColor: '#ff6384',
                    backgroundColor: 'rgba(255,99,132,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#c9d1d9', font: { size: 11 } }
                    },
                    tooltip: {
                        titleColor: '#c9d1d9',
                        bodyColor: '#8b949e',
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#8b949e', font: { size: 11 } }
                    }
                }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        initCharts();
        updateCPU();
        setInterval(updateCPU, 3000);
    });
})();