// analytics/static/analytics/scripts/backups.js
document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh the page every 5 seconds if any backup is in 'creating' status
    const creatingBadges = document.querySelectorAll('.backup-status-creating');
    if (creatingBadges.length > 0) {
        setTimeout(() => {
            location.reload();
        }, 5000);
    }

    // Optional: chunked download support can be added here if needed
});