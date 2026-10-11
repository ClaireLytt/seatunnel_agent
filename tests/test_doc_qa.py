# -*- coding: utf-8 -*-
"""Doc Q&A: tokenization, BM25 retrieval, answers, LLM fallback, CLI, API."""

from __future__ import annotations

import json

from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.doc_qa import (
    BM25Index,
    Chunk,
    answer,
    build_corpus,
    get_index,
    tokenize,
)
from seatunnel_agent.llm import LLMResponse


class TestTokenize:
    def test_mixed_scripts(self):
        toks = tokenize("Jdbc sink 的批量写入 batch_size")
        assert "jdbc" in toks and "batch_size" in toks
        assert "批量" in toks  # CJK bigram

    def test_empty(self):
        assert tokenize("") == []


class TestCorpusAndSearch:
    def test_connector_docs_always_indexed(self):
        chunks = build_corpus(docs_dir=None)
        sources = {c.source for c in chunks}
        assert any(s.startswith("connector:") for s in sources)

    def test_project_docs_included(self):
        chunks = build_corpus("docs")
        assert any(c.source.startswith("docs") for c in chunks)

    def test_search_finds_jdbc(self):
        index = get_index(None)
        hits = index.search("Jdbc sink url driver 参数", k=3)
        assert hits and any("connector:" in c.source for c, _ in hits)
        top = hits[0][0]
        assert "jdbc" in top.title.lower() or "jdbc" in top.text.lower()

    def test_search_no_hit(self):
        index = BM25Index([Chunk(source="s", title="t", text="hello world")])
        assert index.search("量子引力波动方程") == []


class TestAnswer:
    def test_extractive_with_citations(self):
        result = answer("Kafka source 怎么配置 topic", get_index(None),
                        lang="zh")
        assert "文档问答" in result["markdown"]
        assert "来源" in result["markdown"]
        assert result["hits"]

    def test_no_hit_message(self):
        index = BM25Index([Chunk(source="s", title="t", text="abc")])
        result = answer("xyzzy quux", index, lang="en")
        assert "No matching passage" in result["markdown"]
        assert result["hits"] == []

    def test_llm_synthesis_grounded(self):
        def factory(_s):
            class C:
                def chat(self, system, messages):
                    assert "EXCERPTS" in messages[0]["content"]
                    return LLMResponse(wants_tool_use=False, tool_calls=[],
                                       thinking_text="",
                                       reply_text="配 batch_size 即可 [1]",
                                       raw_content=None, usage={})
            return C()
        result = answer("Jdbc 批量写入", get_index(None), use_llm=True,
                        client_factory=factory)
        assert "batch_size 即可 [1]" in result["markdown"]
        assert "来源" in result["markdown"]  # citations kept

    def test_llm_failure_falls_back(self):
        def factory(_s):
            raise RuntimeError("no key")
        result = answer("Jdbc 批量写入", get_index(None), use_llm=True,
                        client_factory=factory)
        assert "LLM 综合失败" in result["markdown"]
        assert "相关片段" in result["markdown"]


class TestCliAndApi:
    def test_cli_markdown(self):
        r = CliRunner().invoke(cli, ["docqa", "Jdbc sink 参数", "--docs",
                                     "does-not-exist"])
        assert r.exit_code == 0, r.output
        assert "文档问答" in r.output

    def test_cli_json(self):
        r = CliRunner().invoke(cli, ["docqa", "Kafka topic", "-F", "json",
                                     "--docs", "does-not-exist"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["hits"]

    def test_api(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.doc_qa.api import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/api/docqa/ask",
                           json={"question": "Jdbc url", "lang": "en"})
        assert resp.status_code == 200
        assert resp.json()["hits"]
        assert client.get("/api/docqa/health").json() == {
            "status": "ok", "agent": "doc_qa"}

    def test_manifest_registered(self):
        from seatunnel_agent.registry import discover
        names = {m.name for m in discover()}
        assert "doc_qa" in names
