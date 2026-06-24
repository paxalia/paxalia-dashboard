// analytics/static/analytics/scripts/server/network.js
(function() {
    const API_URL = window.SERVER_API_METRICS_URL || '/analytics/api/server/metrics/';
    const HISTORY_URL = window.SERVER_API_HISTORY_URL || '/analytics/api/server/history/';

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function updateNetwork() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                let totalIn = 0, totalOut = 0;
                const interfacesDiv = document.getElementById('network-interfaces');
                interfacesDiv.innerHTML = '';
                for (const [iface, stats] of Object.entries(data.network)) {
                    totalIn += stats.bytes_recv;
                    totalOut += stats.bytes_sent;
                    const ifaceDiv = document.createElement('div');
                    ifaceDiv.className = 'network-interface';
                    ifaceDiv.innerHTML = `
                        <div><strong>${iface}</strong></div>
                        <div>In: ${formatBytes(stats.bytes_recv)} &nbsp;|&nbsp; Out: ${formatBytes(stats.bytes_sent)}</div>
                        <div>Packets: ${stats.packets_recv} / ${stats.packets_sent}</div>
                    `;
                    interfacesDiv.appendChild(ifaceDiv);
                }
                document.getElementById('net-in').textContent = formatBytes(totalIn);
                document.getElementById('net-out').textContent = formatBytes(totalOut);

                fetch(HISTORY_URL)
                    .then(res => res.json())
                    .then(history => {
                        const labels = history.map(item => new Date(item.time).toLocaleTimeString());
                        const inData = history.map(item => item.network_in / (1024*1024));
                        const outData = history.map(item => item.network_out / (1024*1024));
                        networkChart.data.labels = labels;
                        networkChart.data.datasets[0].data = inData;
                        networkChart.data.datasets[1].data = outData;
                        networkChart.update();
                    });
            })
            .catch(console.error);
    }

    let networkChart;

    function initChart() {
        const ctx = document.getElementById('networkChart').getContext('2d');
        networkChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'In (MB)', data: [], borderColor: '#36a2eb', backgroundColor: 'rgba(54,162,235,0.1)', fill: true, tension: 0.3, pointRadius: 1 },
                    { label: 'Out (MB)', data: [], borderColor: '#ff6384', backgroundColor: 'rgba(255,99,132,0.1)', fill: true, tension: 0.3, pointRadius: 1 }
                ]
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
        initChart();
        updateNetwork();
        setInterval(updateNetwork, 5000);
    });
})();