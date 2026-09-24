(function () {
    'use strict';

    function init() {
        var body = document.body;
        if (!body) return;

        var home = body.getAttribute('data-error-home-url') || '/';
        var homeLinks = document.querySelectorAll('[data-error-home]');
        homeLinks.forEach(function (link) {
            link.setAttribute('href', home);
        });

        document.querySelectorAll('[data-error-action]').forEach(function (button) {
            button.addEventListener('click', function () {
                var action = button.getAttribute('data-error-action');
                if (action === 'back' && window.history.length > 1) {
                    window.history.back();
                    return;
                }
                if (action === 'reload') {
                    window.location.reload();
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
