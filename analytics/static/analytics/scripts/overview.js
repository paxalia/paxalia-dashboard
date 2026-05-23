(function () {
    const overview = window.__analytics_overview;
    if (!overview) return;

    const ctx1 = document.getElementById('viewsChart');
    if (ctx1) {
        const datasets = [{
            label: 'Page Views',
            data: overview.viewsData,
            borderColor: '#f6c84c',
            backgroundColor: 'rgba(246,200,76,0.08)',
            fill: true,
            tension: 0.3,
            pointBackgroundColor: '#f6c84c',
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2,
        }];

        // Add previous period dataset if comparison is active
        if (overview.compareActive) {
            datasets.push({
                label: 'Previous period',
                data: overview.previousViewsData,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.05)',
                borderDash: [6, 4],
                tension: 0.3,
                pointBackgroundColor: 'rgba(246,200,76,0.6)',
                pointRadius: 2,
                pointHoverRadius: 4,
                borderWidth: 2,
            });
        }

        new Chart(ctx1.getContext('2d'), {
            type: 'line',
            data: {
                labels: overview.viewsLabels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {display: false},
                    subtitle: {
                        display: true,
                        text: overview.dateRangeLabel || '',
                        color: '#8b949e',
                        font: {size: 12}
                    }
                },
                scales: {
                    x: {
                        ticks: {color: '#8b949e', font: {size: 11}},
                        grid: {color: 'rgba(255,255,255,0.05)'}
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {color: '#8b949e', font: {size: 11}, precision: 0},
                        grid: {color: 'rgba(255,255,255,0.05)'}
                    }
                }
            }
        });
    }

    // Top pages bar chart – unchanged
    const ctx2 = document.getElementById('topPagesChart');
    if (ctx2) {
        new Chart(ctx2.getContext('2d'), {
            type: 'bar',
            data: {
                labels: overview.topPagesLabels,
                datasets: [{
                    label: 'Views',
                    data: overview.topPagesData,
                    backgroundColor: '#f6c84c',
                    borderRadius: 4,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {legend: {display: false}},
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {color: '#8b949e', font: {size: 11}, precision: 0},
                        grid: {color: 'rgba(255,255,255,0.05)'}
                    },
                    y: {
                        ticks: {color: '#c9d1d9', font: {size: 11}},
                        grid: {display: false}
                    }
                }
            }
        });
    }
})();