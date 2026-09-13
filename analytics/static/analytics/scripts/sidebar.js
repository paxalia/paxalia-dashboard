/* sidebar.js – handles sidebar toggle (open/close) and collapsible groups */

(function () {
    const body = document.querySelector('.analytics-body');
    const sidebar = document.querySelector('.analytics-sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const closeBtn = document.querySelector('.analytics-sidebar-close-btn');
    const STORAGE_KEY = 'analytics_sidebar_hidden';

    if (!body || !sidebar) return;

    function isHidden() {
        return body.classList.contains('sidebar-hidden');
    }

    function openBackdrop() {
        if (!backdrop) return;
        backdrop.hidden = false;
        backdrop.classList.add('is-visible');
        document.body.style.overflow = 'hidden';
    }

    function closeBackdrop() {
        if (!backdrop) return;
        backdrop.classList.remove('is-visible');
        backdrop.hidden = true;
        document.body.style.overflow = '';
    }

    function applyState(hidden) {
        body.classList.toggle('sidebar-hidden', hidden);

        if (toggleBtn) {
            toggleBtn.setAttribute('aria-expanded', hidden ? 'false' : 'true');
            toggleBtn.setAttribute(
                'aria-label',
                hidden ? 'Open sidebar' : 'Close sidebar'
            );
        }

        if (!hidden && window.innerWidth < 768) {
            openBackdrop();
        } else {
            closeBackdrop();
        }

        try {
            localStorage.setItem(STORAGE_KEY, hidden ? 'true' : 'false');
        } catch (err) {
            // localStorage can be unavailable in privacy-restricted contexts.
        }
    }

    function showSidebar() {
        applyState(false);
    }

    function hideSidebar() {
        applyState(true);
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function (event) {
            event.preventDefault();
            applyState(!isHidden());
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', function (event) {
            event.preventDefault();
            hideSidebar();
        });
    }

    if (backdrop) {
        backdrop.addEventListener('click', hideSidebar);
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !isHidden()) {
            hideSidebar();
        }
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth >= 768) {
            closeBackdrop();
        } else if (!isHidden()) {
            openBackdrop();
        }
    });

    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        applyState(saved === 'true');
    } catch (err) {
        applyState(false);
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

        if (panel) {
            panel.hidden = !open;
        }

        if (group) {
            group.classList.toggle('is-open', open);
        }
    }

    function openGroupIfActive(button) {
        const panelId = button.getAttribute('aria-controls');
        const panel = panelId ? document.getElementById(panelId) : null;
        if (!panel) return;

        if (panel.querySelector('.active')) {
            setGroupState(button, true);
        }
    }

    groupButtons.forEach((button) => {
        const panelId = button.getAttribute('aria-controls');
        const panel = panelId ? document.getElementById(panelId) : null;
        if (!panel) return;

        button.addEventListener('click', function () {
            const isOpen = button.getAttribute('aria-expanded') === 'true';
            setGroupState(button, !isOpen);
        });

        openGroupIfActive(button);
    });
})();
