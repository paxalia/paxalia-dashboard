// static/analytics/scripts/analytics-events.js

(function() {
    'use strict';

    if (typeof window.opAnalytics !== 'undefined') {
        return;
    }

    var EVENT_URL = '/api/analytics/event/';

    // ─── Consent Mode (Phase 14) ─────────────────────────────────
    // window.PAXALIA_CONSENT_CONFIG is set by the
    // {% analytics_consent_config %} template tag — include it right
    // before this script tag. If it's missing, consent mode defaults
    // to disabled and tracking behaves exactly as it did before this
    // phase. See the README's "Consent Mode" section.
    var consentConfig = window.PAXALIA_CONSENT_CONFIG || { enabled: false };

    function hasConsent() {
        if (!consentConfig.enabled) return true;
        var prefix = consentConfig.cookieName + '=';
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(prefix) === 0) {
                return c.substring(prefix.length) === consentConfig.grantedValue;
            }
        }
        return false;
    }

    if (!hasConsent()) {
        // Consent not granted: define opAnalytics as a no-op so any
        // onclick="opAnalytics(...)" call sites elsewhere on the page
        // don't throw, but attach no listeners and send nothing. The
        // server independently enforces this too (AnalyticsMiddleware
        // and the event API endpoints) — this client-side gate is
        // about not even trying, not the actual compliance guarantee.
        window.opAnalytics = function() {};
        return;
    }

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

    // ─── Core Web Vitals (LCP, CLS, INP) ───────────────────────
    // Native PerformanceObserver only — no third-party web-vitals
    // library, to keep this dependency-free like the rest of the
    // package. See analytics/rum.py's module docstring for the
    // accuracy caveats on the CLS session-window and simplified INP
    // implementations below; the 75th-percentile aggregation that
    // Core Web Vitals reporting actually relies on happens
    // server-side, not here — this just measures one page load.
    if (window.PerformanceObserver) {
        var vitalsReported = {};

        function reportVital(metric, value) {
            if (vitalsReported[metric]) return;
            vitalsReported[metric] = true;
            var payload = JSON.stringify({
                category: 'web_vitals',
                action: metric,
                path: window.location.pathname,
                value: value
            });
            if (navigator.sendBeacon) {
                navigator.sendBeacon(EVENT_URL, new Blob([payload], { type: 'application/json' }));
            }
        }

        // LCP — track the latest candidate; the final value is only
        // known once nothing bigger paints before the page is hidden.
        var lcpValue = null;
        try {
            var lcpObserver = new PerformanceObserver(function(list) {
                var entries = list.getEntries();
                var last = entries[entries.length - 1];
                if (last) lcpValue = last.renderTime || last.loadTime || last.startTime;
            });
            lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
        } catch (err) { /* not supported in this browser */ }

        // CLS — session-windowed sum per the current official
        // algorithm: shifts less than 1s apart (session capped at 5s
        // total) are grouped into one session; CLS is the largest
        // session's total, not a running lifetime sum.
        var clsValue = 0;
        var clsSessionValue = 0;
        var clsSessionEntries = [];
        try {
            var clsObserver = new PerformanceObserver(function(list) {
                list.getEntries().forEach(function(entry) {
                    if (entry.hadRecentInput) return; // user-triggered, not a UX issue
                    var firstEntry = clsSessionEntries[0];
                    var lastEntry = clsSessionEntries[clsSessionEntries.length - 1];
                    if (
                        firstEntry &&
                        (entry.startTime - lastEntry.startTime) < 1000 &&
                        (entry.startTime - firstEntry.startTime) < 5000
                    ) {
                        clsSessionValue += entry.value;
                        clsSessionEntries.push(entry);
                    } else {
                        clsSessionValue = entry.value;
                        clsSessionEntries = [entry];
                    }
                    if (clsSessionValue > clsValue) clsValue = clsSessionValue;
                });
            });
            clsObserver.observe({ type: 'layout-shift', buffered: true });
        } catch (err) { /* not supported in this browser */ }

        // INP — simplified to the single worst interaction duration
        // observed. The full spec percentile-ranks across *all*
        // interactions for highly-interactive pages; this converges to
        // the same value for a typical page with a handful of
        // interactions and runs slightly pessimistic otherwise — see
        // rum.py's docstring.
        var inpValue = 0;
        var inpSeen = false;
        try {
            var inpObserver = new PerformanceObserver(function(list) {
                list.getEntries().forEach(function(entry) {
                    inpSeen = true;
                    if (entry.duration > inpValue) inpValue = entry.duration;
                });
            });
            inpObserver.observe({ type: 'event', buffered: true, durationThreshold: 40 });
        } catch (err) { /* not supported in this browser */ }

        function reportAllVitals() {
            if (lcpValue !== null) reportVital('LCP', Math.round(lcpValue));
            if (clsSessionEntries.length) reportVital('CLS', clsValue);
            if (inpSeen) reportVital('INP', Math.round(inpValue));
        }

        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'hidden') reportAllVitals();
        });
        window.addEventListener('pagehide', reportAllVitals);
    }

    // ─── JS error tracking ──────────────────────────────────────
    // Sent immediately via fetch(keepalive) rather than batched or
    // deferred to unload, since the page may keep running for a long
    // time after an error and a developer wants to know sooner.
    var JS_ERROR_URL = '/api/analytics/js-error/';
    var MAX_ERRORS_PER_PAGE = 10; // guard against a runaway error loop
    var errorsSentCount = 0;
    var errorsSeen = {}; // per-page-load dedup: same error firing on every
                          // animation frame shouldn't count as 10 reports

    function reportJsError(message, filename, lineno, colno, stack) {
        if (errorsSentCount >= MAX_ERRORS_PER_PAGE) return;
        var key = message + '|' + filename + '|' + lineno;
        if (errorsSeen[key]) return;
        errorsSeen[key] = true;
        errorsSentCount++;

        var payload = {
            message: String(message || 'Unknown error').slice(0, 500),
            filename: filename ? String(filename).slice(0, 500) : '',
            lineno: lineno || null,
            colno: colno || null,
            stack: stack ? String(stack).slice(0, 4000) : '',
            path: window.location.pathname
        };

        var headers = { 'Content-Type': 'application/json' };
        var csrfToken = getCsrfToken();
        if (csrfToken) headers['X-CSRFToken'] = csrfToken;

        fetch(JS_ERROR_URL, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload),
            keepalive: true
        }).catch(function() { /* silent fail */ });
    }

    window.addEventListener('error', function(e) {
        // Resource-load failures (an <img>/<script>/<link> failing to
        // load) also fire a window 'error' event, but with no message —
        // filter those out, this is for JS exceptions only.
        if (!e.message) return;
        reportJsError(e.message, e.filename, e.lineno, e.colno, e.error && e.error.stack);
    });

    window.addEventListener('unhandledrejection', function(e) {
        var reason = e.reason;
        var reasonMessage = reason && reason.message ? reason.message : String(reason);
        var stack = reason && reason.stack ? reason.stack : '';
        reportJsError('Unhandled promise rejection: ' + reasonMessage, '', null, null, stack);
    });
})();