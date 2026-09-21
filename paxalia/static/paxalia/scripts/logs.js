(function () {
    'use strict';

    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var area = document.createElement('textarea');
            area.value = text;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            try {
                var ok = document.execCommand('copy');
                document.body.removeChild(area);
                if (ok) resolve(); else reject(new Error('copy failed'));
            } catch (error) {
                document.body.removeChild(area);
                reject(error);
            }
        });
    }

    function initCopyButtons() {
        document.querySelectorAll('[data-copy-target]').forEach(function (button) {
            button.addEventListener('click', function () {
                var selector = button.getAttribute('data-copy-target');
                var target = selector ? document.querySelector(selector) : null;
                if (!target) return;

                var status = button.closest('.log-ai-card')?.querySelector('[data-copy-status]');
                var original = button.textContent;
                button.disabled = true;

                copyText(target.textContent.trim())
                    .then(function () {
                        button.textContent = 'Copied';
                        if (status) status.textContent = 'AI-ready details copied to the clipboard.';
                        window.setTimeout(function () {
                            button.textContent = original;
                            button.disabled = false;
                        }, 1500);
                    })
                    .catch(function () {
                        button.disabled = false;
                        if (status) status.textContent = 'Copy was blocked. Select the text manually.';
                    });
            });
        });
    }

    function initAutoRefresh() {
        var toggle = document.querySelector('[data-log-autorefresh]');
        if (!toggle) return;

        var feedUrl = toggle.getAttribute('data-feed-url');
        var detailUrlTemplate = toggle.getAttribute('data-detail-url-template') || '';
        var tbody = document.querySelector('[data-log-tbody]');
        var timer = null;
        var refreshSeconds = Math.max(5, parseInt(toggle.getAttribute('data-refresh-seconds') || '30', 10));
        var uuidPlaceholder = '00000000-0000-0000-0000-000000000000';

        function severityClass(severity) {
            var value = String(severity || 'INFO').toLowerCase();
            return ['critical', 'error', 'warning', 'info', 'debug'].indexOf(value) !== -1 ? value : 'info';
        }

        function addCell(row, value, className) {
            var cell = document.createElement('td');
            if (className) cell.className = className;
            cell.textContent = value == null || value === '' ? '—' : String(value);
            row.appendChild(cell);
            return cell;
        }

        function addSeverityCell(row, severity) {
            var cell = document.createElement('td');
            var value = severity || 'INFO';
            var badge = document.createElement('span');
            badge.className = 'log-severity-badge log-severity-badge--' + severityClass(value);
            badge.textContent = value;
            cell.appendChild(badge);
            row.appendChild(cell);
        }

        function addTimeCell(row, event) {
            var cell = document.createElement('td');
            cell.className = 'logging-time';
            var link = document.createElement('a');
            var timestamp = event && event.timestamp ? new Date(event.timestamp) : null;
            link.textContent = timestamp && !Number.isNaN(timestamp.getTime())
                ? timestamp.toLocaleString()
                : (event.timestamp || '—');
            if (detailUrlTemplate && event && event.id) {
                link.href = detailUrlTemplate.replace(uuidPlaceholder, encodeURIComponent(event.id));
            } else {
                link.href = '#';
                link.addEventListener('click', function (e) { e.preventDefault(); });
            }
            cell.appendChild(link);
            row.appendChild(cell);
        }

        function addSourceCell(row, event) {
            var cell = document.createElement('td');
            cell.className = 'logging-source';
            var source = document.createElement('span');
            source.textContent = event.source || '—';
            cell.appendChild(source);
            if (event.category || event.action) {
                var secondary = document.createElement('span');
                secondary.className = 'logging-table__secondary';
                secondary.textContent = [event.category, event.action].filter(Boolean).join(' · ');
                cell.appendChild(secondary);
            }
            row.appendChild(cell);
        }

        function renderEvents(events) {
            if (!tbody) return;
            while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

            if (!events.length) {
                var empty = document.createElement('tr');
                var emptyCell = document.createElement('td');
                emptyCell.colSpan = 6;
                emptyCell.textContent = 'No log events.';
                empty.appendChild(emptyCell);
                tbody.appendChild(empty);
                return;
            }

            events.forEach(function (event) {
                var row = document.createElement('tr');
                row.className = 'logging-event-row logging-event-row--' + severityClass(event.severity);
                addTimeCell(row, event);
                addSeverityCell(row, event.severity);
                addSourceCell(row, event);
                addCell(row, event.traffic_type);
                addCell(row, event.message, 'log-message');
                addCell(row, event.request_path);
                tbody.appendChild(row);
            });
        }

        function refresh() {
            if (!feedUrl || !tbody) return;
            fetch(feedUrl, {
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                cache: 'no-store'
            })
                .then(function (response) { return response.ok ? response.json() : null; })
                .then(function (payload) {
                    if (!payload || !Array.isArray(payload.events)) return;
                    renderEvents(payload.events);
                })
                .catch(function () {});
        }

        function schedule() {
            if (timer) window.clearInterval(timer);
            timer = toggle.checked ? window.setInterval(refresh, refreshSeconds * 1000) : null;
        }

        toggle.addEventListener('change', schedule);
        schedule();
    }

    function boot() {
        initCopyButtons();
        initAutoRefresh();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
        boot();
    }
}());
