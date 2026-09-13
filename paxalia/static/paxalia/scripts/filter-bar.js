/* filter-bar.js – date range filter & path search */

(function() {
    const data = window.__analytics_filter;
    if (!data) return;

    const startInput = document.getElementById('start_date');
    const endInput = document.getElementById('end_date');
    const applyBtn = document.getElementById('apply-filter');
    const searchInput = document.getElementById('path_search');
    const presetButtons = document.querySelectorAll('[data-preset]');

    // Helper: format date object to YYYY-MM-DD
    function formatDate(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function getToday() { return new Date(); }
    function daysAgo(n) {
        const d = new Date();
        d.setDate(d.getDate() - n);
        return d;
    }

    // Set active class on preset buttons based on activePreset
    if (data.activePreset && presetButtons.length > 0) {
        presetButtons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.preset === data.activePreset) {
                btn.classList.add('active');
            }
        });
    }

    // Set initial date values
    if (startInput && data.startDate) startInput.value = data.startDate;
    if (endInput && data.endDate) endInput.value = data.endDate;

    // Apply filter by reloading with query params
    function applyFilter() {
        const params = new URLSearchParams(window.location.search);
        if (startInput && startInput.value) params.set('start_date', startInput.value);
        else params.delete('start_date');
        if (endInput && endInput.value) params.set('end_date', endInput.value);
        else params.delete('end_date');
        if (searchInput && searchInput.value) params.set('path', searchInput.value);
        else params.delete('path');
        window.location.search = params.toString();
    }

    // Preset button click: set dates, update active class, auto-apply
    presetButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const preset = this.dataset.preset;
            let start, end;
            switch(preset) {
                case 'today':
                    start = end = formatDate(getToday());
                    break;
                case 'yesterday':
                    start = end = formatDate(daysAgo(1));
                    break;
                case 'last7':
                    start = formatDate(daysAgo(6));
                    end = formatDate(getToday());
                    break;
                case 'last30':
                    start = formatDate(daysAgo(29));
                    end = formatDate(getToday());
                    break;
                case 'this_month':
                    const now = new Date();
                    start = formatDate(new Date(now.getFullYear(), now.getMonth(), 1));
                    end = formatDate(getToday());
                    break;
                default:
                    return;
            }
            if (startInput && endInput) {
                startInput.value = start;
                endInput.value = end;
            }
            // Update active preset visual
            presetButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            applyFilter();
        });
    });

    // Apply button click
    if (applyBtn) {
        applyBtn.addEventListener('click', applyFilter);
    }

    // Search input Enter key
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                applyFilter();
            }
        });
    }
})();