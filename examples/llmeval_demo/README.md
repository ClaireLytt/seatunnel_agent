# LLM Eval demo suites

Golden suites for the platform's LLM features. A case names an `agent`
(`raw_prompt`, `text2sql`, `sql_review`), its `input`, and deterministic
`expect` checks (`contains` / `icontains` / `not_contains` / `regex` /
`equals` / `sql_valid` / `json_valid`); `judge` checks are advisory and only
run with `--judge`.

```bash
# needs a configured LLM (.env or /settings)
seatunnel-agent llmeval examples/llmeval_demo/text2sql_golden.yaml

# CI gates
seatunnel-agent llmeval examples/llmeval_demo/sql_review_golden.yaml --fail-on fail
seatunnel-agent llmeval examples/llmeval_demo/text2sql_golden.yaml --fail-on regression

# machine-readable
seatunnel-agent llmeval examples/llmeval_demo/text2sql_golden.yaml -F json
```

Run history lands in `logs/llm_eval_runs.jsonl` (`LLM_EVAL_PATH` relocates,
`LLM_EVAL_LOG=0` disables); `--fail-on regression` compares against the
previous run of the same suite (pass→fail flips, or a score drop > 0.01).
