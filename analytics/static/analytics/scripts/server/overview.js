// analytics/static/analytics/scripts/server/overview.js

(function() {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;
    const HISTORY_URL = window.SERVER_API_HISTORY_URL;

    if (!API_URL || !HISTORY_URL) {
        console.warn('[Analytics] Server API URLs not defined. Overview charts will not work.');
        return;
    }

    let cpuCoreChart, memoryChart, diskIOChart, networkChart;

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function initCharts() {
        // ─── CPU per core (bar) ───
        const ctxCpu = document.getElementById('cpuCoreChart');
        if (ctxCpu) {
            cpuCoreChart = new Chart(ctxCpu.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        data: [],
                        backgroundColor: 'rgba(246, 200, 76, 0.7)',
                        borderColor: 'rgba(246, 200, 76, 1)',
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
        }

        // ─── Memory (doughnut) ───
        const ctxMem = document.getElementById('memoryChart');
        if (ctxMem) {
            memoryChart = new Chart(ctxMem.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['Used', 'Available'],
                    datasets: [{
                        data: [0, 0],
                        backgroundColor: ['#ff6384', '#36a2eb'],
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

        // ─── Disk I/O (line) ───
        const ctxDisk = document.getElementById('diskIOChart');
        if (ctxDisk) {
            diskIOChart = new Chart(ctxDisk.getContext('2d'), {
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

        // ─── Network (line) ───
        const ctxNet = document.getElementById('networkChart');
        if (ctxNet) {
            networkChart = new Chart(ctxNet.getContext('2d'), {
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
    }

    function updateOverview() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                // ─── Stat cards ───
                document.getElementById('cpu-percent').textContent = data.cpu.percent + '%';
                document.getElementById('load-avg').textContent = data.cpu.load_avg ? data.cpu.load_avg.join(' / ') : 'N/A';
                document.getElementById('mem-percent').textContent = data.memory.percent + '%';
                document.getElementById('mem-available').textContent = formatBytes(data.memory.available);

                const partitions = data.disk.partitions;
                const firstPart = Object.values(partitions)[0];
                if (firstPart) {
                    document.getElementById('disk-percent').textContent = firstPart.percent + '%';
                    document.getElementById('disk-used').textContent = formatBytes(firstPart.used);
                }

                let totalIn = 0, totalOut = 0;
                for (const iface in data.network) {
                    totalIn += data.network[iface].bytes_recv;
                    totalOut += data.network[iface].bytes_sent;
                }
                const speed = ((totalIn + totalOut) / (1024 * 1024)).toFixed(2);
                document.getElementById('net-speed').textContent = speed + ' MB';

                // ─── Update charts ───
                updateCharts(data);
            })
            .catch(console.error);
    }

    function updateCharts(data) {
        // ─── CPU per core ───
        if (cpuCoreChart) {
            const coreLabels = data.cpu.per_core.map((_, i) => `Core ${i + 1}`);
            cpuCoreChart.data.labels = coreLabels;
            cpuCoreChart.data.datasets[0].data = data.cpu.per_core;
            cpuCoreChart.update();
        }

        // ─── Memory ───
        if (memoryChart) {
            memoryChart.data.datasets[0].data = [data.memory.used, data.memory.available];
            memoryChart.update();
        }

        // ─── History charts ───
        fetch(HISTORY_URL)
            .then(res => res.json())
            .then(history => {
                const labels = history.map(item => new Date(item.time).toLocaleTimeString());
                const readData = history.map(item => item.disk_io_read / (1024 * 1024));
                const writeData = history.map(item => item.disk_io_write / (1024 * 1024));
                const inData = history.map(item => item.network_in / (1024 * 1024));
                const outData = history.map(item => item.network_out / (1024 * 1024));

                if (diskIOChart) {
                    diskIOChart.data.labels = labels;
                    diskIOChart.data.datasets[0].data = readData;
                    diskIOChart.data.datasets[1].data = writeData;
                    diskIOChart.update();
                }

                if (networkChart) {
                    networkChart.data.labels = labels;
                    networkChart.data.datasets[0].data = inData;
                    networkChart.data.datasets[1].data = outData;
                    networkChart.update();
                }
            })
            .catch(console.error);
    }

    document.addEventListener('DOMContentLoaded', function() {
        initCharts();
        updateOverview();
        setInterval(updateOverview, 5000);
    });
})();