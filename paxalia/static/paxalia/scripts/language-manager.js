(function () {
    'use strict';

    const ENDPOINT = '/i18n/setlang/';

    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') || '' : '';
    }

    function currentLocation() {
        return window.location.pathname + window.location.search + window.location.hash;
    }

    function applyLanguage(lang) {
        if (!lang) return;
        const form = document.createElement('form');
        form.method = 'post';
        form.action = ENDPOINT;
        form.style.display = 'none';

        const csrf = document.createElement('input');
        csrf.type = 'hidden';
        csrf.name = 'csrfmiddlewaretoken';
        csrf.value = getCSRFToken();
        form.appendChild(csrf);

        const language = document.createElement('input');
        language.type = 'hidden';
        language.name = 'language';
        language.value = lang;
        form.appendChild(language);

        const next = document.createElement('input');
        next.type = 'hidden';
        next.name = 'next';
        next.value = currentLocation();
        form.appendChild(next);

        document.body.appendChild(form);
        form.submit();
    }

    function init() {
        document.querySelectorAll('#lang-selector-menu [data-lang]').forEach((item) => {
            item.setAttribute('tabindex', '0');
            item.addEventListener('click', function (event) {
                event.preventDefault();
                applyLanguage(item.dataset.lang);
            });
            item.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    applyLanguage(item.dataset.lang);
                }
            });
        });

        const current = document.documentElement.lang || 'en';
        const display = document.getElementById('lang-selector-value');
        const active = Array.from(document.querySelectorAll('#lang-selector-menu [data-lang]')).find(
            (item) => item.dataset.lang === current
        );
        if (display && active) display.textContent = active.textContent.trim();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
}());
