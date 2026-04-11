self.addEventListener('message', (event) => {
    if (event.data.type === 'NEW_MESSAGE') {
        self.registration.showNotification(
            `💬 New message from ${event.data.sender}`, {
                body: event.data.preview,
                data: { url: event.data.url },
            }
        );
    }
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = event.notification.data?.url || '/messages/';
    event.waitUntil(clients.openWindow(url));
});