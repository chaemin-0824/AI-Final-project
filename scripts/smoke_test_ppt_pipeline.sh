#!/usr/bin/env bash
# End-to-end smoke test for the PPT-format pipeline.
#
# Purpose:
#   Validate that all stages (manifest dry-run -> v12 generation dry-run -> PPT exporter)
#   wire together correctly on the 4 PPT datasets without spending any Upstage / GPU /
#   VLM budget. Successful run leaves a populated `results/ppt_format/` directory.
#
# Required env: a tmp HF cache so HuggingFace dataset loading does not lock against the
#               sandbox-protected default cache.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
CACHE_DIR="${HF_CACHE_DIR:-/tmp/hf_cache}"
SMOKE_LIMIT="${SMOKE_LIMIT:-2}"
SMOKE_TOPK="${SMOKE_TOPK:-1}"
DATASETS=(InfoVQA ChartQA MP-DocVQA SlideVQA)
PARSE_CACHE="data/parsed/ChartQA_sample.jsonl"
OUT_DIR="results/v12_on_visrag/smoke"
mkdir -p "$OUT_DIR" results/ppt_format

if [[ ! -s "$PARSE_CACHE" ]]; then
  echo "Missing sample parse cache: $PARSE_CACHE" >&2
  exit 1
fi

V12_ARGS=()
for DATASET in "${DATASETS[@]}"; do
  for MODE in image_only parsed_text_only parsed_visual; do
    OUT="${OUT_DIR}/${DATASET}_${MODE}_top${SMOKE_TOPK}.json"
    CMD=("$PYTHON" benchmark/v12_on_visrag.py
         --dataset "$DATASET"
         --cache-dir "$CACHE_DIR"
         --oracle
         --topk "$SMOKE_TOPK"
         --limit "$SMOKE_LIMIT"
         --mode "$MODE"
         --generator-backend qwen2vl7b_bnb4
         --output "$OUT"
         --dry-run)
    if [[ "$MODE" != "image_only" ]]; then
      CMD+=(--parse-cache "$PARSE_CACHE")
    fi
    echo "==> ${CMD[*]}"
    "${CMD[@]}"
    V12_ARGS+=(--v12-json "$OUT")
  done
done

echo "==> benchmark/ppt_table_exporter.py"
"$PYTHON" benchmark/ppt_table_exporter.py \
  "${V12_ARGS[@]}" \
  --output-markdown results/ppt_format/smoke_results_table.md \
  --output-csv results/ppt_format/smoke_results_table.csv \
  --output-json results/ppt_format/smoke_results_table.json

echo "smoke test complete."
