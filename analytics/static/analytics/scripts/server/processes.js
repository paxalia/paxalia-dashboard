// analytics/static/analytics/scripts/server/processes.js
(function() {
    const API_URL = window.SERVER_API_METRICS_URL || '/analytics/api/server/metrics/';

    function updateProcesses() {
        fetch(API_URL)
            .then(response => response.json())
            .then(data => {
                const tbody = document.getElementById('processes-list');
                tbody.innerHTML = '';
                if (data.processes && data.processes.length > 0) {
                    data.processes.forEach(proc => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${proc.pid}</td>
                            <td>${proc.name}</td>
                            <td>${proc.cpu}</td>
                            <td>${proc.memory}</td>
                            <td>${proc.status}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5">No processes found.</td></tr>';
                }
            })
            .catch(error => {
                console.error('Error fetching processes:', error);
                document.getElementById('processes-list').innerHTML = '<tr><td colspan="5">Error loading processes.</td></tr>';
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateProcesses();
        setInterval(updateProcesses, 5000);
    });
})();