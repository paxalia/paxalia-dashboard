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

    // ─── Automatic outbound-link & file-download tracking ────────
    // Config: add/remove extensions as needed before this script loads:
    //   window.opAnalyticsDownloadExtensions = ['pdf', 'zip', ...]
    var DOWNLOAD_EXTENSIONS = window.opAnalyticsDownloadExtensions || [
        'pdf', 'zip', 'rar', '7z', 'tar', 'gz',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'mp3', 'mp4', 'mov', 'avi', 'csv', 'txt', 'dmg', 'exe'
    ];

    function getExtension(pathname) {
        var match = /\.([a-z0-9]+)$/i.exec(pathname);
        return match ? match[1].toLowerCase() : '';
    }

    document.addEventListener('click', function(e) {
        var link = e.target.closest('a[href]');
        if (!link) return;
        var href = link.getAttribute('href');
        if (!href || href.indexOf('#') === 0 || href.indexOf('javascript:') === 0) return;

        var url;
        try {
            url = new URL(href, window.location.href);
        } catch (err) {
            return;
        }

        var ext = getExtension(url.pathname);
        if (DOWNLOAD_EXTENSIONS.indexOf(ext) !== -1) {
            window.opAnalytics('download', 'click', url.href);
        } else if (url.hostname && url.hostname !== window.location.hostname) {
            window.opAnalytics('outbound_link', 'click', url.href);
        }
    }, true);

    // ─── Scroll-depth tracking ─────────────────────────────────
    // Fires once per threshold per page load (25/50/75/100%).
    var scrollThresholds = [25, 50, 75, 100];
    var scrollFired = {};
    var scrollTicking = false;

    function checkScrollDepth() {
        scrollTicking = false;
        var scrollTop = window.scrollY || document.documentElement.scrollTop;
        var docHeight = Math.max(
            document.documentElement.scrollHeight, document.body.scrollHeight
        ) - window.innerHeight;
        if (docHeight <= 0) return;
        var pct = Math.min(100, Math.round((scrollTop / docHeight) * 100));

        scrollThresholds.forEach(function(threshold) {
            if (pct >= threshold && !scrollFired[threshold]) {
                scrollFired[threshold] = true;
                window.opAnalytics('engagement', 'scroll_depth', threshold + '%');
            }
        });
    }

    window.addEventListener('scroll', function() {
        if (!scrollTicking) {
            scrollTicking = true;
            window.requestAnimationFrame(checkScrollDepth);
        }
    }, { passive: true });

    // ─── Time-on-page tracking ─────────────────────────────────
    // Sent via sendBeacon (not fetch) on unload/tab-hide, since a
    // regular fetch() call is not guaranteed to complete once the page
    // is being torn down.
    var pageLoadTime = Date.now();
    var engagementSent = false;

    function sendEngagementBeacon() {
        if (engagementSent) return;
        engagementSent = true;
        var seconds = Math.round((Date.now() - pageLoadTime) / 1000);
        if (seconds < 1) return;

        var payload = JSON.stringify({
            category: 'engagement',
            action: 'time_on_page',
            path: window.location.pathname,
            value: seconds
        });
        if (navigator.sendBeacon) {
            var blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon(EVENT_URL, blob);
        }
    }

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            sendEngagementBeacon();
        }
    });
    window.addEventListener('pagehide', sendEngagementBeacon);
})();