# LLM Cost demo

`llm_usage_sample.jsonl` — 14 days of synthetic LLM calls across three
models (2026-09-18 … 2026-10-01) with a cost spike on **2026-09-29** and one
unpriced model (`my-private-llm`). `pricing.yaml` shows how to price it and
override a builtin entry.

```bash
# the fixture uses fixed dates — pass a window large enough to include them
seatunnel-agent llmcost --days 3650 --usage-path examples/llmcost_demo/llm_usage_sample.jsonl

# with the pricing override (prices my-private-llm, re-prices deepseek-chat)
seatunnel-agent llmcost --days 3650 --usage-path examples/llmcost_demo/llm_usage_sample.jsonl \
  --pricing examples/llmcost_demo/pricing.yaml

# CI budget gate
seatunnel-agent llmcost --days 3650 --usage-path examples/llmcost_demo/llm_usage_sample.jsonl \
  --budget 0.5 --fail-on budget
```
