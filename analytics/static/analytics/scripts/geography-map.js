(function () {
    const data = window.__analytics_geography;
    const mapData = {};
    let totalViews = 0;

    if (data && data.countries && data.countries.length) {
        totalViews = data.countries.reduce((sum, c) => sum + c.count, 0);

        // Sort countries by count and split into 5 equal quintiles
        const sorted = [...data.countries].sort((a, b) => a.count - b.count);
        const quintileSize = Math.ceil(sorted.length / 5);
        const fillKeys = ['VERY_LOW', 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'];

        sorted.forEach((c, index) => {
            const quintile = Math.floor(index / quintileSize);   // 0‑4
            const fillKey = fillKeys[Math.min(quintile, 4)];
            mapData[c.code] = {fillKey: fillKey, count: c.count};
        });
    }

    var map = new Datamap({
        element: document.getElementById('world-map'),
        projection: 'mercator',
        fills: {
            defaultFill: '#21262d',
            VERY_HIGH: '#f6c84c',   // brightest gold
            HIGH: '#e2b13b',        // warm amber
            MEDIUM: '#8b949e',      // neutral grey
            LOW: '#484f58',         // darker grey
            VERY_LOW: '#30363d',    // almost background
        },
        data: mapData,
        geographyConfig: {
            borderColor: '#0d1117',
            highlightBorderWidth: 1,
            popupTemplate: function (geo, d) {
                if (!d) {
                    return '<div class="hoverinfo">' + geo.properties.name + ': 0 views</div>';
                }
                var pct = totalViews > 0 ? ((d.count / totalViews) * 100).toFixed(1) : '0.0';
                return '<div class="hoverinfo"><strong>' + geo.properties.name + '</strong><br>' +
                    d.count + ' views (' + pct + '%)</div>';
            },
        }
    });

    // ── Click a country to filter cities ──
    map.svg.selectAll('.datamaps-subunit').on('click', function (geo) {
        if (geo && geo.id && geo.id !== 'ATA') {   // ignore Antarctica
            // Find the alpha2 code from our injected data
            const country = data.countries.find(c => c.code === geo.id);
            const alpha2 = country ? country.alpha2 : geo.id;
            const params = new URLSearchParams(window.location.search);
            params.set('country', alpha2);
            window.location.search = params.toString();
        }
    });

    // ── Drag‑to‑scroll for the map container ──
    const scrollContainer = document.querySelector('.world-map-scroll');
    if (scrollContainer) {
        let isDown = false, startX, startY, scrollLeft, scrollTop;

        scrollContainer.addEventListener('mousedown', function (e) {
            isDown = true;
            scrollContainer.style.cursor = 'grabbing';
            startX = e.pageX - scrollContainer.offsetLeft;
            startY = e.pageY - scrollContainer.offsetTop;
            scrollLeft = scrollContainer.scrollLeft;
            scrollTop = scrollContainer.scrollTop;
            e.preventDefault();   // prevent text selection / map drag
        });

        scrollContainer.addEventListener('mouseleave', function () {
            isDown = false;
            scrollContainer.style.cursor = '';
        });

        scrollContainer.addEventListener('mouseup', function () {
            isDown = false;
            scrollContainer.style.cursor = '';
        });

        scrollContainer.addEventListener('mousemove', function (e) {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - scrollContainer.offsetLeft;
            const y = e.pageY - scrollContainer.offsetTop;
            const walkX = (x - startX) * 1;
            const walkY = (y - startY) * 1;
            scrollContainer.scrollLeft = scrollLeft - walkX;
            scrollContainer.scrollTop = scrollTop - walkY;
        });
    }

    // Responsive resize
    window.addEventListener('resize', function () {
        map.resize();
    });
})();