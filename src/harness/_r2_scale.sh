#!/bin/bash
cd "$(dirname "$0")/.."
until grep -q AUDIO_CHAIN_DONE harness/_r2_audio.log; do sleep 30; done
for spec in "google/gemini-3.8-flash 200" "google/gemini-3.1-pro-preview 80"; do
  set -- $spec; echo "=== scale audio $1 n=$2"; uv run --with requests --with pandas python harness/10_window_scorers.py audio "$1" "$2" 2>&1 | grep -v "Installed\|Warning\|stddev" | grep "SUMMARY\|  orf\|  idwrd" | tail -4
done; echo SCALE_DONE
