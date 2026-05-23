(function() {
    const refreshSeconds = window.__analytics_realtime.refreshSeconds || 30;

    function fetchRealtimeData() {
        fetch(window.__analytics_realtime.dataUrl)
            .then(response => response.json())
            .then(data => {
                document.getElementById('uniqueCount').textContent = data.unique_ips;
                document.getElementById('viewCount').textContent = data.total_views;
                document.getElementById('updateTime').textContent = data.timestamp;

                const tbody = document.querySelector('#realtimeTable tbody');
                tbody.innerHTML = '';
                if (data.recent.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">' + window.__analytics_realtime.emptyMessage + '</td></tr>';
                } else {
                    data.recent.forEach(r => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = '<td>' + r.path + '</td><td>' + r.ip_hash + '</td><td>' + r.method + '</td><td>' + r.status_code + '</td><td>' + r.time + '</td>';
                        tbody.appendChild(tr);
                    });
                }
            })
            .catch(err => console.error('Realtime fetch error:', err));
    }

    fetchRealtimeData();
    setInterval(fetchRealtimeData, refreshSeconds * 1000);
})();