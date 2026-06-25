document.addEventListener('DOMContentLoaded', function() {
    const dataElement = document.getElementById('bot-chart-data');
    if (!dataElement) return;
    const data = JSON.parse(dataElement.textContent);

    // Daily bot chart
    new Chart(document.getElementById('botDayChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.dates,
            datasets: [{
                label: 'Bot Requests',
                data: data.bot_counts,
                backgroundColor: 'rgba(255, 99, 132, 0.7)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { ticks: { color: '#8b949e', font: { size: 11 } }, grid: { display: false } }
            }
        }
    });

    // Top paths (horizontal bar)
    new Chart(document.getElementById('topPathsChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.top_paths,
            datasets: [{
                label: 'Requests',
                data: data.top_counts,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#8b949e', font: { size: 11 } }, grid: { display: false } }
            }
        }
    });

    // Country chart (doughnut)
    new Chart(document.getElementById('countryChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: data.country_codes,
            datasets: [{
                data: data.country_counts,
                backgroundColor: ['#ff6384', '#36a2eb', '#ff9f40', '#4bc0c0', '#9966ff', '#ffcd56', '#c9cbcf', '#ff8a80', '#b39ddb', '#80cbc4'],
                borderWidth: 2,
                borderColor: 'var(--analytics-surface, #161b22)',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: 'var(--analytics-text, #c9d1d9)', font: { size: 12 } }
                }
            },
            cutout: '60%',
        }
    });
});