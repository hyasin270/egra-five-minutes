#!/bin/bash
cd "$(dirname "$0")/.."
for m in google/gemini-3-flash-preview openai/gpt-5-mini anthropic/claude-haiku-4.5 google/gemini-2.5-flash-lite; do
  echo "=== segmenter $m"; uv run --with requests --with pandas python harness/03b_segmenter_llm.py "$m" 25 2>&1 | grep "SUMMARY"
done
for m in anthropic/claude-sonnet-5 openai/gpt-5-mini google/gemini-3-flash-preview; do
  echo "=== maths $m"; uv run --with requests --with pandas python harness/07_maths_grade.py "$m" 40 2>&1 | grep "SUMMARY\|  wrdpblm\|  bleffcomp\|  numrep\|  idnummag\|  patterns"
done; echo SEG_MATHS_CHAIN_DONE
