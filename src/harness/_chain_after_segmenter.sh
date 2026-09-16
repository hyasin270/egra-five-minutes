#!/bin/bash
# Wait for segmenter pass 2, then run the English Whisper pass and maths grading over every segmented file, then re-score.
cd "$(dirname "$0")/.."
until ! pgrep -f 03b_segmenter_llm >/dev/null; do sleep 20; done
echo "segmenter done: $(ls harness/segments_llm/google_gemini-2.5-pro__* | wc -l) files"
until ! pgrep -f 08b_whisper_english_pass >/dev/null; do sleep 20; done
uv run --with requests python harness/08b_whisper_english_pass.py 400 2>&1 | grep -v Installed | tail -2
until ! pgrep -f 07_maths_grade >/dev/null; do sleep 20; done
uv run --with requests --with pandas python harness/07_maths_grade.py google/gemini-2.5-pro 400 2>&1 | grep -v Installed | tail -8
until ! pgrep -f 09_english_azure_speechace >/dev/null; do sleep 20; done
uv run --with requests --with pandas python harness/09_english_azure_speechace.py 400 2>&1 | grep -v "Installed\|Warning\|stddev" | tail -3
echo CHAIN_DONE
