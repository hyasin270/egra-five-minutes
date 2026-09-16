#!/bin/bash
cd "$(dirname "$0")/.."
for spec in "google/gemini-2.5-flash 40" "google/gemini-3.8-flash 40" "google/gemini-3.5-flash-lite 40" "google/gemini-3.1-pro-preview 40" "openai/gpt-audio-mini 40" "xiaomi/mimo-v2.5 40" "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free 20" "openai/gpt-audio 20" "mistralai/voxtral-small-24b-2507 10"; do
  set -- $spec; echo "=== audio $1 n=$2"; uv run --with requests --with pandas python harness/10_window_scorers.py audio "$1" "$2" 2>&1 | grep -v "Installed\|Warning\|stddev"| grep "SUMMARY\|  orf\|  idwrd\|spent" | tail -4
done; echo AUDIO_CHAIN_DONE
