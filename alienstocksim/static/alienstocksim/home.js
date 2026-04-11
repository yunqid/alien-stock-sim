let company = "Pear";
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

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const socket = new WebSocket(protocol + "//" + window.location.host + "/ws/alienstocksim/");

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
        dataPoint.datapoints.forEach(dp => {
            const time = new Date(dp.t * 1000).toLocaleTimeString();
            const price = dp.p / 100;  // cents → dollars
            chart.data.labels.push(time);
            chart.data.datasets[0].data.push(price);
        });
        chart.update('none');
        return;
    }

    if (dataPoint.type === "stock_price" && dataPoint.company !== company) return;

    const time = new Date().toLocaleTimeString();
    currentPrice = dataPoint.price;

    // Max number of points that can be present at once
    const max_points = 10;

    // Calculating the percent change in value
    const prevPrice = chart.data.datasets[0].data.at(-1) ?? dataPoint.price;
    const change = ((dataPoint.price - prevPrice) / prevPrice * 100).toFixed(2);

    // Creating + setting the legend value
    const sign = change >= 0 ? "+" : "";
    chart.data.datasets[0].label = `${company} ${sign}${change}%`;

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

// Error Messages
const ERROR_MESSAGES = {
    insufficient_funds: "You don't have enough money to buy this share.",
    no_shares_available: "There are no more shares available for this company.",
    no_shares: "You don't own any shares in this company.",
    invalid_price: "Invalid price — please wait for the chart to load.",
    invalid_json: "Something went wrong. Please try again.",
    invalid_company: "Invalid company selected.",
    invalid_action: "Invalid action.",
    no_profile: "Profile not found. Please refresh the page.",
};

// Basic Error Alert
function showTradeError(code) {
    const msg = ERROR_MESSAGES[code];
    alert(msg);
}

let modalAction = null;
let modalQuantity = 1;

// Opening the popup window
function openTradeModal(action) {
    modalAction = action;
    modalQuantity = 1;
    
    // Getting the values
    const held = parseInt(document.getElementById("holdings").textContent) || 0;
    const liquid = parseInt((document.getElementById("liquid_money").textContent || "0").replace(/[^0-9]/g, "")) || 0;
    const remaining = parseInt(document.getElementById("shares_remaining").textContent) || 0;

    // Setting the contents of the popup
    document.getElementById("modal_quantity").value = 1;
    document.getElementById("modal_title").textContent = action === "buy" ? "Confirm Purchase" : "Confirm Sale";
    document.getElementById("modal_company").textContent = company;
    document.getElementById("modal_price").textContent = `$${currentPrice.toFixed(2)}`;
    document.getElementById("modal_holdings").textContent = held;
    document.getElementById("modal_liquid").textContent = `$${liquid.toLocaleString()}`;
    document.getElementById("modal_shares_remaining").textContent = remaining;
    document.getElementById("modal_total_label").textContent = action === "buy" ? "Total cost" : "Total earnings";
    document.getElementById("modal_confirm").className = `btn_trade ${action === "buy" ? "btn_buy" : "btn_sell"}`;

    // Updating and opening the popup
    updateModalQuantity();
    document.getElementById("trade_modal").classList.add("open");
}

