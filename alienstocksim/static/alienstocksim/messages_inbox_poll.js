/**
 * Refreshes the messages inbox thread list every few seconds (no full page reload).
 */
(function () {
    const POLL_MS = 3000;
    const root = document.getElementById('inbox-thread-root');
    if (!root || !root.dataset.pollUrl) return;

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    function threadHref(username) {
        return `/messages/${encodeURIComponent(username)}/`;
    }

    function render(threads) {
        if (!threads || threads.length === 0) {
            root.innerHTML =
                '<p class="messages-empty">No mutual friends yet. Follow someone and ask them to follow you back to start messaging.</p>';
            return;
        }
        const items = threads.map((row) => {
            const unread = Number(row.unread_count) > 0;
            const unreadDot = unread
                ? `<span class="thread-unread-dot" aria-label="${esc(row.unread_count)} unread"></span>`
                : '';
            const linkClass = unread ? 'thread-link thread-link--unread' : 'thread-link';
            let body;
            if (row.has_last && row.last_preview) {
                body = `<span class="thread-link-preview">${esc(row.last_preview)}</span>
                        <span class="thread-link-meta">${esc(row.last_at)}</span>`;
            } else {
                body =
                    '<span class="thread-link-preview muted">No messages yet — say hi.</span>';
            }
            return `<li>
                    <a href="${esc(threadHref(row.username))}" class="${linkClass}">
                        <span class="thread-link-top">
                            <span class="thread-link-user">${esc(row.username)}</span>
                            ${unreadDot}
                        </span>
                        ${body}
                    </a>
                </li>`;
        });
        root.innerHTML = `<ul class="thread-list">${items.join('')}</ul>`;
    }

    async function poll() {
        try {
            const res = await fetch(root.dataset.pollUrl, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
            });
            if (!res.ok) return;
            const data = await res.json();
            if (!Array.isArray(data.threads)) return;
            render(data.threads);
        } catch (_) {
            /* ignore network errors */
        }
    }

    poll();
    setInterval(poll, POLL_MS);
})();
