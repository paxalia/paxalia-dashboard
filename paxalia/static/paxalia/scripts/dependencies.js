/* Paxalia Dashboard — progressive dependency checks */
(function () {
    const page = document.querySelector('.dependencies-page');
    const table = document.getElementById('dependencyTable');
    const refresh = document.getElementById('dependencyRefresh');
    const checks = document.getElementById('dependencyChecks');
    const state = document.getElementById('dependencyCheckState');
    const progress = document.getElementById('dependencyProgressBar');
    if (!page || !table || !checks || !state || !progress) return;

    const rows = Array.from(table.querySelectorAll('tbody tr[data-package]'));
    const template = page.dataset.statusUrlTemplate || '';
    let stopped = false;

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }

    function setStatus(row, status) {
        const cell = row.querySelector('.dependency-status');
        const latest = row.querySelector('.dependency-latest');
        const source = row.querySelector('.dependency-latest-source');
        if (status === 'current') {
            cell.innerHTML = '<span class="status-pill status-pill--success">Current</span>';
            row.classList.add('dependency-row-current');
        } else if (status === 'update') {
            cell.innerHTML = '<span class="status-pill status-pill--warning">Update available</span>';
            row.classList.add('dependency-row-update');
        } else if (status === 'missing') {
            cell.innerHTML = '<span class="status-pill status-pill--danger">Missing</span>';
            latest.innerHTML = '<span class="dependency-check-fail">Not installed</span>';
            row.classList.add('dependency-row-missing');
        } else {
            cell.innerHTML = '<span class="status-pill status-pill--danger">Check unavailable</span>';
            row.classList.add('dependency-row-error');
        }
        if (source && status !== 'missing') {
            source.innerHTML = '<span class="dependency-source dependency-source--pypi">' + (row.dataset.latestSource || 'PyPI') + '</span>';
        }
    }

    async function checkRow(row) {
        const name = row.dataset.package;
        const url = template.replace('PACKAGE_NAME', encodeURIComponent(name));
        row.classList.remove('dependency-row-current','dependency-row-update','dependency-row-missing','dependency-row-error');
        row.querySelector('.dependency-latest').innerHTML = '<span class="dependency-pending"><span class="dependency-spinner"></span>Checking…</span>';
        row.querySelector('.dependency-status').innerHTML = '<span class="status-pill status-pill--neutral">Checking</span>';
        row.querySelector('.dependency-latest-source').innerHTML = '<span class="dependency-source dependency-source--pending">Pending</span>';
        try {
            const response = await fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'}, cache:'no-store'});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Check failed');
            const latest = row.querySelector('.dependency-latest');
            latest.innerHTML = data.latest ? '<code>' + escapeHtml(data.latest) + '</code>' : '<span class="dependency-check-fail">Unavailable</span>';
            if (data.source) row.dataset.latestSource = data.source;
            setStatus(row, data.status);
        } catch (error) {
            row.querySelector('.dependency-latest').innerHTML = '<span class="dependency-check-fail">Unavailable</span>';
            row.dataset.latestSource = '';
            setStatus(row, 'unavailable');
        }
    }

    async function run() {
        if (stopped) return;
        stopped = false;
        refresh.disabled = true;
        checks.textContent = '0';
        progress.style.width = '0%';
        state.textContent = 'Checking one package at a time…';
        for (let i = 0; i < rows.length; i += 1) {
            if (stopped) break;
            await checkRow(rows[i]);
            checks.textContent = String(i + 1);
            progress.style.width = (((i + 1) / rows.length) * 100) + '%';
        }
        refresh.disabled = false;
        if (!stopped) state.textContent = 'All release checks completed';
    }

    refresh?.addEventListener('click', run);
    run();
})();
