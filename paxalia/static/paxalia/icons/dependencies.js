/* Paxalia Dashboard — progressive dependency health checks. */
(function () {
    'use strict';

    function init() {
        const page = document.querySelector('.dependencies-page');
        const table = document.getElementById('dependencyTable');
        const refresh = document.getElementById('dependencyRefresh');
        const checks = document.getElementById('dependencyChecks');
        const state = document.getElementById('dependencyCheckState');
        const progress = document.getElementById('dependencyProgressBar');

        if (!page || !table || !checks || !state || !progress) return;

        const rows = Array.from(table.querySelectorAll('tbody tr[data-package]'));
        const template = page.dataset.statusUrlTemplate || '';
        if (!rows.length || !template) {
            state.textContent = 'No dependency checks are available.';
            return;
        }

        let running = false;
        let cancelled = false;

        function setText(element, value) {
            if (element) element.textContent = value;
        }

        function replaceWithText(parent, tag, value, className) {
            if (!parent) return;
            const element = document.createElement(tag);
            element.textContent = value;
            if (className) element.className = className;
            parent.replaceChildren(element);
        }

        function setStatus(row, status, sourceLabel) {
            const cell = row.querySelector('.dependency-status');
            const latestSource = row.querySelector('.dependency-latest-source');
            if (!cell) return;

            row.classList.remove(
                'dependency-row-current',
                'dependency-row-update',
                'dependency-row-missing',
                'dependency-row-error'
            );

            let label = 'Check unavailable';
            let className = 'status-pill status-pill--danger';

            if (status === 'current') {
                label = 'Current';
                className = 'status-pill status-pill--success';
                row.classList.add('dependency-row-current');
            } else if (status === 'update') {
                label = 'Update available';
                className = 'status-pill status-pill--warning';
                row.classList.add('dependency-row-update');
            } else if (status === 'missing') {
                label = 'Missing';
                className = 'status-pill status-pill--danger';
                row.classList.add('dependency-row-missing');
            } else {
                row.classList.add('dependency-row-error');
            }

            replaceWithText(cell, 'span', label, className);

            if (latestSource) {
                replaceWithText(
                    latestSource,
                    'span',
                    sourceLabel || (status === 'unavailable' ? 'PyPI unavailable' : 'PyPI'),
                    'dependency-source ' + (status === 'unavailable'
                        ? 'dependency-source--pending'
                        : 'dependency-source--pypi')
                );
            }
        }

        async function checkRow(row) {
            const name = row.dataset.package || '';
            const url = template.replace('PACKAGE_NAME', encodeURIComponent(name));
            const latest = row.querySelector('.dependency-latest');
            const status = row.querySelector('.dependency-status');
            const source = row.querySelector('.dependency-latest-source');

            if (!latest || !status || !source) return;

            replaceWithText(latest, 'span', 'Checking…', 'dependency-pending');
            replaceWithText(status, 'span', 'Checking', 'status-pill status-pill--neutral');
            replaceWithText(source, 'span', 'PyPI', 'dependency-source dependency-source--pending');

            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => controller.abort(), 8000);

            try {
                const response = await fetch(url, {
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    cache: 'no-store',
                    signal: controller.signal,
                });

                const contentType = response.headers.get('content-type') || '';
                if (!response.ok) {
                    throw new Error('Status endpoint returned HTTP ' + response.status);
                }
                if (!contentType.includes('application/json')) {
                    throw new Error('Status endpoint returned a non-JSON response');
                }

                const data = await response.json();

                if (data.latest) {
                    replaceWithText(latest, 'code', data.latest);
                } else if (data.status === 'missing') {
                    replaceWithText(latest, 'span', 'Not installed', 'dependency-check-fail');
                } else {
                    replaceWithText(latest, 'span', 'Unavailable', 'dependency-check-fail');
                }

                setStatus(row, data.status, data.source_status === 'unavailable'
                    ? 'PyPI unavailable'
                    : (data.source || 'PyPI'));
            } catch (error) {
                const message = error && error.name === 'AbortError'
                    ? 'PyPI check timed out'
                    : 'PyPI unavailable';

                replaceWithText(latest, 'span', message, 'dependency-check-fail');
                setStatus(row, 'unavailable', message);
            } finally {
                window.clearTimeout(timeoutId);
            }
        }

        async function run() {
            if (running) return;
            running = true;
            cancelled = false;

            if (refresh) refresh.disabled = true;
            setText(checks, '0');
            progress.style.width = '0%';
            setText(state, 'Checking one package at a time…');

            for (let index = 0; index < rows.length; index += 1) {
                if (cancelled) break;
                await checkRow(rows[index]);
                const completed = index + 1;
                setText(checks, String(completed));
                progress.style.width = ((completed / rows.length) * 100) + '%';
            }

            if (cancelled) {
                setText(state, 'Release checks stopped.');
            } else {
                setText(state, 'All release checks completed');
            }

            running = false;
            if (refresh) refresh.disabled = false;
        }

        if (refresh) refresh.addEventListener('click', run);
        run();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
