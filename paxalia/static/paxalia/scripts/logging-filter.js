/* Paxalia logging filters: preserves the existing filter-bar visual system. */
(function () {
    'use strict';

    function formatDate(date) {
        var y = date.getFullYear();
        var m = String(date.getMonth() + 1).padStart(2, '0');
        var d = String(date.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }

    function shiftDays(days) {
        var d = new Date();
        d.setHours(0, 0, 0, 0);
        d.setDate(d.getDate() + days);
        return d;
    }

    function ranges(preset) {
        var today = shiftDays(0);
        var start;
        var end;
        switch (preset) {
            case 'today':
                start = end = today;
                break;
            case 'yesterday':
                start = end = shiftDays(-1);
                break;
            case 'last7':
                start = shiftDays(-6);
                end = today;
                break;
            case 'last30':
                start = shiftDays(-29);
                end = today;
                break;
            case 'this_month':
                start = new Date(today.getFullYear(), today.getMonth(), 1);
                end = today;
                break;
            default:
                return null;
        }
        return { start: formatDate(start), end: formatDate(end) };
    }

    function initFilter(root) {
        var form = root.closest('form');
        if (!form) return;
        var start = root.querySelector('input[name="start_date"]');
        var end = root.querySelector('input[name="end_date"]');
        var presets = root.querySelectorAll('[data-preset]');
        var active = root.getAttribute('data-active-preset') || '';

        presets.forEach(function (button) {
            var isActive = button.getAttribute('data-preset') === active;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            button.addEventListener('click', function () {
                var range = ranges(button.getAttribute('data-preset'));
                if (!range || !start || !end) return;
                start.value = range.start;
                end.value = range.end;
                form.requestSubmit ? form.requestSubmit() : form.submit();
            });
        });

        form.addEventListener('submit', function () {
            var page = form.querySelector('input[name="page"]');
            if (page) page.remove();
        });
    }

    function boot() {
        document.querySelectorAll('[data-logging-filter]').forEach(initFilter);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
        boot();
    }
})();
