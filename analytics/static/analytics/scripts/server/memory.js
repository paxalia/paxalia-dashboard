// analytics/static/analytics/scripts/server/memory.js
(function() {
    const API_URL = window.SERVER_API_METRICS_URL || '/analytics/api/server/metrics/';

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function updateMemory() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const mem = data.memory;
                document.getElementById('ram-percent').textContent = mem.percent + '%';
                document.getElementById('ram-used').textContent = formatBytes(mem.used);
                document.getElementById('ram-total').textContent = formatBytes(mem.total);
                document.getElementById('swap-percent').textContent = (mem.swap_total > 0 ? mem.swap_percent : 0) + '%';
                document.getElementById('swap-used').textContent = formatBytes(mem.swap_used);
                document.getElementById('swap-total').textContent = formatBytes(mem.swap_total);

                memoryChart.data.datasets[0].data = [mem.used, mem.available, mem.swap_used];
                memoryChart.update();
            })
            .catch(console.error);
    }

    let memoryChart;

    function initChart() {
        const ctx = document.getElementById('memoryChart').getContext('2d');
        memoryChart = new Chart(ctx, {
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

    document.addEventListener('DOMContentLoaded', function() {
        initChart();
        updateMemory();
        setInterval(updateMemory, 3000);
    });
})();