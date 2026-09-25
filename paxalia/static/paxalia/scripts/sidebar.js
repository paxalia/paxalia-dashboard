/* Paxalia Dashboard sidebar controller. */
(function () {
    'use strict';

    function init() {
        const body = document.querySelector('.analytics-body');
        const sidebar = document.querySelector('.analytics-sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        const toggleBtn = document.querySelector('.sidebar-toggle');
        const closeBtn = document.querySelector('.analytics-sidebar-close-btn');
        const STORAGE_KEY = 'paxalia_sidebar_hidden';

        // Do not let an unrelated page script stop the rest of this file.
        if (!body || !sidebar) {
            return;
        }

        const isMobile = () => window.innerWidth < 768;
        const isHidden = () => body.classList.contains('sidebar-hidden');

        function openBackdrop() {
            if (!backdrop) return;
            backdrop.hidden = false;
            backdrop.classList.add('is-visible');
            document.body.classList.add('sidebar-backdrop-open');
        }

        function closeBackdrop() {
            if (!backdrop) return;
            backdrop.classList.remove('is-visible');
            backdrop.hidden = true;
            document.body.classList.remove('sidebar-backdrop-open');
        }

        function applyState(hidden, persist) {
            body.classList.toggle('sidebar-hidden', hidden);

            if (toggleBtn) {
                toggleBtn.setAttribute('aria-expanded', hidden ? 'false' : 'true');
                toggleBtn.setAttribute('aria-label', hidden ? 'Open sidebar' : 'Close sidebar');
            }

            if (isMobile() && !hidden) {
                openBackdrop();
            } else {
                closeBackdrop();
            }

            if (persist) {
                try {
                    localStorage.setItem(STORAGE_KEY, hidden ? 'true' : 'false');
                } catch (error) {
                    // Storage can be unavailable in privacy-restricted contexts.
                }
            }
        }

        function toggleSidebar(event) {
            if (event) event.preventDefault();
            applyState(!isHidden(), true);
        }

        if (toggleBtn) {
            toggleBtn.addEventListener('click', toggleSidebar);
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', function (event) {
                event.preventDefault();
                applyState(true, true);
            });
        }

        if (backdrop) {
            backdrop.addEventListener('click', function () {
                applyState(true, true);
            });
        }

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && isMobile() && !isHidden()) {
                applyState(true, true);
            }
        });

        window.addEventListener('resize', function () {
            if (isMobile()) {
                if (!isHidden()) openBackdrop();
            } else {
                closeBackdrop();
            }
        });

        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            // Desktop defaults to visible; mobile also starts visible unless
            // the user explicitly hid it previously.
            applyState(saved === 'true', false);
        } catch (error) {
            applyState(false, false);
        }

        // ----------------------------
        // CSP-safe auto-submit controls
        // ----------------------------
        document.querySelectorAll('[data-paxalia-auto-submit]').forEach(function (form) {
            const controls = form.querySelectorAll('select, input:not([type="hidden"]), textarea');
            controls.forEach(function (control) {
                control.addEventListener('change', function () {
                    form.requestSubmit();
                });
            });
        });
        document.querySelectorAll('[data-paxalia-auto-submit-control]').forEach(function (control) {
            if (control.dataset.paxaliaAutoSubmitBound === 'true') return;
            const form = control.form;
            if (!form) return;
            control.dataset.paxaliaAutoSubmitBound = 'true';
            control.addEventListener('change', function () {
                form.requestSubmit();
            });
        });

        // ----------------------------
        // Administrator account menu
        // ----------------------------
        const accountButton = document.querySelector('[data-sidebar-account-toggle]');
        const accountMenu = document.getElementById('sidebar-account-menu');

        function setAccountMenu(open) {
            if (!accountButton || !accountMenu) return;
            accountButton.setAttribute('aria-expanded', open ? 'true' : 'false');
            accountMenu.hidden = !open;
            accountButton.closest('.sidebar__account')?.classList.toggle('is-open', open);
        }

        if (accountButton && accountMenu) {
            accountButton.addEventListener('click', function (event) {
                event.preventDefault();
                setAccountMenu(accountMenu.hidden);
            });

            document.addEventListener('click', function (event) {
                const account = accountButton.closest('.sidebar__account');
                if (account && !account.contains(event.target)) {
                    setAccountMenu(false);
                }
            });

            document.addEventListener('keydown', function (event) {
                if (event.key === 'Escape') setAccountMenu(false);
            });
        }

        // ----------------------------
        // Collapsible sidebar groups
        // ----------------------------
        const groupButtons = document.querySelectorAll('[data-sidebar-group-toggle]');

        function setGroupState(button, open) {
            const panelId = button.getAttribute('aria-controls');
            const panel = panelId ? document.getElementById(panelId) : null;
            const group = button.closest('[data-sidebar-group]');

            button.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (panel) panel.hidden = !open;
            if (group) group.classList.toggle('is-open', open);
        }

        groupButtons.forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                const expanded = button.getAttribute('aria-expanded') === 'true';
                setGroupState(button, !expanded);
            });
        });

        // Always open groups containing the currently active page.
        groupButtons.forEach(function (button) {
            const panelId = button.getAttribute('aria-controls');
            const panel = panelId ? document.getElementById(panelId) : null;
            if (panel && panel.querySelector('.active')) {
                setGroupState(button, true);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();

