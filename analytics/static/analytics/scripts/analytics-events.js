// static/analytics/scripts/analytics-events.js

(function() {
    'use strict';

    if (typeof window.opAnalytics !== 'undefined') {
        return;
    }

    var EVENT_URL = '/api/analytics/event/';

    // ─── Get CSRF token from cookie ──────────────────────────────
    function getCsrfToken() {
        var cookieValue = null;
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.startsWith('csrftoken=')) {
                cookieValue = cookie.substring('csrftoken='.length);
                break;
            }
        }
        return cookieValue;
    }

    window.opAnalytics = function(category, action, label, value) {
        var payload = {
            category: category,
            action: action,
            path: window.location.pathname
        };
        if (label !== undefined && label !== null && label !== '') {
            payload.label = label;
        }
        if (value !== undefined && value !== null) {
            payload.value = parseFloat(value); // ensure number
        }

        var headers = {
            'Content-Type': 'application/json'
        };
        var csrfToken = getCsrfToken();
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        fetch(EVENT_URL, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        })
        .then(function(response) {
            if (!response.ok) {
                return response.text().then(function(text) {
                    console.warn('[Analytics] Error response:', text);
                });
            }
        })
        .catch(function() { /* silent fail */ });
    };

    // ─── Global click listener ──────────────────────────────────
    document.addEventListener('click', function(e) {
        var el = e.target.closest('[data-analytics-category]');
        if (!el) return;
        var category = el.getAttribute('data-analytics-category');
        var action = el.getAttribute('data-analytics-action') || 'click';
        var label = el.getAttribute('data-analytics-label') || undefined;
        var value = el.getAttribute('data-analytics-value');
        window.opAnalytics(category, action, label, value);
    }, true);
})();