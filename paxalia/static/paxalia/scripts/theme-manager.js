(function () {
    'use strict';

    const ATTR = 'data-analytics-theme';
    const STORAGE = 'paxalia-theme';
    const DEFAULT = 'dark';
    const KNOWN_THEMES = new Set([
        'dark', 'default', 'golden', 'azure', 'sunlit', 'indigo',
        'arctic', 'ocean', 'twilight', 'velvet', 'citrine', 'amethyst', 'onyx'
    ]);

    function themeItems() {
        return Array.from(document.querySelectorAll('#theme-selector-menu [data-theme]'));
    }

    function getDisplayName(slug) {
        const item = themeItems().find((node) => node.dataset.theme === slug);
        return item ? item.textContent.trim() : slug;
    }

    function updateDisplay(slug) {
        const value = document.getElementById('theme-selector-value');
        if (value) value.textContent = getDisplayName(slug);
        themeItems().forEach((item) => {
            const selected = item.dataset.theme === slug;
            item.setAttribute('aria-checked', selected ? 'true' : 'false');
            item.classList.toggle('is-selected', selected);
        });
    }

    function validTheme(slug) {
        return KNOWN_THEMES.has(slug) || themeItems().some((item) => item.dataset.theme === slug);
    }

    function applyTheme(slug, persist) {
        const next = validTheme(slug) ? slug : DEFAULT;
        document.documentElement.setAttribute(ATTR, next);
        if (persist !== false) {
            try { localStorage.setItem(STORAGE, next); } catch (error) { /* storage is optional */ }
        }
        updateDisplay(next);
        return next;
    }

    function init() {
        let saved = null;
        try { saved = localStorage.getItem(STORAGE); } catch (error) { saved = null; }
        const initial = saved || document.documentElement.getAttribute(ATTR) || DEFAULT;
        applyTheme(initial, false);

        themeItems().forEach((item) => {
            item.setAttribute('aria-checked', 'false');
            item.addEventListener('click', function (event) {
                event.preventDefault();
                applyTheme(item.dataset.theme, true);
            });
            item.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    applyTheme(item.dataset.theme, true);
                }
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
}());
