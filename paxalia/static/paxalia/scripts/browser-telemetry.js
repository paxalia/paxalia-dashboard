/* Paxalia Browser Telemetry — bounded client failure diagnostics.
 *
 * This is technical observability only. It does not record dashboard clicks,
 * form values, query-string URLs, cookies, or credentials. Feature-specific
 * clients (Transfer Center/Auth) may emit their own lifecycle events; this
 * collector focuses on uncaught browser failures and avoids duplicating those
 * events when the existing full browser logger is present.
 */
(function () {
    'use strict';

    if (window.__paxaliaBrowserTelemetryInitialized) return;
    window.__paxaliaBrowserTelemetryInitialized = true;

    var body = document.body;
    if (!body || body.getAttribute('data-paxalia-telemetry-enabled') !== '1') return;

    var endpoint = body.getAttribute('data-paxalia-telemetry-url') || '';
    if (!endpoint || typeof window.fetch !== 'function') return;

    var captureResourceErrors = body.getAttribute('data-paxalia-telemetry-resource-errors') === '1';
    var maxEvents = Math.max(1, Math.min(50, Number(body.getAttribute('data-paxalia-telemetry-max-events') || 50)));
    var seen = Object.create(null);
    var emitted = 0;


    function bounded(value, max) {
        return String(value || '').slice(0, max);
    }

    function safePath(value) {
        var text = bounded(value, 500);
        return text.split('#', 1)[0].split('?', 1)[0];
    }

    function safeMessage(value) {
        var text = bounded(value, 1000);
        // Remove common inline credential/query forms before transmission. The
        // server performs its own central redaction as a second boundary.
        return text
            .replace(/([?&](?:token|code|secret|password|passwd|authorization|api[_-]?key|access[_-]?token|refresh[_-]?token)=)[^&\s]*/ig, '$1[REDACTED]')
            .replace(/\b(Bearer\s+)[A-Za-z0-9._~+/=-]+/ig, '$1[REDACTED]')
            .replace(/\b(password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^,;\s]+/ig, '$1:[REDACTED]');
    }

    function safeFilename(value) {
        var text = bounded(value, 500);
        return safePath(text);
    }

    function stableKey(kind, message, filename, line, col) {
        return [kind, message, filename, line || '', col || ''].join('|').slice(0, 1800);
    }

    function emit(kind, severity, message, details) {
        if (emitted >= maxEvents) return;
        var info = details || {};
        var safeMessageValue = safeMessage(message);
        var key = stableKey(kind, safeMessageValue, safeFilename(info.filename), info.lineno, info.colno);
        if (seen[key]) return;
        seen[key] = true;
        emitted += 1;

        var metadata = {};
        if (info.category) metadata.category = bounded(info.category, 80);
        if (info.resourceType) metadata.resource_type = bounded(info.resourceType, 40);
        if (info.status !== undefined && info.status !== null) metadata.http_status = Number(info.status) || 0;
        if (info.promiseType) metadata.promise_type = bounded(info.promiseType, 80);

        var payload = {
            kind: kind,
            severity: severity,
            message: safeMessageValue,
            filename: safeFilename(info.filename),
            lineno: Number(info.lineno) || null,
            colno: Number(info.colno) || null,
            stack: bounded(info.stack, 4000),
            path: safePath(window.location.pathname),
            metadata: metadata
        };

        try {
            window.fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                keepalive: true,
                cache: 'no-store'
            }).catch(function () {});
        } catch (error) {
            // Telemetry must never interfere with the application.
        }
    }

    window.addEventListener('error', function (event) {
        // A resource load failure has an Element target and usually no JS error
        // object. Keep it as a bounded resource diagnostic instead of inventing
        // a URL that might contain a secret query string.
        var target = event && event.target;
        if (target && target !== window && target.tagName && captureResourceErrors) {
            var resourceUrl = target.currentSrc || target.src || target.href || '';
            emit('resource', 'ERROR', 'Dashboard resource failed to load.', {
                filename: resourceUrl,
                resourceType: String(target.tagName || '').toLowerCase(),
                status: 0,
                category: 'resource'
            });
            return;
        }

        var error = event && event.error;
        emit('error', 'ERROR', error && error.message ? error.message : (event && event.message) || 'Unhandled dashboard JavaScript error.', {
            filename: event && event.filename,
            lineno: event && event.lineno,
            colno: event && event.colno,
            stack: error && error.stack,
            category: 'javascript'
        });
    }, true);

    window.addEventListener('unhandledrejection', function (event) {
        var reason = event && event.reason;
        var message = reason && reason.message ? reason.message : String(reason || 'Unhandled dashboard promise rejection.');
        emit('rejection', 'ERROR', message, {
            stack: reason && reason.stack,
            category: 'promise',
            promiseType: reason && reason.name
        });
    });

})();
