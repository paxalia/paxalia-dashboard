(function() {
    const detail = window.__analytics_page_detail;
    if (!detail) return;

    const ctx = document.getElementById('pageViewsChart');
    if (!ctx) return;

    const datasets = [{
        label: 'Views',
        data: detail.data,
        borderColor: '#f6c84c',
        backgroundColor: 'rgba(246,200,76,0.08)',
        fill: true,
        tension: 0.3,
        pointBackgroundColor: '#f6c84c',
    }];

    if (detail.compareActive) {
        datasets.push({
            label: 'Previous period',
            data: detail.previousData,
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88,166,255,0.05)',
            borderDash: [6, 4],
            tension: 0.3,
            pointBackgroundColor: 'rgba(88,166,255,0.7)',
            pointRadius: 2,
            pointHoverRadius: 4,
            borderWidth: 2,
        });
    }

    new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: detail.labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                subtitle: {
                    display: true,
                    text: detail.dateRangeLabel || '',
                    color: '#8b949e',
                    font: { size: 12 }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#8b949e' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#8b949e', precision: 0 },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            }
        }
    });
})();