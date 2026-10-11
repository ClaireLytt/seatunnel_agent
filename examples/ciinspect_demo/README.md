# CI Log Triage demo

Two fabricated failed-job logs (shared `ConnectionError` root cause clusters
across both jobs) and `runs.json` with a flaky `tests` workflow (same commit
`abc1234` both passed and failed) and a `lint` duration spike (95s vs ~40s
median).

```bash
seatunnel-agent ciinspect examples/ciinspect_demo/job_tests.log \
  examples/ciinspect_demo/job_lint.log --runs examples/ciinspect_demo/runs.json

seatunnel-agent ciinspect --runs examples/ciinspect_demo/runs.json --fail-on flaky  # exit 1

# live metadata from GitHub (needs gh auth)
seatunnel-agent ciinspect --gh owner/repo --limit 30
```
