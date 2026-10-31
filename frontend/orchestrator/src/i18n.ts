import { initI18n } from '@shared/i18n'

// Copy carried over from the legacy Gradio page
// (seatunnel_agent/agents/ai/orchestrator/ui.py _I18N).
const resources = {
  en: {
    translation: {
      title: 'Agent Orchestrator',
      subtitle:
        'One chat entry for the whole platform — describe what you need ' +
        '(paste SQL / configs / DDL right in the message) and the LLM routes ' +
        'it to the right agents, chaining steps when needed.',
      chatPhTitle: '👋 What can I do?',
      chatPh:
        'Paste SQL / configs / DDL straight into the message — I route it to ' +
        'the right agent: review, dialect translation, impact analysis, skew ' +
        'check, formatting, config lint, schema drift, PII scan, test data…',
      chatPhChain: 'Steps chain automatically: “translate to Doris, then review the result”.',
      inputPh: 'e.g. Review this SQL and then format it: SELECT …',
      send: 'Send',
      newSession: 'New session',
      noKey: 'No LLM configured — suggestions only. Configure an API key on the Settings page.',
      working: '⏳ Routing & running agents…',
      home: 'Home',
      agentsAcc: 'Routable agents',
      colAgent: 'Agent',
      colPage: 'Page',
      colDesc: 'What it does',
      exReview: 'Try: SQL review',
      exChain: 'Try: translate + review',
      exPii: 'Try: PII scan',
      exReviewText:
        "Review this SQL: SELECT * FROM dwd_order_df a, dim_user_df b WHERE a.ds='2026-10-01'",
      exChainText:
        'Translate this Hive SQL to Doris, then review the result: ' +
        'SELECT city, collect_set(user_id) FROM t GROUP BY city',
      exPiiText:
        "Any sensitive columns in this DDL? CREATE TABLE u (phone STRING COMMENT 'mobile phone', " +
        "id_card STRING COMMENT 'national id')",
      exRealtime: 'Try: realtime health check',
      exRealtimeText:
        'Run a realtime health check: first diagnose the Kafka lag with ' +
        '{"group":"g-orders","topics":[{"topic":"orders","partitions":[' +
        '{"partition":0,"log_end_offset":1500000,"committed_offset":600000,' +
        '"consume_rate":300,"produce_rate":900}]}]} , then the Flink job with ' +
        '{"job":"sync-orders","operators":[{"name":"join-enrich",' +
        '"backpressure":0.86,"watermark_lag_ms":420000}],"restarts":2} , ' +
        'and summarize the causal chain between them.',
    },
  },
  zh: {
    translation: {
      title: '智能编排',
      subtitle:
        '全平台统一对话入口 — 描述你的需求(SQL / 配置 / DDL 直接贴在消息里),' +
        'LLM 自动路由到合适的 agent,需要时自动串联多步。',
      chatPhTitle: '👋 我能做什么?',
      chatPh:
        '把 SQL / 配置 / DDL 直接贴进消息,我会路由到合适的 agent:审查、' +
        '方言翻译、影响分析、倾斜检测、格式化、配置检查、Schema 漂移、' +
        'PII 扫描、测试造数…',
      chatPhChain: '支持多步串联:「翻译成 Doris,然后审查结果」。',
      inputPh: '例如:帮我审查这段 SQL 然后格式化:SELECT …',
      send: '发送',
      newSession: '新会话',
      noKey: '未配置 LLM — 仅能做关键词推荐。请到设置页配置 API key。',
      working: '⏳ 正在路由并执行 agent…',
      home: '首页',
      agentsAcc: '可路由的 agent',
      colAgent: 'Agent',
      colPage: '页面',
      colDesc: '说明',
      exReview: '示例:SQL 审查',
      exChain: '示例:翻译+审查',
      exPii: '示例:PII 扫描',
      exReviewText:
        "审查这段 SQL:SELECT * FROM dwd_order_df a, dim_user_df b WHERE a.ds='2026-10-01'",
      exChainText:
        '把这段 Hive SQL 翻译成 Doris,然后审查翻译结果:' +
        'SELECT city, collect_set(user_id) FROM t GROUP BY city',
      exPiiText:
        "这段 DDL 里有敏感字段吗?CREATE TABLE u (phone STRING COMMENT '手机号', " +
        "id_card STRING COMMENT '身份证')",
      exRealtime: '示例:实时体检',
      exRealtimeText:
        '做一次实时链路体检:先用这份快照诊断 Kafka 积压 ' +
        '{"group":"g-orders","topics":[{"topic":"orders","partitions":[' +
        '{"partition":0,"log_end_offset":1500000,"committed_offset":600000,' +
        '"consume_rate":300,"produce_rate":900}]}]} ,再用这份快照诊断 ' +
        'Flink 作业 {"job":"sync-orders","operators":[{"name":"join-enrich",' +
        '"backpressure":0.86,"watermark_lag_ms":420000}],"restarts":2} ,' +
        '最后总结两者之间的因果链。',
    },
  },
}

export default initI18n(resources)
