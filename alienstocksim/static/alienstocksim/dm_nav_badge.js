/**
 * Polls unread DM count and updates the Messages nav red dot without a full page reload.
 */
(function () {
    const POLL_MS = 3000;
    const link = document.querySelector('.nav-msg-link');
    if (!link) return;

    let lastUnreadCount = null;

    function syncBadge(count, sender, preview, threadUrl) {
        let badge = link.querySelector('.nav-unread-badge');
        if (count > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'nav-unread-badge';
                link.appendChild(badge);
            }
            const plural = count === 1 ? '' : 's';
            const label = `${count} unread direct message${plural}`;
            badge.title = `${count} unread`;
            badge.setAttribute('aria-label', label);
        } else {
            badge?.remove();
        }

        if (
            lastUnreadCount !== null &&
            count > lastUnreadCount &&
            sender &&
            Notification.permission === 'granted' &&
            navigator.serviceWorker?.controller
        ) {
            navigator.serviceWorker.controller.postMessage({
                type: 'NEW_MESSAGE',
                sender,
                preview,
                url: threadUrl,
            });
        }
        lastUnreadCount = count;
    }

    async function poll() {
        try {
            const res = await fetch('/unread_messages/', {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
            });
            if (!res.ok) return;
            const data = await res.json();
            const count = typeof data.unread_count === 'number' ? data.unread_count : 0;
            syncBadge(count, data.sender, data.preview, data.thread_url);
        } catch (_) {
            /* ignore network errors */
        }
    }

    poll();
    setInterval(poll, POLL_MS);
})();
