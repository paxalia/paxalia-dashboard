/* sidebar.js – handles sidebar toggle (open/close) on all screens */

(function () {
    const body = document.querySelector('.analytics-body');
    const sidebar = document.querySelector('.analytics-sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const closeBtn = document.querySelector('.analytics-sidebar-close-btn');
    const STORAGE_KEY = 'analytics_sidebar_hidden';

    // Check if currently hidden
    function isHidden() {
        return body.classList.contains('sidebar-hidden');
    }

    // Update UI based on state
    function applyState(hidden) {
        if (hidden) {
            body.classList.add('sidebar-hidden');
            closeBackdrop();
        } else {
            body.classList.remove('sidebar-hidden');
            // On mobile, show backdrop when opening
            if (window.innerWidth < 768) {
                backdrop.hidden = false;
                backdrop.classList.add('is-visible');
                document.body.style.overflow = 'hidden';
            }
        }
        localStorage.setItem(STORAGE_KEY, hidden);
    }

    function showSidebar() {
        applyState(false);
    }

    function hideSidebar() {
        applyState(true);
    }

    function closeBackdrop() {
        backdrop.classList.remove('is-visible');
        backdrop.hidden = true;
        document.body.style.overflow = '';
    }

    // Toggle button (header)
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (isHidden()) {
                showSidebar();
            } else {
                hideSidebar();
            }
        });
    }

    // Close button inside sidebar
    if (closeBtn) {
        closeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            hideSidebar();
        });
    }

    // Backdrop click closes sidebar on mobile
    if (backdrop) {
        backdrop.addEventListener('click', hideSidebar);
    }

    // Escape key closes sidebar
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !isHidden()) {
            hideSidebar();
        }
    });

    // When resizing to desktop, ensure backdrop is hidden and body overflow reset
    window.addEventListener('resize', function () {
        if (window.innerWidth >= 768) {
            closeBackdrop();
        } else if (!isHidden()) {
            // Re-open overlay if we were showing it before resize
            backdrop.hidden = false;
            backdrop.classList.add('is-visible');
            document.body.style.overflow = 'hidden';
        }
    });

    // Restore saved state (default: sidebar visible)
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'true') {
        applyState(true);
    }
})();