// static/analytics/scripts/realtime.js

(function() {
    'use strict';

    const config = window.ANALYTICS_CONFIG || {};
    const dataUrl = config.realtimeDataUrl || '/insights/api/realtime/data/';
    const refreshSeconds = parseInt(config.realtimeRefreshSeconds, 10) || 30;
    const emptyMessage = config.realtimeEmptyMessage || 'No recent activity.';

    function makeCell(value) {
        var td = document.createElement('td');
        td.textContent = (value === null || value === undefined) ? '' : String(value);
        return td;
    }

    function fetchRealtimeData() {
        fetch(dataUrl)
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                var uniqueCount = document.getElementById('uniqueCount');
                var viewCount = document.getElementById('viewCount');
                var updateTime = document.getElementById('updateTime');
                var tbody = document.querySelector('#realtimeTable tbody');

                if (uniqueCount) uniqueCount.textContent = data.unique_ips || 0;
                if (viewCount) viewCount.textContent = data.total_views || 0;
                if (updateTime) updateTime.textContent = data.timestamp || '';

                if (tbody) {
                    // Clear existing rows without touching innerHTML.
                    while (tbody.firstChild) {
                        tbody.removeChild(tbody.firstChild);
                    }
                    if (!data.recent || data.recent.length === 0) {
                        var emptyRow = document.createElement('tr');
                        var emptyCell = document.createElement('td');
                        emptyCell.setAttribute('colspan', '5');
                        emptyCell.textContent = emptyMessage;
                        emptyRow.appendChild(emptyCell);
                        tbody.appendChild(emptyRow);
                    } else {
                        data.recent.forEach(function(r) {
                            var tr = document.createElement('tr');
                            tr.appendChild(makeCell(r.path));
                            tr.appendChild(makeCell(r.ip_hash));
                            tr.appendChild(makeCell(r.method));
                            tr.appendChild(makeCell(r.status_code));
                            tr.appendChild(makeCell(r.time));
                            tbody.appendChild(tr);
                        });
                    }
                }
            })
            .catch(function(err) {
                console.warn('[Realtime] Fetch error:', err);
            });
    }

    // ─── Initial fetch ──────────────────────────────────────────────
    fetchRealtimeData();

    // ─── Polling ─────────────────────────────────────────────────────
    var intervalId = setInterval(fetchRealtimeData, refreshSeconds * 1000);

    // ─── Cleanup ─────────────────────────────────────────────────────
    if (typeof window._realtimeCleanup !== 'undefined') {
        window._realtimeCleanup();
    }
    window._realtimeCleanup = function() {
        clearInterval(intervalId);
    };
})();