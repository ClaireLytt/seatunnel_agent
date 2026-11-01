#!/bin/bash
# orchestration wrapper: retries each step
for step in sync_orders build_sales; do
  if [ -f "/locks/$step.lock" ]; then
    echo "skip $step"
  else
    bash "$step.sh" || exit 1
  fi
done
