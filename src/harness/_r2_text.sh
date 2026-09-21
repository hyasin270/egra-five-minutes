#!/bin/bash
cd "$(dirname "$0")/.."
for m in openai/gpt-5-mini anthropic/claude-sonnet-5 google/gemini-3-flash-preview deepseek/deepseek-v3.2; do
  echo "=== text $m"; uv run --with requests --with pandas python harness/10_window_scorers.py text "$m" 40 2>&1 | grep -v "Installed\|Warning\|stddev" | grep "SUMMARY\|  orf\|  idwrd" | tail -4
done
for m in openai/gpt-5-mini anthropic/claude-sonnet-5 google/gemini-3-flash-preview google/gemini-2.5-flash-lite deepseek/deepseek-v3.2; do
  echo "=== comprehension $m"; uv run --with requests --with pandas python harness/11_comprehension_grade.py "$m" 100 2>&1 | grep "SUMMARY"
done; echo TEXT_CHAIN_DONE
