// static/analytics/scripts/realtime.js

(function() {
    'use strict';

    const config = window.ANALYTICS_CONFIG || {};
    const dataUrl = config.realtimeDataUrl || '/insights/api/realtime/data/';
    const refreshSeconds = parseInt(config.realtimeRefreshSeconds, 10) || 30;
    const emptyMessage = config.realtimeEmptyMessage || 'No recent activity.';

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
                    tbody.innerHTML = '';
                    if (!data.recent || data.recent.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5">' + emptyMessage + '</td></tr>';
                    } else {
                        data.recent.forEach(function(r) {
                            var tr = document.createElement('tr');
                            tr.innerHTML = [
                                '<td>' + (r.path || '') + '</td>',
                                '<td>' + (r.ip_hash || '') + '</td>',
                                '<td>' + (r.method || '') + '</td>',
                                '<td>' + (r.status_code || '') + '</td>',
                                '<td>' + (r.time || '') + '</td>'
                            ].join('');
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