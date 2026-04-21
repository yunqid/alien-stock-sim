let company = "Pear";
let currentPrice = null;
const MAX_HEADLINES = 20;

// Getting the chart element
const ctx = document.getElementById('chart').getContext('2d');

// Setting up the chart stuff
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

// Setting the websocket
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const socket = new WebSocket(protocol + "//" + window.location.host + "/ws/alienstocksim/");

// Constant variables
const LEADERBOARD_POLL_MS = 8000;

// Error Messages
const ERROR_MESSAGES = {
    insufficient_funds: "You don't have enough money to buy this share.",
    no_shares_available: "There are no more shares available for this company.",
    no_shares: "You don't own enough shares of this company.",
    invalid_price: "Invalid price please wait for the chart to load.",
    invalid_json: "Something went wrong. Please try again.",
    invalid_company: "Invalid company selected.",
    invalid_action: "Invalid action.",
    no_profile: "Profile not found. Please refresh the page.",
    invalid_amount: "Invalid amount of stocks to purchase/sell.",
    server_busy: "server busy please try again later.",
};

// Basic Error Alert
function showTradeError(code) {
    const msg = ERROR_MESSAGES[code];
    alert(msg);
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

// Basic sanitization function
function sanitize(s) {
    // Check if s is null
    return (s ?? "").toString().replace(/[^0-9]/g, "");
}

// Run these when recieving a message
socket.onmessage = function(e) {
    // Getting the value + time stamp
    const dataPoint = JSON.parse(e.data);

    // Recieving news headline
    if (dataPoint.type === "news_headline") {
        console.log("headline received:", dataPoint.headline);  // check this in browser devtools
        addHeadline(dataPoint.headline);
        return;
    }

    // Recieving price history
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

    // Ignoring updates that is not the company currently in view
    if (dataPoint.type === "stock_price" && dataPoint.company !== company) return;

    // Setting values of the new datapoint
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
    updateTradeButtonsDisabled(); 
    closeTradeModal(); // Closes trade popup to refresh price
};

let modalAction = null;
let modalQuantity = 1;

// Server trade_stock charges int(price) whole dollars per share (Python int()).
function getTradingSnapshot() {
    // Getting basic information
    const heldRaw = parseInt(sanitize(document.getElementById("holdings")?.textContent), 10) || 0;
    const liquidRaw = parseInt(sanitize((document.getElementById("liquid_money")?.textContent)), 10) || 0;
    const remainingRaw = parseInt(sanitize(document.getElementById("shares_remaining")?.textContent), 10) || 0;
    const price = Number(currentPrice);

    return {
        held: Number.isFinite(heldRaw) ? heldRaw : 0,
        liquid: Number.isFinite(liquidRaw) ? liquidRaw : 0,
        remaining: Number.isFinite(remainingRaw) ? remainingRaw : 0,
        priceInt: Math.floor(price),
        priceOk: Number.isFinite(price) && price > 0,
    };
}

// Simple check functions that checks if the user can buy/sell one stock
function canAffordOneShare() {
    const s = getTradingSnapshot();
    if (!s.priceOk || s.priceInt < 1) return false;
    return s.liquid >= s.priceInt && s.remaining >= 1;
}
function canSellOneShare() {
    return getTradingSnapshot().held >= 1;
}

// Updates the action buttons based on if the user can buy/sell
function updateTradeButtonsDisabled() {
    // Getting the trade button
    const buyBtn = document.getElementById("buy_button");
    const sellBtn = document.getElementById("sell_button");
    // Returns if the buttons doesn't exist
    if (!buyBtn || !sellBtn) return;
    // Disables the button if the corresponding action can't be done
    buyBtn.disabled = !canAffordOneShare();
    sellBtn.disabled = !canSellOneShare();
    //BUG: DOES NOT DISABLE IF THERE ARE NO MORE SHARES TO BE BOUGHT
}

// Not sure if the below is ever needed since the user can't physically buy or sell greater than they can
// Updates confirmation button in the popup
/*
function syncModalConfirmDisabled() {
    const btn = document.getElementById("modal_confirm");
    if (!btn || !modalAction) return;
    if (modalAction === "buy") {
        const s = getTradingSnapshot();
        const maxAff = s.priceOk && s.priceInt > 0 ? Math.floor(s.liquid / s.priceInt) : 0;
        const maxBuyable = Math.min(maxAff, s.remaining);
        btn.disabled = maxBuyable < 1 || modalQuantity < 1 || modalQuantity > maxBuyable;
    } else {
        const held = getTradingSnapshot().held;
        btn.disabled = held < 1 || modalQuantity < 1 || modalQuantity > held;
    }
}
*/

// This function opens the trade popup and changes the contents depending on the action
function openTradeModal(action) {
    // User can't open popup unless they can do the action
    if (action === "buy" && !canAffordOneShare()) return;
    if (action === "sell" && !canSellOneShare()) return;

    modalAction = action;
    modalQuantity = 1;
    
    // Getting basic information
    const held = parseInt(sanitize(document.getElementById("holdings")?.textContent), 10) || 0;
    const liquid = parseInt(sanitize((document.getElementById("liquid_money")?.textContent)), 10) || 0;
    const remaining = parseInt(sanitize(document.getElementById("shares_remaining")?.textContent), 10) || 0;

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
    //syncModalConfirmDisabled();
    document.getElementById("trade_modal").classList.add("open");
}

// Updating the popup
function updateModalQuantity() {
    // Getting basic information
    const held = parseInt(document.getElementById("holdings").textContent) || 0;
    const input = document.getElementById("modal_quantity");
    const s = getTradingSnapshot();

    // Makes sure that the input amount is valid
    // Defaults to 0
    modalQuantity = parseInt(input.value, 10);
    if (!Number.isFinite(modalQuantity) || modalQuantity < 0) modalQuantity = 0;

    // Limiting the range of possible number of stocks to buy/sell
    if (modalAction === "buy") {
        // Calculations for how many stocks the user can afford
        const maxAff = s.priceOk && s.priceInt > 0? Math.floor(s.liquid / s.priceInt) : 0;
        const maxBuyable = Math.min(maxAff, s.remaining);
        // Setting the maximum value for the input
        input.max = Math.max(0, maxBuyable);
        // Setting the minimal value for the input
        if (maxBuyable < 1) {
            input.min = 0;
            modalQuantity = 0;
            input.value = 0;
        } else {
            input.min = 1;
            modalQuantity = Math.max(1, Math.min(modalQuantity, maxBuyable)); // Clamps the value of input
            input.value = modalQuantity;
        }
    } else {
        // Setting the maximal value for the input
        input.max = Math.max(0, held);
        // Setting the minimal value for the input
        input.min = held >= 1 ? 1 : 0;
        if (held < 1) {
            modalQuantity = 0;
            input.value = 0;
        } else {
            modalQuantity = Math.max(1, Math.min(modalQuantity, held)); // Clamps the value of the input
            input.value = modalQuantity;
        }
    }

    // Updating the modal display
    let totalStr;
    // Default to 0.00 if the user can't buy or sell
    if (modalAction === "buy" && modalQuantity < 1) {
        totalStr = "0.00";
    } else if (modalAction === "sell" && modalQuantity < 1) {
        totalStr = "0.00";
    } else {
        const total = Number(currentPrice) * modalQuantity; // Calculating
        totalStr = total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    document.getElementById("modal_total").textContent = `$${totalStr}`;
    //syncModalConfirmDisabled();
}

// Closing the popup
function closeTradeModal() {
    document.getElementById("trade_modal").classList.remove("open");
    // Resetting the values of the modal
    modalAction = null;
    modalQuantity = 1;
}

// Processing the trade
async function confirmTrade() {
    // Getting the amount of stock to trade
    const qty = modalQuantity;
    // If the number of stocks to trade is invalid close the modal
    // Same for 0, because nothing changes
    if (!Number.isFinite(qty) || qty < 1) {
        closeTradeModal();
        return;
    }

    bsPrice = currentPrice;

    // buy/sell the stocks all at once
    const res = await fetch("/trade/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken() },
        body: JSON.stringify({ company, action: modalAction || 
            (document.getElementById("modal_confirm").classList.contains("btn_buy") ? "buy" : "sell"), 
            price: bsPrice, amount: qty})
    });

    // Closing the popup now that trade is complete
    closeTradeModal();

    // Error handeling
    if (!res.ok) {
        const err = await res.json();
        showTradeError(err.error);
        return;
    }
    // Waiting for response then updating holdings + liquid money
    const data = await res.json();
    document.getElementById("holdings").textContent = data.quantity;
    document.getElementById("liquid_money").textContent = `$${data.liquid_money}`;

    await fetchStockStats();
    refreshLeaderboard();
    updateTradeButtonsDisabled();
}

// Basic functions for opening up the trade popup with the right action
function buyStock() {
    if (!canAffordOneShare()) return;
    openTradeModal("buy");
}
function sellStock() {
    if (!canSellOneShare()) return;
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
    updateTradeButtonsDisabled();
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
    updateTradeButtonsDisabled();
}


// Creates an URL to a user's profile
function profilePathForUser(username) {
    return `/profile/${encodeURIComponent(username)}`;
}

// Renders leaderboard
function renderLeaderboardRows(rows) {
    // Getting the leaderboard container
    const container = document.getElementById("leaderboard_list");
    if (!container) return;
    container.replaceChildren(); // Clears the current content

    // Creating and empty leaderboard
    if (!rows || !rows.length) {
        const empty = document.createElement("div");
        empty.className = "leaderboard_row leaderboard_empty";
        empty.textContent = "No users yet.";
        container.appendChild(empty);
        return;
    }
   // Populating the leaderboard
    for (const row of rows) {
        const div = document.createElement("div");
        div.className = "leaderboard_row";

        // Highlighting current user
        if (row.is_current) div.classList.add("current_user");

        // Adding a medal next to the top 3
        if (row.rank === 1) div.classList.add("rank_medal_1");
        else if (row.rank === 2) div.classList.add("rank_medal_2");
        else if (row.rank === 3) div.classList.add("rank_medal_3");

        // Creating row elements
        const rankSpan = document.createElement("span");
        rankSpan.className = "rank";
        rankSpan.textContent = `${row.rank}.`;

        const link = document.createElement("a");
        link.className = "username";
        link.href = profilePathForUser(row.username);
        link.textContent = row.username;

        const worth = document.createElement("span");
        worth.className = "net_worth";
        worth.textContent = row.net_worth;

        // Adds row to container
        div.append(rankSpan, link, worth);
        container.appendChild(div);
    }
}

// Regreshes the leaderboard
async function refreshLeaderboard() {
    // Getting the leaderboard container
    const container = document.getElementById("leaderboard_list");
    if (!container) return;

    try {
        // Sends a request for leaderboard data
        const res = await fetch("/api/leaderboard/");
        if (!res.ok) return;
        const data = await res.json();
        // Constructs the leaderboard once data is recieved
        renderLeaderboardRows(data.rows);
    } catch (_) {
        /* ignore transient network errors */
    }
}

// News filter dropdown toggle
const newsFilterBtn = document.getElementById('news_filter_btn');
const newsFilterDropdown = document.getElementById('news_filter_dropdown');

// Add in event listeners for the news filter button
// Event listener for opening the dropdown when pressing the dropdown
newsFilterBtn?.addEventListener('click', () => {
    const open = newsFilterDropdown.classList.toggle('open');
    newsFilterBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});
// Event listener to close the dropdown when pressing outside
document.addEventListener('click', (e) => {
    if (!newsFilterBtn || !newsFilterDropdown) return;
    if (!newsFilterBtn.contains(e.target) && !newsFilterDropdown.contains(e.target)) {
        newsFilterDropdown.classList.remove('open');
        newsFilterBtn.setAttribute('aria-expanded', 'false');
    }
});

// Chart filter dropdown toggle
const chartFilterBtn = document.getElementById('chart_filter_btn');
const chartFilterDropdown = document.getElementById('chart_filter_dropdown');

// Add in event listerners for the chart filter button
// Event listener for opening the dropdown when pressing the dropdown
chartFilterBtn?.addEventListener('click', () => {
    const open = chartFilterDropdown.classList.toggle('open');
    chartFilterBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});
// Event listener to close the dropdown when pressing outside
document.addEventListener('click', (e) => {
    if (!chartFilterBtn || !chartFilterDropdown) return;
    if (!chartFilterBtn.contains(e.target) && !chartFilterDropdown.contains(e.target)) {
        chartFilterDropdown.classList.remove('open');
        chartFilterBtn.setAttribute('aria-expanded', 'false');
    }
});

// Adds new headlines to the news container
function addHeadline(data) {
    // Getting the container for headlines
    const newsFeed = document.getElementById('news_feed');
    if (!newsFeed) return;
    const placeholder = newsFeed.querySelector('.news_placeholder');
    if (placeholder) placeholder.remove();

    // Getting the direction of the impact
    const directionClass = data.direction === 'up' ? 'news_tag_up' : 'news_tag_down';
    const arrow = data.direction === 'up' ? '▲' : '▼';

    // Creating the news item
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

    // Removing news item when the number exceed the max number
    const items = newsFeed.querySelectorAll('.news_item');
    if (items.length > MAX_HEADLINES) {
        items[items.length - 1].remove();
    }
}

// Switching company
function switchCompany(newCompany) {
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

    fetchStockStats();
    //getTradingSnapshot();
    fetchUserStats(); // Waiting for price to update
}

// The below is ran the moment the window is loaded
window.onload= function () {
    // Updates the leaderboard periodically
    refreshLeaderboard();
    setInterval(refreshLeaderboard, LEADERBOARD_POLL_MS);
    setInterval(fetchStockStats, LEADERBOARD_POLL_MS);
    setInterval(fetchUserStats, LEADERBOARD_POLL_MS);

    // Add event listeners to each of the drop down option
    document.querySelectorAll('.news_filter_option').forEach(option => {
        option.addEventListener('click', () => {
            // Gets the company to filter by
            const selected = option.textContent.trim();
            // Gets all news items
            const items = document.querySelectorAll('.news_item');
            // Updates the news filter btn's text
            newsFilterBtn.textContent = selected === 'All Companies' ? 'Filter by Company ▾' : `${selected} ▾`;
            items.forEach(item => {
                // Only display the company selected
                if (selected === 'All Companies' || item.getAttribute('data-company') === selected) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });

            newsFilterDropdown.classList.remove('open');
            newsFilterBtn.setAttribute('aria-expanded', 'false');
        });
    });

    // Chart filter
    document.querySelectorAll('.chart_filter_option').forEach(option => {
        option.addEventListener('click', () => {
            // Getting the company to switch to
            const selected = option.textContent.trim();
            // Updates the chart filter btn's text
            chartFilterBtn.textContent = `${selected} ▾`;

            switchCompany(selected);

            chartFilterDropdown.classList.remove('open');
            chartFilterBtn.setAttribute('aria-expanded', 'false');
        });
    });

    // Add listeners to the buy and sell button
    document.getElementById("buy_button")?.addEventListener("click", () => buyStock());
    document.getElementById("sell_button")?.addEventListener("click", () => sellStock());

    // Add listeners to the trade popup buttons
    document.getElementById("modal_cancel").addEventListener("click", closeTradeModal);
    document.getElementById("modal_confirm").addEventListener("click", confirmTrade);
    document.getElementById("modal_quantity").addEventListener("input", updateModalQuantity);
    // Add listener that closes the trade popup when clicking outside
    document.getElementById("trade_modal").addEventListener("click", (e) => {
        if (e.target === document.getElementById("trade_modal")) closeTradeModal();
    });

    fetchStockStats();
    fetchUserStats();
}

// Registers the service worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
}

// Hides the notification button if it's already enables
if (Notification.permission === 'granted') {
    document.getElementById('notif_button').style.display = 'none'
}

// Enables notification
async function enableNotifications() {
    // Waits for permission
    const permission = await Notification.requestPermission()
    if (permission === 'granted') {
        document.getElementById('notif_button').style.display = 'none' // Hides button
        const reg = await navigator.serviceWorker.ready
        // Show notification
        reg.showNotification("Notifications enabled!", {
            body: "You'll receive stock alerts here."
        })
    }
}

