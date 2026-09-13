// Paxalia Dashboard — server network monitoring
(function () {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;
    const HISTORY_URL = window.SERVER_API_HISTORY_URL;
    let networkChart = null;

    function formatBytes(bytes) {
        const value = Number(bytes) || 0;
        if (value === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.min(Math.floor(Math.log(value) / Math.log(k)), sizes.length - 1);
        return (value / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    function appendText(parent, tag, value, className) {
        const element = document.createElement(tag);
        element.textContent = value === null || value === undefined ? '' : String(value);
        if (className) element.className = className;
        parent.appendChild(element);
        return element;
    }

    async function updateNetwork() {
        const interfacesDiv = document.getElementById('network-interfaces');
        const inEl = document.getElementById('net-in');
        const outEl = document.getElementById('net-out');
        if (!interfacesDiv || !API_URL) return;

        try {
            const response = await fetch(API_URL, {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (!response.ok) throw new Error('Server returned ' + response.status);

            const data = await response.json();
            const network = data.network && typeof data.network === 'object' ? data.network : {};
            let totalIn = 0;
            let totalOut = 0;
            interfacesDiv.replaceChildren();

            const entries = Object.entries(network);
            if (entries.length === 0) {
                appendText(interfacesDiv, 'p', 'No network interfaces found.', 'status-empty');
            }

            entries.forEach(function ([iface, stats]) {
                const safeStats = stats || {};
                const bytesRecv = Number(safeStats.bytes_recv) || 0;
                const bytesSent = Number(safeStats.bytes_sent) || 0;
                totalIn += bytesRecv;
                totalOut += bytesSent;

                const card = document.createElement('div');
                card.className = 'network-interface';
                appendText(card, 'strong', iface);
                appendText(card, 'div', `In: ${formatBytes(bytesRecv)} | Out: ${formatBytes(bytesSent)}`);
                appendText(card, 'div', `Packets: ${Number(safeStats.packets_recv) || 0} / ${Number(safeStats.packets_sent) || 0}`);
                interfacesDiv.appendChild(card);
            });

            if (inEl) inEl.textContent = formatBytes(totalIn);
            if (outEl) outEl.textContent = formatBytes(totalOut);

            if (HISTORY_URL && networkChart) {
                try {
                    const historyResponse = await fetch(HISTORY_URL, {
                        headers: { 'Accept': 'application/json' },
                        credentials: 'same-origin',
                        cache: 'no-store',
                    });
                    if (!historyResponse.ok) throw new Error('History returned ' + historyResponse.status);
                    const history = await historyResponse.json();
                    const rows = Array.isArray(history) ? history : [];
                    networkChart.data.labels = rows.map(item => new Date(item.time).toLocaleTimeString());
                    networkChart.data.datasets[0].data = rows.map(item => Number(item.network_bytes_recv) || 0);
                    networkChart.data.datasets[1].data = rows.map(item => Number(item.network_bytes_sent) || 0);
                    networkChart.update();
                } catch (error) {
                    console.warn('[Paxalia] Network history unavailable:', error);
                }
            }
        } catch (error) {
            console.error('[Paxalia] Error fetching network metrics:', error);
            interfacesDiv.replaceChildren();
            appendText(interfacesDiv, 'p', 'Error loading network metrics.', 'status-error');
        }
    }

    function initChart() {
        const ctx = document.getElementById('networkChart');
        if (!ctx || typeof Chart === 'undefined') return;
        networkChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Inbound', data: [], tension: 0.3 },
                    { label: 'Outbound', data: [], tension: 0.3 },
                ],
            },
            options: { responsive: true, maintainAspectRatio: false },
        });
    }

    function init() {
        if (!API_URL) {
            console.warn('[Paxalia] Server API URL not defined. Network monitoring will not work.');
            return;
        }
        initChart();
        updateNetwork();
        window.setInterval(updateNetwork, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
