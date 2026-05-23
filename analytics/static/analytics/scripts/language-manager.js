(function() {
    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function applyLanguage(lang) {
        const formBody = `language=${encodeURIComponent(lang)}&next=${encodeURIComponent(window.location.pathname)}`;
        fetch('/i18n/setlang/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCSRFToken(),
            },
            body: formBody,
        }).then(response => {
            if (response.ok) window.location.reload();
        }).catch(err => console.error('Language switch failed', err));
    }

    document.querySelectorAll('#lang-selector-menu [data-lang]').forEach(item => {
        item.addEventListener('click', () => applyLanguage(item.dataset.lang));
    });

    // Set initial display from <html lang>
    const currentLang = document.documentElement.lang || 'en';
    const langItem = document.querySelector(`#lang-selector-menu [data-lang="${currentLang}"]`);
    const displayName = langItem ? langItem.textContent.trim() : currentLang;
    const displayEl = document.getElementById('lang-selector-value');
    if (displayEl) displayEl.textContent = displayName;
})();