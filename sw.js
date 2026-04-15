// Event listener waiting for the "message" event
//When triggered, if it is a new message, it sends the notification
self.addEventListener('message', (event) => {
    if (event.data.type === 'NEW_MESSAGE') {
        self.registration.showNotification(
            `New message from ${event.data.sender}`, {
                body: event.data.preview,
                data: { url: event.data.url },
            }
        );
    }
});

// Event listener waiting for notification to be clicked
// If notification is clicked, it opens the website in a new tab to see messages
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = event.notification.data?.url || '/messages/';
    event.waitUntil(clients.openWindow(url));
});