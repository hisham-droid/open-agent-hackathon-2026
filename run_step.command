#!/bin/bash
# Helper so Claude can run steps on this Mac by double-clicking. Runs .step.sh, output goes to .cmd_log.txt
cd "$(dirname "$0")"
bash ./.step.sh > .cmd_log.txt 2>&1
echo "=== finished $(date) ===" >> .cmd_log.txt
