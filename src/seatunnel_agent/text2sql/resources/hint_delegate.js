// hint_delegate.js — Clickable hint cards (event delegation — works after language switch)
() => {
    if (document._hintDelegated) return;
    document._hintDelegated = true;
    document.addEventListener('click', e => {
        const card = e.target.closest('.st-hint-card');
        if (!card) return;
        const ta = document.querySelector('.st-input textarea');
        if (ta) {
            const nativeSetter = Object.getOwnPropertyDescriptor(
                HTMLTextAreaElement.prototype, 'value').set;
            nativeSetter.call(ta, card.textContent.trim());
            ta.dispatchEvent(new Event('input', {bubbles: true}));
        }
    });
}
