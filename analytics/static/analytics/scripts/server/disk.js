// analytics/static/analytics/scripts/server/disk.js

(function() {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;
    const HISTORY_URL = window.SERVER_API_HISTORY_URL;

    if (!API_URL || !HISTORY_URL) {
        console.warn('[Analytics] Server API URLs not defined. Disk charts will not work.');
        return;
    }

    let diskIOChart;

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function initChart() {
        const ctx = document.getElementById('diskIOChart');
        if (!ctx) return;

        diskIOChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Read (MB)',
                        data: [],
                        borderColor: '#4bc0c0',
                        backgroundColor: 'rgba(75,192,192,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 1
                    },
                    {
                        label: 'Write (MB)',
                        data: [],
                        borderColor: '#ff9f40',
                        backgroundColor: 'rgba(255,159,64,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 1
                    }
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

    function updateDisk() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const io = data.disk.io;
                document.getElementById('disk-reads').textContent = io.read_count || 0;
                document.getElementById('disk-writes').textContent = io.write_count || 0;

                const partitionsDiv = document.getElementById('disk-partitions');
                if (!partitionsDiv) return;

                partitionsDiv.innerHTML = '';

                for (const [dev, info] of Object.entries(data.disk.partitions)) {
                    const bar = document.createElement('div');
                    bar.className = 'disk-partition';
                    const pct = info.percent || 0;
                    const color = pct > 90 ? '#ff6384' : (pct > 70 ? '#ff9f40' : '#36a2eb');
                    bar.innerHTML = `
                        <div class="partition-label">${dev} (${info.mount || ''})</div>
                        <div class="partition-bar">
                            <div class="partition-fill" style="width: ${pct}%; background: ${color};"></div>
                        </div>
                        <div class="partition-stats">${formatBytes(info.used || 0)} / ${formatBytes(info.total || 0)} (${pct}%)</div>
                    `;
                    partitionsDiv.appendChild(bar);
                }

                fetch(HISTORY_URL)
                    .then(res => res.json())
                    .then(history => {
                        if (!diskIOChart) return;
                        const labels = history.map(item => new Date(item.time).toLocaleTimeString());
                        const readData = history.map(item => (item.disk_io_read || 0) / (1024 * 1024));
                        const writeData = history.map(item => (item.disk_io_write || 0) / (1024 * 1024));
                        diskIOChart.data.labels = labels;
                        diskIOChart.data.datasets[0].data = readData;
                        diskIOChart.data.datasets[1].data = writeData;
                        diskIOChart.update();
                    });
            })
            .catch(console.error);
    }

    document.addEventListener('DOMContentLoaded', function() {
        initChart();
        updateDisk();
        setInterval(updateDisk, 5000);
    });
})();