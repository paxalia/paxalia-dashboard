// Paxalia Dashboard — server process monitoring
(function () {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;

    function appendCell(row, value) {
        const cell = document.createElement('td');
        cell.textContent = value === null || value === undefined ? '' : String(value);
        row.appendChild(cell);
    }

    async function updateProcesses() {
        const tbody = document.getElementById('processes-list');
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

            const processes = Array.isArray(data.processes) ? data.processes : [];
            if (!processes.length) {
                const row = document.createElement('tr');
                appendCell(row, 'No processes found.');
                row.firstChild.colSpan = 5;
                tbody.appendChild(row);
                return;
            }

            processes.forEach(function (proc) {
                const row = document.createElement('tr');
                appendCell(row, proc.pid);
                appendCell(row, proc.name);
                appendCell(row, Number(proc.cpu) || 0);
                appendCell(row, Number(proc.memory) || 0);
                appendCell(row, proc.status);
                tbody.appendChild(row);
            });
        } catch (error) {
            console.error('[Paxalia] Error fetching processes:', error);
            tbody.replaceChildren();
            const row = document.createElement('tr');
            appendCell(row, 'Error loading processes.');
            row.firstChild.colSpan = 5;
            row.firstChild.className = 'status-error';
            tbody.appendChild(row);
        }
    }

    function init() {
        if (!API_URL) {
            console.warn('[Paxalia] Server API URL is not defined. Process monitoring is disabled.');
            return;
        }
        updateProcesses();
        window.setInterval(updateProcesses, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
