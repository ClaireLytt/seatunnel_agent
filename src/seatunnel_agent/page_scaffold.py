# -*- coding: utf-8 -*-
"""Shared scaffolding for the per-agent Gradio pages.

Every ``*_ui.py`` page repeats the same skeleton: an ``_I18N`` lookup, the
scroll-marker div, a title row with the 🏠 button, and the language/home/
stamp wiring around ``lang_pref``.  These helpers hold the single copy;
pages keep only their own strings, layout and callbacks.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import gradio as gr

from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
from .utils import normalize_lang


def make_page_t(i18n: dict[str, dict[str, str]]) -> Callable[[str, str], str]:
    """The pages' ``_t(lang, key)`` lookup over a page-local _I18N dict."""
    def _t(lang: str, key: str) -> str:
        return i18n[normalize_lang(lang)].get(key, key)
    return _t


def scroll_marker() -> None:
    """Marker div: body:has(.st-scroll-page) re-enables page scrolling."""
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')


def title_row(title_text: str) -> tuple[gr.Markdown, gr.Button]:
    """Standard page header: title markdown + the 🏠 home button."""
    with gr.Row():
        title_md = gr.Markdown(title_text)
        home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                             elem_classes=["st-home-btn"])
    return title_md, home_btn


def wire_page(app: gr.Blocks, home_btn: gr.Button,
              switch_lang: Callable[[str], Any],
              outputs: Sequence[Any]) -> None:
    """Shared tail wiring of every page: 🏠 → '/', body lang stamp, and
    the on-load language switch driven by the st-lang cookie."""
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(_lang_on_load, inputs=None, outputs=list(outputs))
