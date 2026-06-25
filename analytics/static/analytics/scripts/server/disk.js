// analytics/static/analytics/scripts/server/disk.js
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

    function updateDisk() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const io = data.disk.io;
                document.getElementById('disk-reads').textContent = io.read_count;
                document.getElementById('disk-writes').textContent = io.write_count;

                const partitionsDiv = document.getElementById('disk-partitions');
                partitionsDiv.innerHTML = '';
                for (const [dev, info] of Object.entries(data.disk.partitions)) {
                    const bar = document.createElement('div');
                    bar.className = 'disk-partition';
                    const pct = info.percent;
                    const color = pct > 90 ? '#ff6384' : (pct > 70 ? '#ff9f40' : '#36a2eb');
                    bar.innerHTML = `
                        <div class="partition-label">${dev} (${info.mount})</div>
                        <div class="partition-bar">
                            <div class="partition-fill" style="width: ${pct}%; background: ${color};"></div>
                        </div>
                        <div class="partition-stats">${formatBytes(info.used)} / ${formatBytes(info.total)} (${pct}%)</div>
                    `;
                    partitionsDiv.appendChild(bar);
                }

                fetch(HISTORY_URL)
                    .then(res => res.json())
                    .then(history => {
                        const labels = history.map(item => new Date(item.time).toLocaleTimeString());
                        const readData = history.map(item => item.disk_io_read / (1024*1024));
                        const writeData = history.map(item => item.disk_io_write / (1024*1024));
                        diskIOChart.data.labels = labels;
                        diskIOChart.data.datasets[0].data = readData;
                        diskIOChart.data.datasets[1].data = writeData;
                        diskIOChart.update();
                    });
            })
            .catch(console.error);
    }

    let diskIOChart;

    function initChart() {
        const ctx = document.getElementById('diskIOChart').getContext('2d');
        diskIOChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Read (MB)', data: [], borderColor: '#4bc0c0', backgroundColor: 'rgba(75,192,192,0.1)', fill: true, tension: 0.3, pointRadius: 1 },
                    { label: 'Write (MB)', data: [], borderColor: '#ff9f40', backgroundColor: 'rgba(255,159,64,0.1)', fill: true, tension: 0.3, pointRadius: 1 }
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
        updateDisk();
        setInterval(updateDisk, 5000);
    });
})();