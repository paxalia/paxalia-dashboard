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

    function initLiveConsole() {
        var root = document.querySelector('[data-live-log-console]');
        if (!root) return;

        var feedUrl = root.getAttribute('data-live-feed-url');
        var limit = Math.max(1, Math.min(2000, parseInt(root.getAttribute('data-live-limit') || '2000', 10)));
        var viewport = root.querySelector('[data-live-viewport]');
        var linesEl = root.querySelector('[data-live-lines]');
        var emptyEl = root.querySelector('[data-live-empty]');
        var statusEl = root.querySelector('[data-live-status]');
        var statusDot = root.querySelector('[data-live-status-dot]');
        var countEl = root.querySelector('[data-live-count]');
        var levelEl = root.querySelector('[data-live-level]');
        var searchEl = root.querySelector('[data-live-search]');
        var followEl = root.querySelector('[data-live-follow]');
        var enabledEl = root.querySelector('[data-live-enabled]');
        var clearEl = root.querySelector('[data-live-clear]');

        var entries = [];
        var latestSequence = null;
        var timer = null;
        var inFlight = false;
        var pollMs = 1000;
        var levelRank = {DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50};

        function setStatus(text, state) {
            if (statusEl) statusEl.textContent = text;
            if (statusDot) statusDot.dataset.state = state || 'idle';
        }

        function activeLevel(entry) {
            var selected = levelEl ? levelEl.value : 'ALL';
            return selected === 'ALL' || String(entry.level) === selected;
        }

        function matchesSearch(entry) {
            var needle = searchEl ? String(searchEl.value || '').trim().toLowerCase() : '';
            if (!needle) return true;
            return String(entry.text || '').toLowerCase().indexOf(needle) !== -1 ||
                String(entry.logger || '').toLowerCase().indexOf(needle) !== -1;
        }

        function visibleEntries() {
            return entries.filter(function (entry) {
                return activeLevel(entry) && matchesSearch(entry);
            });
        }

        function render() {
            if (!linesEl) return;
            var visible = visibleEntries();
            while (linesEl.firstChild) linesEl.removeChild(linesEl.firstChild);

            if (emptyEl) emptyEl.hidden = visible.length > 0;
            if (countEl) countEl.textContent = visible.length + ' lines';

            visible.forEach(function (entry) {
                var row = document.createElement('div');
                row.className = 'live-log-line live-log-line--' + String(entry.level || 'INFO').toLowerCase();

                var time = document.createElement('span');
                time.className = 'live-log-line__time';
                var date = new Date((Number(entry.timestamp) || 0) * 1000);
                time.textContent = Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString();

                var text = document.createElement('span');
                text.className = 'live-log-line__text';
                text.textContent = String(entry.text || '');

                row.appendChild(time);
                row.appendChild(text);
                linesEl.appendChild(row);
            });

            if (followEl && followEl.checked && viewport) {
                viewport.scrollTop = viewport.scrollHeight;
            }
        }

        function merge(payload) {
            if (!payload || !Array.isArray(payload.entries)) return;
            if (payload.reset) entries = [];

            var incoming = payload.entries;
            if (incoming.length) {
                var seen = {};
                entries.forEach(function (entry) { seen[String(entry.sequence)] = true; });
                incoming.forEach(function (entry) {
                    if (!seen[String(entry.sequence)]) {
                        entries.push(entry);
                        seen[String(entry.sequence)] = true;
                    }
                });
                entries.sort(function (a, b) { return Number(a.sequence || 0) - Number(b.sequence || 0); });
                if (entries.length > limit) entries = entries.slice(-limit);
            }
            if (payload.latest_sequence != null) latestSequence = Number(payload.latest_sequence);
            render();
        }

        function fetchLogs(initial) {
            if (!feedUrl || inFlight || !enabledEl || !enabledEl.checked) return;
            inFlight = true;
            var url = feedUrl + (feedUrl.indexOf('?') === -1 ? '?' : '&');
            url += 'limit=' + encodeURIComponent(limit);
            if (!initial && latestSequence != null) {
                url += '&since=' + encodeURIComponent(latestSequence);
            }
            setStatus('Connecting…', 'connecting');
            fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                cache: 'no-store'
            })
                .then(function (response) {
                    if (!response.ok) throw new Error('Live log feed unavailable');
                    return response.json();
                })
                .then(function (payload) {
                    merge(payload);
                    setStatus('Live', 'live');
                })
                .catch(function () {
                    setStatus('Connection unavailable', 'error');
                })
                .finally(function () {
                    inFlight = false;
                });
        }

        function stop() {
            if (timer) {
                window.clearInterval(timer);
                timer = null;
            }
        }

        function start(initial) {
            stop();
            if (!enabledEl || !enabledEl.checked || document.hidden) return;
            fetchLogs(initial);
            timer = window.setInterval(function () { fetchLogs(false); }, pollMs);
        }

        function clearView() {
            entries = [];
            render();
            if (latestSequence == null) {
                start(true);
            } else {
                fetchLogs(false);
            }
        }

        if (levelEl) levelEl.addEventListener('change', render);
        if (searchEl) searchEl.addEventListener('input', render);
        if (clearEl) clearEl.addEventListener('click', clearView);
        if (followEl) followEl.addEventListener('change', function () {
            if (followEl.checked && viewport) viewport.scrollTop = viewport.scrollHeight;
        });
        if (enabledEl) enabledEl.addEventListener('change', function () {
            if (enabledEl.checked) {
                setStatus('Connecting…', 'connecting');
                start(latestSequence == null);
            } else {
                stop();
                setStatus('Paused', 'paused');
            }
        });
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) {
                stop();
            } else if (enabledEl && enabledEl.checked) {
                start(latestSequence == null);
            }
        });

        start(true);
    }

    function boot() {
        initCopyButtons();
        initAutoRefresh();
        initLiveConsole();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
        boot();
    }
}());
