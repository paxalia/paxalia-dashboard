document.addEventListener('DOMContentLoaded', function() {
    const chartDataElement = document.getElementById('admin-chart-data');
    if (!chartDataElement) return;

    let chartData;
    try {
        chartData = JSON.parse(chartDataElement.textContent);
    } catch (e) {
        console.warn('Admin chart data not available.');
        return;
    }

    const { labels, registrations, content, logins } = chartData;

    function createChart(ctx, type, data, label, color, borderColor) {
        const isBar = type === 'bar';
        const isLine = type === 'line';
        return new Chart(ctx, {
            type: type,
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: data,
                    backgroundColor: color,
                    borderColor: borderColor || color,
                    borderWidth: 1,
                    borderRadius: isBar ? 4 : 0,
                    fill: isLine ? true : false,
                    tension: isLine ? 0.3 : undefined,
                    pointRadius: isLine ? 1 : undefined,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    x: {
                        ticks: { color: '#8b949e', font: { size: 11 } },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // Registration chart (bar)
    const regCanvas = document.getElementById('registrationChart');
    if (regCanvas) {
        createChart(
            regCanvas.getContext('2d'),
            'bar',
            registrations,
            'New Users',
            'rgba(246, 200, 76, 0.7)',
            'rgba(246, 200, 76, 1)'
        );
    }

    // Content chart (line)
    const contentCanvas = document.getElementById('contentChart');
    if (contentCanvas) {
        createChart(
            contentCanvas.getContext('2d'),
            'line',
            content,
            'Content Created',
            'rgba(75,192,192,0.2)',
            '#4bc0c0'
        );
    }

    // Login chart (bar)
    const loginCanvas = document.getElementById('loginChart');
    if (loginCanvas) {
        createChart(
            loginCanvas.getContext('2d'),
            'bar',
            logins,
            'Logins',
            'rgba(54, 162, 235, 0.7)',
            'rgba(54, 162, 235, 1)'
        );
    }
});