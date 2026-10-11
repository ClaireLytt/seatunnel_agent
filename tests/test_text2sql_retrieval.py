"""Tests for hybrid retrieval (M3): BM25, fusion, the optional vector
channel with cache, the prompt context-rot guard, and the bench gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.text2sql.retrieval import (
    BM25,
    HybridRetriever,
    _doc_tokens,
    schema_hash,
    table_document,
)
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

_FIXTURES = Path(__file__).parent / "fixtures"
_BENCH_DDL = _FIXTURES / "t2s_bench_schema.sql"
_BENCH_FILE = _FIXTURES / "t2s_retrieval_bench.jsonl"


@pytest.fixture(scope="module")
def bench_store() -> SchemaStore:
    return SchemaStore.from_file(_BENCH_DDL)


# ----------------------------------------------------------------------
# Tokenizer & BM25
# ----------------------------------------------------------------------


def test_doc_tokens_snake_case_and_bigrams() -> None:
    tokens = _doc_tokens("dwd_trade_order_di 交易订单")
    assert "dwd_trade_order_di" in tokens
    assert "trade" in tokens and "order" in tokens  # snake_case parts
    assert "交易" in tokens and "订单" in tokens      # CJK bigrams
    assert "易订" in tokens                           # sliding window


def test_bm25_ranks_relevant_doc_higher() -> None:
    docs = [
        _doc_tokens("交易订单明细 order_id 实付金额"),
        _doc_tokens("仓库维表 warehouse 库容"),
        _doc_tokens("用户登录日志 login ip"),
    ]
    bm = BM25(docs)
    scores = bm.scores(_doc_tokens("订单金额"))
    assert scores[0] > scores[1] and scores[0] > scores[2]


def test_bm25_empty() -> None:
    assert BM25([]).scores(["x"]) == []


# ----------------------------------------------------------------------
# Hybrid fusion
# ----------------------------------------------------------------------


def test_hybrid_scores_bounded_and_sorted(bench_store) -> None:
    r = HybridRetriever(bench_store)
    matches = r.rank("昨天各渠道的成交总额", top_n=5)
    assert matches
    assert matches[0].table.full_name == "dws.dws_trade_gmv_channel_df"
    scores = [m.score for m in matches]
    assert all(0 < s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_hybrid_deterministic(bench_store) -> None:
    r = HybridRetriever(bench_store)
    a = [(m.table.full_name, m.score) for m in r.rank("退款金额", top_n=5)]
    b = [(m.table.full_name, m.score) for m in r.rank("退款金额", top_n=5)]
    assert a == b


def test_weights_env_override(bench_store, monkeypatch) -> None:
    monkeypatch.setenv("T2S_RETRIEVAL_WEIGHTS", "1,0,0")
    kw_only = HybridRetriever(bench_store).rank("订单明细", top_n=3)
    monkeypatch.setenv("T2S_RETRIEVAL_WEIGHTS", "bogus")
    fallback = HybridRetriever(bench_store).rank("订单明细", top_n=3)
    assert kw_only and fallback  # bad value falls back to defaults, no crash


# ----------------------------------------------------------------------
# Vector channel (fake embedder — no network)
# ----------------------------------------------------------------------


def _pay_aware_embedder(texts: list[str]) -> list[list[float]]:
    """Toy semantic space: 付款/支付 on one axis, everything else on the other."""
    out = []
    for t in texts:
        hot = ("支付" in t) or ("付款" in t)
        out.append([1.0, 0.0] if hot else [0.0, 1.0])
    return out


def test_vector_channel_bridges_synonyms(bench_store, tmp_path) -> None:
    query = "用户都是通过什么方式付款的"  # keyword+bm25 both miss (bench)
    no_vec = HybridRetriever(bench_store, index_dir=tmp_path)
    names = [m.table.full_name for m in no_vec.rank(query, top_n=3)]
    assert "dwd.dwd_trade_pay_flow_di" not in names

    with_vec = HybridRetriever(
        bench_store, index_dir=tmp_path, embed_fn=_pay_aware_embedder,
    )
    names = [m.table.full_name for m in with_vec.rank(query, top_n=3)]
    assert "dwd.dwd_trade_pay_flow_di" in names


def test_vector_cache_persists(bench_store, tmp_path) -> None:
    calls = {"n": 0}

    def counting_embedder(texts):
        calls["n"] += 1
        return _pay_aware_embedder(texts)

    r1 = HybridRetriever(bench_store, index_dir=tmp_path, embed_fn=counting_embedder)
    r1.rank("付款方式", top_n=3)
    docs_calls = calls["n"]  # 1 for docs + 1 for the query
    assert docs_calls == 2
    assert list(tmp_path.glob("*.emb.json"))

    r2 = HybridRetriever(bench_store, index_dir=tmp_path, embed_fn=counting_embedder)
    r2.rank("付款方式", top_n=3)
    # doc vectors came from the cache: only one extra call (the query)
    assert calls["n"] == docs_calls + 1


def test_vector_failure_degrades(bench_store, tmp_path) -> None:
    def broken_embedder(texts):
        raise RuntimeError("quota exceeded")

    r = HybridRetriever(bench_store, index_dir=tmp_path, embed_fn=broken_embedder)
    matches = r.rank("订单明细", top_n=3)
    assert matches  # keyword+bm25 still work
    assert r._vector_failed is True


def test_schema_hash_stable_and_sensitive(bench_store) -> None:
    assert schema_hash(bench_store) == schema_hash(bench_store)
    small = SchemaStore(parse_ddl(
        "CREATE TABLE t(a string COMMENT 'x') COMMENT 'y';"
    ))
    assert schema_hash(small) != schema_hash(bench_store)
    assert table_document(small.tables[0]) == "t y a x"


# ----------------------------------------------------------------------
# match_tables tool integration
# ----------------------------------------------------------------------


def test_tool_match_tables_uses_hybrid(bench_store) -> None:
    from seatunnel_agent.text2sql.tools import Text2SQLRuntime, execute_text2sql_tool

    rt = Text2SQLRuntime(store=bench_store)
    out = json.loads(execute_text2sql_tool(
        "match_tables", {"query": "销量排名前十的商品"}, rt,
    ))
    assert out["count"] >= 1
    assert out["candidates"][0]["table"] == "dws.dws_item_sale_rank_df"
    # retriever is cached on the runtime and rebuilt on store swap
    first = rt.retriever
    assert rt.retriever is first
    rt.store = SchemaStore(parse_ddl("CREATE TABLE t(a string) COMMENT 'x';"))
    assert rt.retriever is not first


# ----------------------------------------------------------------------
# Prompt context-rot guard
# ----------------------------------------------------------------------


def test_prompt_full_injection_below_limit(bench_store) -> None:
    from seatunnel_agent.text2sql.prompts import build_text2sql_prompt

    prompt = build_text2sql_prompt(bench_store, "hive")  # 40 tables <= 50
    assert "仅允许查询以下表" in prompt
    assert "交易订单明细表" in prompt  # comments included


def test_prompt_names_only_above_limit(bench_store, monkeypatch) -> None:
    from seatunnel_agent.text2sql.prompts import build_text2sql_prompt

    monkeypatch.setenv("T2S_SCHEMA_PROMPT_LIMIT", "10")
    prompt = build_text2sql_prompt(bench_store, "hive")
    assert "names only" in prompt
    assert "MUST call" in prompt
    assert "dwd.dwd_trade_order_di" in prompt      # names are listed
    assert "交易订单明细表" not in prompt            # comments are not


# ----------------------------------------------------------------------
# Bench & regression gate
# ----------------------------------------------------------------------


def test_bench_load_and_validation(tmp_path) -> None:
    from seatunnel_agent.text2sql.bench import load_bench

    cases = load_bench(_BENCH_FILE)
    assert len(cases) >= 50
    assert all(c.question and c.tables for c in cases)

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"question": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="tables"):
        load_bench(bad)


def test_bench_gate_hybrid_not_worse(bench_store) -> None:
    """The PRD regression gate as a test: hybrid Top1/Top3 >= keyword."""
    from seatunnel_agent.text2sql.bench import load_bench, run_bench

    cases = load_bench(_BENCH_FILE)
    kw = run_bench(bench_store, cases, "keyword")
    hy = run_bench(bench_store, cases, "hybrid")
    assert hy.top3 >= kw.top3, (
        f"hybrid top3 {hy.top3_rate:.1%} < keyword {kw.top3_rate:.1%}: "
        f"{hy.misses}"
    )
    assert hy.top1 >= kw.top1
    assert kw.top3_rate >= 0.85  # the bench itself stays healthy


def test_cli_t2s_bench(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    result = CliRunner().invoke(cli, [
        "t2s-bench",
        "--ddl", str(_BENCH_DDL),
        "--bench", str(_BENCH_FILE),
        "--gate",
    ])
    assert result.exit_code == 0, result.output
    assert "keyword" in result.output and "hybrid" in result.output
    assert "门禁通过" in result.output
