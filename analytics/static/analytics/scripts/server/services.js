// analytics/static/analytics/scripts/server/services.js

(function() {
    'use strict';

    const API_URL = window.SERVER_API_METRICS_URL;

    if (!API_URL) {
        console.warn('[Analytics] Server API URL not defined. Services list will not work.');
        return;
    }

    function updateServices() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const tbody = document.getElementById('services-list');
                if (!tbody) return;

                tbody.innerHTML = '';

                if (data.services && data.services.length > 0) {
                    data.services.forEach(svc => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${svc.name || ''}</td>
                            <td>${svc.load || ''}</td>
                            <td>${svc.active || ''}</td>
                            <td>${svc.sub || ''}</td>
                            <td>${svc.description || ''}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = `<tr><td colspan="5">No services found or systemd not available.</td></tr>`;
                }
            })
            .catch(error => {
                console.error('Error fetching services:', error);
                const tbody = document.getElementById('services-list');
                if (tbody) {
                    tbody.innerHTML = `<tr><td colspan="5">Error loading services.</td></tr>`;
                }
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateServices();
        setInterval(updateServices, 10000);
    });
})();