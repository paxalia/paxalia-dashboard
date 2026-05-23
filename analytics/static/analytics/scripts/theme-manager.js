(function() {
    const ATTR = 'data-analytics-theme';
    const STORAGE = 'analytics-theme';
    const DEFAULT = 'dark';

    const themes = window.__analytics_themes || [
        { slug: 'dark', label: 'Dark Gold' },
        { slug: 'light', label: 'Light' },
        { slug: 'midnight', label: 'Midnight Blue' }
    ];

    function getDisplayName(slug) {
        const t = themes.find(t => t.slug === slug);
        return t ? t.label : slug;
    }

    function updateDisplay(slug) {
        const el = document.getElementById('theme-selector-value');
        if (el) el.textContent = getDisplayName(slug);
    }

    function applyTheme(slug) {
        document.documentElement.setAttribute(ATTR, slug);
        localStorage.setItem(STORAGE, slug);
        updateDisplay(slug);
    }

    function init() {
        const saved = localStorage.getItem(STORAGE);
        applyTheme(saved || DEFAULT);
    }

    document.querySelectorAll('#theme-selector-menu [data-theme]').forEach(item => {
        item.addEventListener('click', () => applyTheme(item.dataset.theme));
    });

    if (document.readyState === 'complete') init();
    else document.addEventListener('DOMContentLoaded', init);
})();