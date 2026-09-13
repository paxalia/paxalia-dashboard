// Paxalia Dashboard — system service monitoring
(function () {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;

    function appendCell(row, value) {
        const cell = document.createElement('td');
        cell.textContent = value === null || value === undefined ? '' : String(value);
        row.appendChild(cell);
    }

    async function updateServices() {
        const tbody = document.getElementById('services-list');
        if (!tbody || !API_URL) return;

        try {
            const response = await fetch(API_URL, {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (!response.ok) throw new Error('Server returned ' + response.status);

            const data = await response.json();
            tbody.replaceChildren();

            const services = Array.isArray(data.services) ? data.services : [];
            if (!services.length) {
                const row = document.createElement('tr');
                appendCell(row, 'No services found or systemd is not available.');
                row.firstChild.colSpan = 5;
                tbody.appendChild(row);
                return;
            }

            services.forEach(function (svc) {
                const row = document.createElement('tr');
                appendCell(row, svc.name);
                appendCell(row, svc.load);
                appendCell(row, svc.active);
                appendCell(row, svc.sub);
                appendCell(row, svc.description);
                tbody.appendChild(row);
            });
        } catch (error) {
            console.error('[Paxalia] Error fetching services:', error);
            tbody.replaceChildren();
            const row = document.createElement('tr');
            appendCell(row, 'Error loading services.');
            row.firstChild.colSpan = 5;
            row.firstChild.className = 'status-error';
            tbody.appendChild(row);
        }
    }

    function init() {
        if (!API_URL) {
            console.warn('[Paxalia] Server API URL is not defined. Service monitoring is disabled.');
            return;
        }
        updateServices();
        window.setInterval(updateServices, 10000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
