# -*- coding: utf-8 -*-
"""SeaTunnel transform 字段级血缘（任务 #34）。"""

from __future__ import annotations

import pytest

from seatunnel_agent.data_lineage.seatunnel_loader import from_seatunnel_files

FIELD_MAPPER_CONF = """
env { job.mode = "BATCH" }
source {
  Jdbc {
    url = "jdbc:mysql://h:3306/db"
    table_name = "db.src_orders"
    result_table_name = "src_t"
  }
}
transform {
  FieldMapper {
    source_table_name = "src_t"
    result_table_name = "mapped"
    field_mapper {
      id = user_id
      name = user_name
    }
  }
}
sink {
  Jdbc {
    url = "jdbc:mysql://h:3306/dw"
    table_name = "dw.dst_orders"
    source_table_name = "mapped"
  }
}
"""

SQL_TRANSFORM_CONF = """
source {
  Jdbc {
    table_name = "db.src_orders"
    result_table_name = "src_t"
  }
}
transform {
  Sql {
    source_table_name = "src_t"
    result_table_name = "out_t"
    query = "select id, upper(name) as name_u from src_t"
  }
}
sink {
  Jdbc {
    table_name = "dw.dst_orders"
    source_table_name = "out_t"
  }
}
"""

NO_TRANSFORM_CONF = """
source {
  Jdbc { table_name = "db.a" }
}
sink {
  Jdbc { table_name = "dw.b" }
}
"""

NO_LINK_NAMES_CONF = """
source {
  Jdbc { table_name = "db.a" }
}
transform {
  FieldMapper {
    field_mapper {
      col1 = col1_out
    }
  }
}
sink {
  Jdbc { table_name = "dw.b" }
}
"""

CHAINED_TRANSFORM_CONF = """
source {
  Jdbc {
    table_name = "db.a"
    result_table_name = "t0"
  }
}
transform {
  FieldMapper {
    source_table_name = "t0"
    result_table_name = "t1"
    field_mapper { x = y }
  }
  FieldMapper {
    source_table_name = "t1"
    result_table_name = "t2"
    field_mapper { y = z }
  }
}
sink {
  Jdbc {
    table_name = "dw.b"
    source_table_name = "t2"
  }
}
"""

BROKEN_CONF = """
source {
  Jdbc { table_name = "db.a"
transform {{{ ??? garbage
"""


def _write(tmp_path, text):
    p = tmp_path / "job.conf"
    p.write_text(text, encoding="utf-8")
    return p


def test_field_mapper_produces_high_confidence_column_edges(tmp_path):
    graph, warnings = from_seatunnel_files([_write(tmp_path, FIELD_MAPPER_CONF)])
    assert warnings == []
    edges = graph.column_down.get(("db.src_orders", "id"), [])
    assert len(edges) == 1
    e = edges[0]
    assert (e.dst_table, e.dst_column) == ("dw.dst_orders", "user_id")
    assert e.source == "seatunnel"
    assert e.confidence == "high"
    names = graph.column_down.get(("db.src_orders", "name"), [])
    assert [(x.dst_table, x.dst_column) for x in names] == [("dw.dst_orders", "user_name")]
    # 表级 source×sink 行为不变
    assert "dw.dst_orders" in graph.downstream.get("db.src_orders", set())
    meta = graph.edge_meta[("db.src_orders", "dw.dst_orders")]
    assert meta.confidence == "medium"


def test_sql_transform_produces_medium_confidence_column_edges(tmp_path):
    pytest.importorskip("sqlglot")
    graph, warnings = from_seatunnel_files([_write(tmp_path, SQL_TRANSFORM_CONF)])
    assert warnings == []
    id_edges = graph.column_down.get(("db.src_orders", "id"), [])
    assert [(e.dst_table, e.dst_column) for e in id_edges] == [("dw.dst_orders", "id")]
    name_edges = graph.column_down.get(("db.src_orders", "name"), [])
    assert [(e.dst_table, e.dst_column) for e in name_edges] == [("dw.dst_orders", "name_u")]
    assert all(e.source == "seatunnel" and e.confidence == "medium"
               for e in id_edges + name_edges)


def test_no_transform_yields_no_column_edges(tmp_path):
    graph, warnings = from_seatunnel_files([_write(tmp_path, NO_TRANSFORM_CONF)])
    assert warnings == []
    assert graph.column_down == {}
    assert "dw.b" in graph.downstream.get("db.a", set())


