const company = "TESTTESTEST"; // Change this later
let currentPrice = null;
const MAX_HEADLINES = 20;

// Getting the chart element
const ctx = document.getElementById('chart').getContext('2d');

let data = {
    labels: [],
    datasets: [{
        data: [],
        borderColor: '#5b9def',
        backgroundColor: 'rgba(91, 157, 239, 0.12)',
        borderWidth: 2,
        fill: true,
        tension: 0.25,
    }]
};

const chart = new Chart(ctx, {
    type: 'line',
    data: data,
    options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        elements: {
            point: { radius: 0, hoverRadius: 4 }
        },
        plugins: {
            legend: {
                labels: { color: '#e8ecf1', font: { size: 12, weight: '600' } }
            }
        },
        scales: {
            x: {
                ticks: { color: '#9ca3af', maxTicksLimit: 8 },
                grid: { color: 'rgba(255, 255, 255, 0.06)' }
            },
            y: {
                ticks: { color: '#9ca3af' },
                grid: { color: 'rgba(255, 255, 255, 0.06)' }
            }
        },
    }
});

// Opening a connection to the websocket
const socket = new WebSocket('ws://localhost:8000/ws/alienstocksim/');

socket.onmessage = function(e) {
    // Getting the value + time stamp
    const dataPoint = JSON.parse(e.data);

    if (dataPoint.type === "news_headline") {
        console.log("headline received:", dataPoint.headline);  // check this in browser devtools
        addHeadline(dataPoint.headline);
        return;
    }

    if (dataPoint.type === "price_history") {
        // Pre-populate chart with cached points before live data arrives
        console.log(dataPoint);
        dataPoint.datapoints.forEach(dp => {
            const time = new Date(dp.t * 1000).toLocaleTimeString();
            const price = dp.p / 100;  // cents → dollars
            chart.data.labels.push(time);
            chart.data.datasets[0].data.push(price);
        });
        chart.update('none');
        return;
    }

    const time = new Date().toLocaleTimeString();
    currentPrice = dataPoint.price;

    // Max number of points that can be present at once
    const max_points = 10;

    // Calculating the percent change in value
    const prevPrice = chart.data.datasets[0].data.at(-1) ?? dataPoint.price;
    const change = ((dataPoint.price - prevPrice) / prevPrice * 100).toFixed(2);

    // Creating + setting the legend value
    const sign = change >= 0 ? "+" : "";
    chart.data.datasets[0].label = `Test Stock ${sign}${change}%`;

    // Adding the data points
    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(dataPoint.price);

    // Shifts the whole chart if the # of data points exceeds the max points allowed
    if (chart.data.labels.length > max_points) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update('none');
};

async function buyStock() {
    // Communication with DJango
    const res = await fetch("/trade/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken()},
        // Passes the stock company, action, and price
        body: JSON.stringify({ company, action: "buy", price: currentPrice }) 
    });
    const data = await res.json();
    // Setting the UI
    document.getElementById("holdings").textContent = data.quantity;
    document.getElementById("liquid_money").textContent = `$${data.liquid_money}`;
    // Refreshing the screen
    fetchStats();
}

async function sellStock() {
    // Communication with DJango
    const res = await fetch("/trade/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken()},
        // Passes the stock company, action, and price
        body: JSON.stringify({ company, action: "sell", price: currentPrice })
    });
    const data = await res.json();
    // Setting the UI
    document.getElementById("holdings").textContent = data.quantity;
    document.getElementById("liquid_money").textContent = `$${data.liquid_money}`;
    // Refreshing the screen
    fetchStats();
}

async function fetchStats() {
    // Communication with DJango
    const res = await fetch(`/stats/${company}/`);
    const data = await res.json();
    // Setting the UI
    document.getElementById("total_holders").textContent = data.holders;
    document.getElementById("total_shares").textContent = data.total_quantity;
}

// Getting CSRF Token
function getCSRFToken() {
    let cookies = document.cookie.split(";")
    for (let i = 0; i < cookies.length; i++) {
        let c = cookies[i].trim();
        if (c.startsWith("csrftoken=")) {
            return c.substring("csrftoken=".length, c.length);
        }
    }
    return "unknown";
}


// News filter dropdown toggle
const filterBtn = document.getElementById('news_filter_btn');
const filterDropdown = document.getElementById('news_filter_dropdown');

filterBtn?.addEventListener('click', () => {
    const open = filterDropdown.classList.toggle('open');
    filterBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});

document.addEventListener('click', (e) => {
    if (!filterBtn || !filterDropdown) return;
    if (!filterBtn.contains(e.target) && !filterDropdown.contains(e.target)) {
        filterDropdown.classList.remove('open');
        filterBtn.setAttribute('aria-expanded', 'false');
    }
});


function addHeadline(data) {
    const newsFeed = document.getElementById('news_feed');
    if (!newsFeed) return;
    const placeholder = newsFeed.querySelector('.news_placeholder');
    if (placeholder) placeholder.remove();

    const directionClass = data.direction === 'up' ? 'news_tag_up' : 'news_tag_down';
    const arrow = data.direction === 'up' ? '▲' : '▼';

    const item = document.createElement('div');
    item.className = 'news_item';
    item.setAttribute('data-company', data.company);
    item.innerHTML = `
        <span class="news_tag ${directionClass}">${data.company} ${arrow}</span>
        <div class="news_text">
            <strong>${data.headline}</strong>
            <p class="news_blurb">${data.blurb}</p>
        </div>
    `;

    newsFeed.prepend(item);

    const items = newsFeed.querySelectorAll('.news_item');
    if (items.length > MAX_HEADLINES) {
        items[items.length - 1].remove();
    }
}

window.onload= function () {
    fetchStats();

    document.querySelectorAll('.news_filter_option').forEach(option => {
        option.addEventListener('click', () => {
            const selected = option.textContent.trim();
            const items = document.querySelectorAll('.news_item');
            filterBtn.textContent = selected === 'All Companies' ? 'Filter by Company ▾' : `${selected} ▾`;
            items.forEach(item => {
                if (selected === 'All Companies' || item.getAttribute('data-company') === selected) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });

            filterDropdown.classList.remove('open');
            filterBtn.setAttribute('aria-expanded', 'false');
        });
    });
    }