// analytics/static/analytics/scripts/server/processes.js

(function() {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;

    if (!API_URL) {
        console.warn('[Analytics] Server API URL not defined. Processes list will not work.');
        return;
    }

    function updateProcesses() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const tbody = document.getElementById('processes-list');
                if (!tbody) return;

                tbody.innerHTML = '';

                if (data.processes && data.processes.length > 0) {
                    data.processes.forEach(proc => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${proc.pid || ''}</td>
                            <td>${proc.name || ''}</td>
                            <td>${proc.cpu || 0}</td>
                            <td>${proc.memory || 0}</td>
                            <td>${proc.status || ''}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5">No processes found.</td></tr>';
                }
            })
            .catch(error => {
                console.error('Error fetching processes:', error);
                const tbody = document.getElementById('processes-list');
                if (tbody) {
                    tbody.innerHTML = '<tr><td colspan="5">Error loading processes.</td></tr>';
                }
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateProcesses();
        setInterval(updateProcesses, 5000);
    });
})();