def test_single_source_sink_infers_link_without_names(tmp_path):
    graph, _ = from_seatunnel_files([_write(tmp_path, NO_LINK_NAMES_CONF)])
    edges = graph.column_down.get(("db.a", "col1"), [])
    assert [(e.dst_table, e.dst_column) for e in edges] == [("dw.b", "col1_out")]


def test_chained_transforms_skip_column_inference(tmp_path):
    graph, warnings = from_seatunnel_files([_write(tmp_path, CHAINED_TRANSFORM_CONF)])
    assert warnings == []
    # 链式 transform 无法可靠推断，只保留表级血缘
    assert graph.column_down == {}
    assert "dw.b" in graph.downstream.get("db.a", set())


def test_broken_config_does_not_raise(tmp_path):
    graph, _ = from_seatunnel_files([_write(tmp_path, BROKEN_CONF)])
    assert graph.column_down == {}


INLINE_KV_CONF = """
source {
  Jdbc { table_name = "db.a", result_table_name = "t0" }
}
transform {
  FieldMapper {
    source_table_name = t0, result_table_name = t1
    field_mapper { x = y }
  }
}
sink {
  Jdbc { table_name = "dw.b", source_table_name = "t1" }
}
"""

ARRAY_TABLES_CONF = """
source {
  Jdbc {
    tables = ["db.a", "db.b"]
  }
}
sink {
  Jdbc { table_name = "dw.c" }
}
"""

DASH_FIELD_MAPPER_CONF = """
source {
  Jdbc {
    table_name = "db.a"
    result_table_name = "t0"
  }
}
transform {
  FieldMapper {
    source_table_name = "t0"
    result_table_name = "t1"
    field_mapper {
      order-id = order_id
    }
  }
}
sink {
  Jdbc { table_name = "dw.b", source_table_name = "t1" }
}
"""

AMBIGUOUS_RESULT_CONF = """
source {
  Jdbc { table_name = "db.a", result_table_name = "t0" }
  Jdbc { table_name = "db.b", result_table_name = "t0" }
}
transform {
  FieldMapper {
    source_table_name = "t0"
    result_table_name = "t1"
    field_mapper { x = y }
  }
}
sink {
  Jdbc { table_name = "dw.c", source_table_name = "t1" }
}
"""


def test_same_line_multiple_kv_pairs_all_parsed(tmp_path):
    """同一行多对 k=v（HOCON 合法）时第二对起也要被解析到。"""
    graph, warnings = from_seatunnel_files([_write(tmp_path, INLINE_KV_CONF)])
    assert warnings == []
    edges = graph.column_down.get(("db.a", "x"), [])
    assert [(e.dst_table, e.dst_column) for e in edges] == [("dw.b", "y")]


def test_array_table_values_parsed(tmp_path):
    graph, warnings = from_seatunnel_files([_write(tmp_path, ARRAY_TABLES_CONF)])
    assert warnings == []
    assert "db.a" in graph.nodes and "db.b" in graph.nodes
    assert not any("[" in n or '"' in n for n in graph.nodes)
    assert "dw.c" in graph.downstream.get("db.a", set())
    assert "dw.c" in graph.downstream.get("db.b", set())


def test_field_mapper_keeps_dash_in_column_names(tmp_path):
    """FieldMapper 的 key 是列名，不应被 key 规范化把 - 改成 _。"""
    graph, warnings = from_seatunnel_files([_write(tmp_path, DASH_FIELD_MAPPER_CONF)])
    assert warnings == []
    edges = graph.column_down.get(("db.a", "order-id"), [])
    assert [(e.dst_table, e.dst_column) for e in edges] == [("dw.b", "order_id")]
    assert ("db.a", "order_id") not in graph.column_down


def test_ambiguous_result_table_name_skips_column_lineage(tmp_path):
    """同一 result_table_name 对应多张物理表时保守跳过列级血缘，表级不受影响。"""
    graph, warnings = from_seatunnel_files([_write(tmp_path, AMBIGUOUS_RESULT_CONF)])
    assert warnings == []
    assert graph.column_down == {}
    assert "dw.c" in graph.downstream.get("db.a", set())
    assert "dw.c" in graph.downstream.get("db.b", set())
