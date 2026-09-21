// dl_inject.js — Inject CSV/Chart download buttons next to the copy icon
// in the last bot message. Uses MutationObserver with debounce.
() => {
    if (document._dlInjectInit) return;
    document._dlInjectInit = true;

    const MARKER = 'st-dl-injected';
    let timer = null;

    function injectButtons() {
        const chatbot = document.querySelector('.st-chatbot');
        if (!chatbot) return;

        chatbot.querySelectorAll('.' + MARKER).forEach(el => el.remove());

        const wrappers = chatbot.querySelectorAll('.icon-button-wrapper');
        if (!wrappers.length) return;
        const lastWrapper = wrappers[wrappers.length - 1];

        const csvDl = document.querySelector('#st-csv-dl button');
        const chartDl = document.querySelector('#st-chart-dl button');
        if (!csvDl && !chartDl) return;

        function makeBtn(label, targetBtn) {
            const btn = document.createElement('button');
            btn.className = MARKER;
            btn.textContent = label;
            btn.title = label;
            btn.style.cssText =
                'background:none;border:none;cursor:pointer;padding:2px 6px;' +
                'font-size:13px;color:var(--body-text-color-subdued,#666);' +
                'border-radius:4px;display:inline-flex;align-items:center;' +
                'transition:background .15s';
            btn.onmouseenter = () => { btn.style.background = 'var(--background-fill-secondary,#f0f0f0)'; };
            btn.onmouseleave = () => { btn.style.background = 'none'; };
            btn.onclick = (e) => { e.preventDefault(); e.stopPropagation(); targetBtn.click(); };
            return btn;
        }

        if (csvDl) lastWrapper.appendChild(makeBtn('📥 CSV', csvDl));
        if (chartDl) lastWrapper.appendChild(makeBtn('🖼️ Chart', chartDl));
    }

    function scheduleInject() {
        clearTimeout(timer);
        timer = setTimeout(injectButtons, 200);
    }

    // Initial injection after page loads
    setTimeout(injectButtons, 800);

    // Re-inject on chatbot DOM changes (debounced)
    const chatbot = document.querySelector('.st-chatbot');
    if (chatbot) {
        new MutationObserver(scheduleInject).observe(chatbot, { childList: true, subtree: true });
    }
}
