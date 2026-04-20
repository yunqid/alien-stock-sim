const POLL_INTERVAL_MS = 3000;
document.addEventListener('DOMContentLoaded', () => {
    const bubbleList = document.querySelector('.msg-bubble-list');
    const emptyItem = bubbleList.querySelector('.messages-empty');

    function getLastMessageId() {
        const ids = [...bubbleList.querySelectorAll('[data-msg-id]')]
            .map(el => parseInt(el.getAttribute('data-msg-id')))
            .filter(n => !isNaN(n));
        return ids.length ? Math.max(...ids) : null;
    }

    function appendMessage(msg) {
        if (emptyItem) emptyItem.remove();

        const li = document.createElement('li');
        li.className = 'msg-bubble ' + (msg.is_mine ? 'msg-bubble--mine' : 'msg-bubble--theirs');
        li.setAttribute('data-msg-id', msg.id);

        // textContent to prevent xss
        const bodyText = document.createTextNode(msg.body);
        const meta = document.createElement('span');
        meta.className = 'msg-meta';
        meta.textContent = msg.created_at;

        li.appendChild(bodyText);
        li.appendChild(meta);
        bubbleList.appendChild(li);
        li.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }

    async function pollMessages() {
        const lastId = getLastMessageId();

        //building the URL safely
        let url = `/messages/${encodeURIComponent(THREAD_OTHER_USERNAME)}/poll/`;
        if (lastId !== null) url += `?after_id=${lastId}`;

        try {
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();
            for (const msg of data.messages) {
                appendMessage(msg);
            }
        } catch (_) {
            //just ignore catch, it'll repoll in 3 seconds anyway
        }
    }

    setInterval(pollMessages, POLL_INTERVAL_MS);
});