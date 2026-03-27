// self.addEventListener('message', (event) => {
//     if (event.data.type === 'PRICE_ALERT') {
//         const direction = event.data.changePercent > 0 ? '📈' : '📉'
//         self.registration.showNotification(`${direction} ${event.data.ticker} moved ${event.data.changePercent}%`, {
//             body: 'Tap to view your portfolio',
//             icon: '/static/images/your-icon.png'
//         })
//     }
// })

//Empty for now with test notifications