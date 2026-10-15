// tab_fill.js — Press Tab on an empty input to fill in the placeholder value
() => {
    if (document._tabFillReady) return;
    document._tabFillReady = true;
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Tab') return;
        var el = e.target;
        if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') return;
        if (el.value.trim() !== '' || !el.placeholder) return;
        e.preventDefault();
        var proto = el.tagName === 'TEXTAREA'
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
        var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(el, el.placeholder);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    });
}
