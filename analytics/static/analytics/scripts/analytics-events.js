(function() {
    if (typeof window.opAnalytics !== 'undefined') return;

    window.opAnalytics = function(category, action, label, value) {
        var payload = {
            category: category,
            action: action,
            path: window.location.pathname
        };
        if (label !== undefined) payload.label = label;
        if (value !== undefined) payload.value = value;

        fetch('insights/api/event/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).catch(function() {});
    };
})();