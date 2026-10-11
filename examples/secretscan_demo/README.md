# Secret Scan demo

All credentials here are **deliberately fake** (the AWS pair is Amazon's
official documentation example). Expected: 4 high / 4 medium / 1 low.

```bash
seatunnel-agent secretscan examples/secretscan_demo
seatunnel-agent secretscan examples/secretscan_demo --fail-on high   # exit 1
seatunnel-agent secretscan --text 'password = "hunter2-prod"' -F json
```

Suppression: add `secretscan:ignore` to a line, or a `.secretscan.yaml`
with `ignore_rules: [...]` / `ignore_paths: ["glob", ...]` at the scan root.
