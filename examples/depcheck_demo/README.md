# Dependency Health demo

`requirements.txt` carries deliberate issues: an unpinned dep, conflicting
specs for `click`, and a package that is not installed.

```bash
seatunnel-agent depcheck --path examples/depcheck_demo
seatunnel-agent depcheck --path examples/depcheck_demo --fail-on high  # exit 1
seatunnel-agent depcheck --path . -F json      # check this project itself
```
