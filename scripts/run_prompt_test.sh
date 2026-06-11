#!/usr/bin/env bash
# Prompt-bias hypothesis test runner.
#
# Cells run (Upstage I+T tf457 prompt already exists from prior parsed_visual run):
#   - Upstage  I+T  image_first
#   - Qwen OCR I+T  tf457        (reproduce on local hardware)
#   - Qwen OCR I+T  image_first
#
# 4 datasets x 3 cells = 12 runs. Each ~100 samples.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/results/prompt_test"
LOG_DIR="$RESULTS/logs"
mkdir -p "$LOG_DIR"

LIMIT="${LIMIT:-100}"
DATASETS=(InfoVQA ChartQA MP-DocVQA SlideVQA)

# (mode, prompt)
CELLS=(
    "qwen_ocr_text_image tf457"
    "qwen_ocr_text_image image_first"
    "upstage_text_image image_first"
    "upstage_text_image tf457"
)

echo "=== prompt-test run start: $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
echo "limit=$LIMIT"

for cell in "${CELLS[@]}"; do
    mode="${cell% *}"
    prompt="${cell#* }"
    for ds in "${DATASETS[@]}"; do
        out="$RESULTS/${ds}_${mode}_${prompt}.json"
        if [ -f "$out" ]; then
            echo "[skip] $ds/$mode/$prompt (exists)"
            continue
        fi
        log="$LOG_DIR/${ds}_${mode}_${prompt}.log"
        echo "=== [$(date '+%H:%M:%S')] $ds / $mode / $prompt ==="
        python3 -m benchmark.experiment_prompt_test \
            --dataset "$ds" --mode "$mode" --prompt "$prompt" --limit "$LIMIT" \
            >"$log" 2>&1
        STATUS=$?
        if [ "$STATUS" -ne 0 ]; then
            echo "!!! FAILED $ds/$mode/$prompt (exit $STATUS) — see $log"
            tail -n 30 "$log"
            exit 1
        fi
        tail -n 4 "$log"
    done
done

echo "=== all prompt-test runs done: $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
python3 "$ROOT/benchmark/build_prompt_test_table.py"
