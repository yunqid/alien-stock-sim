const ctx = document.getElementById('chart').getContext('2d');

let data = {
    labels: [],
    datasets: [{
        label: 'Stock Price',
        data: []
    }]
};

const chart = new Chart(ctx, {
    type: 'line',
    data: data
});

const socket = new WebSocket('ws://localhost:8000/ws/alienstocksim/');

socket.onmessage = function(e) {
    const dataPoint = JSON.parse(e.data);
    const time = new Date().toLocaleTimeString();

    const max_points = 10;

    const prevPrice = chart.data.datasets[0].data.at(-1) ?? dataPoint.price;
    const change = ((dataPoint.price - prevPrice) / prevPrice * 100).toFixed(2);

    const sign = change >= 0 ? "+" : "";

    chart.data.datasets[0].label = `Test Stock ${sign}${change}%`;

    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(dataPoint.price);

    if (chart.data.labels.length > max_points) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update();
};