(function() {
    const data = window.__analytics_events;
    if (!data) return;
    const ctx = document.getElementById('eventsChart');
    if (!ctx) return;

    const datasets = [{
        label: 'Events',
        data: data.data,
        borderColor: '#f6c84c',
        backgroundColor: 'rgba(246,200,76,0.08)',
        fill: true,
        tension: 0.3,
        pointBackgroundColor: '#f6c84c',
    }];

    if (data.compareActive) {
        datasets.push({
            label: 'Previous period',
            data: data.previousData,
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
            labels: data.labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                subtitle: {
                    display: true,
                    text: data.dateRangeLabel || '',
                    color: '#8b949e',
                    font: { size: 12 }
                }
            },
            scales: {
                x: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { beginAtZero: true, ticks: { color: '#8b949e', precision: 0 }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
})();