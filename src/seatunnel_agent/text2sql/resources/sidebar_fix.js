// sidebar_fix.js — Force sidebar column layout (skip Gradio input internals)
() => {
    function fixSidebar() {
        const sb = document.querySelector('.st-sidebar');
        if (!sb) return;
        sb.style.setProperty('display', 'flex', 'important');
        sb.style.setProperty('flex-direction', 'column', 'important');
        sb.style.setProperty('flex-wrap', 'nowrap', 'important');
        const allDivs = sb.querySelectorAll(':scope > div');
        for (const el of allDivs) {
            el.style.setProperty('width', '100%', 'important');
            el.style.setProperty('max-width', '100%', 'important');
            el.style.setProperty('min-width', '0', 'important');
            el.style.setProperty('box-sizing', 'border-box', 'important');
            el.style.setProperty('flex-shrink', '0', 'important');
        }
    }
    fixSidebar();
    setTimeout(fixSidebar, 200);
    setTimeout(fixSidebar, 1000);
    let tid;
    new MutationObserver(() => {
        clearTimeout(tid);
        tid = setTimeout(fixSidebar, 80);
    }).observe(document.body, {childList: true, subtree: true});
}
