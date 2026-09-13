// Paxalia Dashboard — realtime visitors
(function () {
    'use strict';

    const config = window.ANALYTICS_CONFIG || {};
    const inlineConfig = window.__analytics_realtime || {};
    const dataUrl = config.realtimeDataUrl || inlineConfig.dataUrl;
    const refreshSeconds = parseInt(config.realtimeRefreshSeconds || inlineConfig.refreshSeconds, 10) || 30;
    const emptyMessage = config.realtimeEmptyMessage || inlineConfig.emptyMessage || 'No recent activity.';

    function makeCell(value) {
        const td = document.createElement('td');
        td.textContent = value === null || value === undefined ? '' : String(value);
        return td;
    }

    function setMessage(tbody, colspan, message, className) {
        tbody.replaceChildren();
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = colspan;
        td.textContent = message;
        if (className) td.className = className;
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    async function refresh() {
        const table = document.getElementById('realtimeTable');
        if (!table || !dataUrl) return;
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        try {
            const response = await fetch(dataUrl, {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (!response.ok) throw new Error('Server returned ' + response.status);
            const data = await response.json();

            document.getElementById('uniqueCount').textContent = Number(data.unique_visitors ?? data.unique_ips ?? 0).toLocaleString();
            document.getElementById('viewCount').textContent = Number(data.page_views ?? data.views ?? 0).toLocaleString();
            document.getElementById('apiCount').textContent = Number(data.api_calls ?? 0).toLocaleString();
            document.getElementById('updateTime').textContent = new Date().toLocaleTimeString();

            const rows = Array.isArray(data.recent_page_views) ? data.recent_page_views : (Array.isArray(data.results) ? data.results : []);
            tbody.replaceChildren();
            if (rows.length === 0) {
                setMessage(tbody, 5, emptyMessage, 'status-empty');
                return;
            }

            rows.forEach(function (row) {
                const tr = document.createElement('tr');
                tr.appendChild(makeCell(row.path));
                tr.appendChild(makeCell(row.ip || row.ip_address));
                tr.appendChild(makeCell(row.method));
                tr.appendChild(makeCell(row.status_code || row.status));
                tr.appendChild(makeCell(row.created_at || row.timestamp));
                tbody.appendChild(tr);
            });
        } catch (error) {
            console.error('[Paxalia] Realtime refresh failed:', error);
            setMessage(tbody, 5, 'Unable to load recent activity.', 'status-error');
        }
    }

    function init() {
        if (!dataUrl) {
            console.warn('[Paxalia] Realtime endpoint is not configured.');
            return;
        }
        refresh();
        window.setInterval(refresh, Math.max(refreshSeconds, 5) * 1000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
