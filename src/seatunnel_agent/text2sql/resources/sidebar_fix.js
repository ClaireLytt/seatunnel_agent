// sidebar_fix.js — Force sidebar column layout (Gradio 6.x internal divs override CSS)
() => {
    function fixSidebar() {
        const sb = document.querySelector('.st-sidebar');
        if (!sb) return;
        sb.style.setProperty('display', 'flex', 'important');
        sb.style.setProperty('flex-direction', 'column', 'important');
        sb.style.setProperty('flex-wrap', 'nowrap', 'important');
        const allDivs = sb.querySelectorAll('div');
        for (const el of allDivs) {
            const cl = el.className || '';
            if (cl.includes('row') || cl.includes('st-filter-actions') ||
                cl.includes('st-filter-confirm') || cl.includes('st-action-row') ||
                cl.includes('st-rename-row') || cl.includes('st-topbar')) continue;
            if (el.closest('.st-table-filter') && el.classList.contains('wrap')) {
                el.style.setProperty('flex-direction', 'column', 'important');
                el.style.setProperty('flex-wrap', 'nowrap', 'important');
                continue;
            }
            const cls = String(cl);
            if (cls.includes('dropdown') || cls.includes('listbox') ||
                cls.includes('option') || cls.includes('wrap-inner') ||
                cls.includes('secondary-wrap') || cls.includes('icon-wrap') ||
                cls.includes('input-wrap') ||
                el.closest('ul') || el.tagName === 'LI' ||
                el.querySelector('svg[class*="dropdown-arrow"]')) continue;
            el.style.setProperty('display', 'flex', 'important');
            el.style.setProperty('flex-direction', 'column', 'important');
            el.style.setProperty('flex-wrap', 'nowrap', 'important');
            el.style.setProperty('width', '100%', 'important');
            el.style.setProperty('max-width', '100%', 'important');
            el.style.setProperty('min-width', '0', 'important');
        }
        sb.querySelectorAll('.st-filter-accordion').forEach(acc => {
            acc.querySelectorAll('*').forEach(el => {
                const cl = el.className || '';
                if (typeof cl === 'string' && cl.includes('label-wrap')) {
                    el.style.setProperty('padding', '4px 8px', 'important');
                    el.style.setProperty('min-height', '0', 'important');
                    el.style.setProperty('font-size', '12px', 'important');
                    el.style.setProperty('line-height', '1.3', 'important');
                    el.style.setProperty('background', '#f9fafb', 'important');
                    el.style.setProperty('border', 'none', 'important');
                    el.style.setProperty('box-shadow', 'none', 'important');
                    el.style.setProperty('gap', '4px', 'important');
                    el.querySelectorAll('span').forEach(sp => {
                        sp.style.setProperty('font-size', '12px', 'important');
                        sp.style.setProperty('font-weight', '500', 'important');
                        sp.style.setProperty('line-height', '1.3', 'important');
                    });
                }
                if (typeof cl === 'string' && cl.includes('icon') && el.tagName === 'SPAN') {
                    el.style.setProperty('font-size', '10px', 'important');
                }
            });
            acc.querySelectorAll('button').forEach(btn => {
                btn.style.setProperty('padding', '4px 8px', 'important');
                btn.style.setProperty('min-height', '0', 'important');
                btn.style.setProperty('font-size', '12px', 'important');
                btn.style.setProperty('line-height', '1.3', 'important');
                btn.style.setProperty('background', '#f9fafb', 'important');
                btn.style.setProperty('border', 'none', 'important');
                btn.style.setProperty('box-shadow', 'none', 'important');
                btn.style.setProperty('gap', '4px', 'important');
                btn.querySelectorAll('span').forEach(sp => {
                    sp.style.setProperty('font-size', '12px', 'important');
                    sp.style.setProperty('font-weight', '500', 'important');
                    sp.style.setProperty('line-height', '1.3', 'important');
                });
            });
        });
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
