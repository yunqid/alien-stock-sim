// Getting the chart element
const ctx = document.getElementById('chart').getContext('2d');

let data = {
    labels: [], // X-axis
    datasets: [{
        data: [] // Y-axis
    }]
};

const chart = new Chart(ctx, {
    type: 'line', // Type of chart
    data: data, // Data that is being used to draw the chart, see above
    options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false, // Allows the size of the chart to rescale
        y: {
            beginAtZero: false,
        }
    }
});

// Opening a connection to the websocket
const socket = new WebSocket('ws://localhost:8000/ws/alienstocksim/');

socket.onmessage = function(e) {
    // Getting the value + time stamp
    const dataPoint = JSON.parse(e.data);
    const time = new Date().toLocaleTimeString();

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