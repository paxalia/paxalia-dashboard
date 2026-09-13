// Paxalia Dashboard — server disk monitoring
(function () {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;
    const HISTORY_URL = window.SERVER_API_HISTORY_URL;
    let diskIOChart = null;

    function formatBytes(bytes) {
        const value = Number(bytes) || 0;
        if (value === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
        return (value / Math.pow(1024, index)).toFixed(2) + ' ' + units[index];
    }

    function appendText(parent, tag, value, className) {
        const element = document.createElement(tag);
        element.textContent = value === null || value === undefined ? '' : String(value);
        if (className) element.className = className;
        parent.appendChild(element);
        return element;
    }

    function initChart() {
        const canvas = document.getElementById('diskIOChart');
        if (!canvas || typeof Chart === 'undefined') return;

        diskIOChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Read (MB)', data: [], fill: true, tension: 0.3, pointRadius: 1 },
                    { label: 'Write (MB)', data: [], fill: true, tension: 0.3, pointRadius: 1 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    async function updateDisk() {
        const partitions = document.getElementById('disk-partitions');
        const reads = document.getElementById('disk-reads');
        const writes = document.getElementById('disk-writes');

        if (!partitions || !API_URL) return;

        try {
            const response = await fetch(API_URL, {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store'
            });
            if (!response.ok) throw new Error('Server returned ' + response.status);

            const data = await response.json();
            const io = (data.disk && data.disk.io) || {};
            const disk = data.disk || {};

            if (reads) reads.textContent = Number(io.read_count) || 0;
            if (writes) writes.textContent = Number(io.write_count) || 0;

            partitions.replaceChildren();

            const entries = Object.entries(disk.partitions || {});
            if (!entries.length) {
                appendText(partitions, 'p', 'No disk partitions found.', 'status-empty');
            }

            entries.forEach(function ([device, info]) {
                const safe = info || {};
                const card = document.createElement('div');
                card.className = 'disk-partition';

                const label = document.createElement('div');
                label.className = 'partition-label';
                label.textContent = `${device} (${safe.mount || ''})`;
                card.appendChild(label);

                const bar = document.createElement('div');
                bar.className = 'partition-bar';
                const fill = document.createElement('div');
                fill.className = 'partition-fill';
                const percent = Math.max(0, Math.min(100, Number(safe.percent) || 0));
                fill.style.width = percent + '%';
                fill.style.background = percent > 90
                    ? '#ff6384'
                    : (percent > 70 ? '#ff9f40' : '#36a2eb');
                bar.appendChild(fill);
                card.appendChild(bar);

                appendText(
                    card,
                    'div',
                    `${formatBytes(safe.used)} / ${formatBytes(safe.total)} (${percent}%)`,
                    'partition-stats'
                );
                partitions.appendChild(card);
            });

            if (HISTORY_URL && diskIOChart) {
                try {
                    const historyResponse = await fetch(HISTORY_URL, {
                        headers: { 'Accept': 'application/json' },
                        credentials: 'same-origin',
                        cache: 'no-store'
                    });
                    if (!historyResponse.ok) {
                        throw new Error('History returned ' + historyResponse.status);
                    }

                    const history = await historyResponse.json();
                    const rows = Array.isArray(history) ? history : [];
                    diskIOChart.data.labels = rows.map(item => new Date(item.time).toLocaleTimeString());
                    diskIOChart.data.datasets[0].data = rows.map(
                        item => (Number(item.disk_io_read) || 0) / (1024 * 1024)
                    );
                    diskIOChart.data.datasets[1].data = rows.map(
                        item => (Number(item.disk_io_write) || 0) / (1024 * 1024)
                    );
                    diskIOChart.update();
                } catch (error) {
                    console.warn('[Paxalia] Disk history unavailable:', error);
                }
            }
        } catch (error) {
            console.error('[Paxalia] Error fetching disk metrics:', error);
            partitions.replaceChildren();
            appendText(partitions, 'p', 'Error loading disk metrics.', 'status-error');
        }
    }

    function init() {
        if (!API_URL) {
            console.warn('[Paxalia] Server API URL is not defined. Disk monitoring is disabled.');
            return;
        }
        initChart();
        updateDisk();
        window.setInterval(updateDisk, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
