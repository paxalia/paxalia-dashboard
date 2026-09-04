// analytics/static/analytics/scripts/security.js

document.addEventListener('DOMContentLoaded', function () {
    // Shared confirm-before-submit handler (same convention as backups.js)
    document.querySelectorAll('[data-confirm]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    var tabs = document.querySelectorAll('.security-tab');
    var panels = document.querySelectorAll('.security-panel');

    function activate(tabName) {
        tabs.forEach(function (tab) {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        panels.forEach(function (panel) {
            panel.hidden = panel.dataset.panel !== tabName;
        });
        if (window.history && window.history.replaceState) {
            var url = new URL(window.location.href);
            url.hash = tabName;
            window.history.replaceState(null, '', url);
        }
    }

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            activate(tab.dataset.tab);
        });
    });

    var initial = (window.location.hash || '').replace('#', '');
    var validTabs = Array.prototype.map.call(tabs, function (t) { return t.dataset.tab; });
    if (initial && validTabs.indexOf(initial) !== -1) {
        activate(initial);
    }
});