// Updating the popup
function updateModalQuantity() {
    // Getting the values
    const held = parseInt(document.getElementById("holdings").textContent) || 0;
    const remaining = parseInt(document.getElementById("shares_remaining").textContent) || 0;
    const liquid = parseInt((document.getElementById("liquid_money").textContent || "0").replace(/[^0-9]/g, "")) || 0;
    const input = document.getElementById("modal_quantity");

    modalQuantity = parseInt(input.value) || 1;

    // Bounding the input
    if (modalAction === "buy") {
        const maxAffordable = Math.floor(liquid / currentPrice);
        const maxBuyable = Math.min(maxAffordable, remaining);
        modalQuantity = Math.max(1, Math.min(modalQuantity, maxBuyable));
        input.max = maxBuyable;
    } else {
        modalQuantity = Math.max(1, Math.min(modalQuantity, held));
        input.max = held;
    }

    // Calculating and editing the cost/value
    input.value = modalQuantity;
    const total = (currentPrice * modalQuantity).toFixed(2);
    document.getElementById("modal_total").textContent = `$${parseFloat(total).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Closing the popup
function closeTradeModal() {
    document.getElementById("trade_modal").classList.remove("open");
    modalAction = null;
    modalQuantity = 1;
}
// Processing the trade
async function confirmTrade() {
    // Getting the amount to sell/buy
    const qty = modalQuantity;
    closeTradeModal();

    // Selling/buying each stock individually
    for (let i = 0; i < qty; i++) {
        const res = await fetch("/trade/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken() },
            body: JSON.stringify({ company, action: modalAction || (document.getElementById("modal_confirm").classList.contains("btn_buy") ? "buy" : "sell"), price: currentPrice })
        });
        if (!res.ok) {
            const err = await res.json();
            showTradeError(err.error);
            break;
        }
        const data = await res.json();
        document.getElementById("holdings").textContent = data.quantity;
        document.getElementById("liquid_money").textContent = `$${data.liquid_money}`;
    }

    fetchStockStats();
}

// Buying or selling
function buyStock() {
    openTradeModal("buy");
}
function sellStock() {
    openTradeModal("sell");
}

// Getting stock stats
async function fetchStockStats() {
    // Communication with DJango
    const res = await fetch(`/stock_stats/${company}/`);
    const data = await res.json();
    // Setting the UI
    document.getElementById("total_holders").textContent = data.holders;
    document.getElementById("total_shares").textContent = data.total_quantity;
    document.getElementById("shares_remaining").textContent = data.shares_remaining;
}

// Getting user stats
async function fetchUserStats() {
    // Communication with DJango
    const res = await fetch(`/user_stats/${company}/`);
    const data = await res.json();
    // Setting the UI and the current price
    document.getElementById("holdings").textContent = data.quantity;
    document.getElementById("liquid_money").textContent = `$${data.liquid_money}`;
    currentPrice = data.price;
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

function switchCompany(newCompany) {
    fetchStockStats();
    fetchUserStats();

    if (newCompany === company) return;
    company = newCompany;

    // Clear the chart
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.data.datasets[0].label = newCompany;
    chart.update('none');

    // Ask the server for the new company's cache
    socket.send(JSON.stringify({
        type: "switch_company",
        company: newCompany
    }));

    // Update the dropdown label
    document.getElementById('chart_filter_btn').textContent = `${newCompany} ▾`;
}

window.onload= function () {
    fetchStockStats();
    fetchUserStats();

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

    // Chart filter
    const chartFilterBtn = document.getElementById('chart_filter_btn');
    const chartFilterDropdown = document.getElementById('chart_filter_dropdown');

    chartFilterBtn?.addEventListener('click', () => {
        const open = chartFilterDropdown.classList.toggle('open');
        chartFilterBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.addEventListener('click', (e) => {
        if (!chartFilterBtn || !chartFilterDropdown) return;
        if (!chartFilterBtn.contains(e.target) && !chartFilterDropdown.contains(e.target)) {
            chartFilterDropdown.classList.remove('open');
            chartFilterBtn.setAttribute('aria-expanded', 'false');
        }
    });

    document.querySelectorAll('.chart_filter_option').forEach(option => {
        option.addEventListener('click', () => {
            const selected = option.getAttribute('data-company');
            switchCompany(selected);
            chartFilterDropdown.classList.remove('open');
            chartFilterBtn.setAttribute('aria-expanded', 'false');
        });
    });

    // Trade popup
    document.getElementById("modal_cancel").addEventListener("click", closeTradeModal);
    document.getElementById("modal_confirm").addEventListener("click", confirmTrade);
    document.getElementById("modal_quantity").addEventListener("input", updateModalQuantity);
    document.getElementById("trade_modal").addEventListener("click", (e) => {
        if (e.target === document.getElementById("trade_modal")) closeTradeModal();
    });
}

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
}

if (Notification.permission === 'granted') {
    document.getElementById('notif_button').style.display = 'none'
}

async function enableNotifications() {
    const permission = await Notification.requestPermission()
    if (permission === 'granted') {
        document.getElementById('notif_button').style.display = 'none'
        const reg = await navigator.serviceWorker.ready
        reg.showNotification("Notifications enabled!", {
            body: "You'll receive stock alerts here."
        })
    }
}

let lastUnreadCount = 0;

async function pollUnreadMessages() {
    if (Notification.permission !== 'granted' || !navigator.serviceWorker.controller) return;

    const res = await fetch('/unread_messages/');
    const data = await res.json();

    if (data.unread_count > lastUnreadCount && data.sender) {
        navigator.serviceWorker.controller.postMessage({
            type: 'NEW_MESSAGE',
            sender: data.sender,
            preview: data.preview,
            url: data.thread_url,
        });
    }

    lastUnreadCount = data.unread_count;
}

setInterval(pollUnreadMessages, 15000);
