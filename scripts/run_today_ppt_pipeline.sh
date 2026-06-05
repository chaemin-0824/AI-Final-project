#!/usr/bin/env bash
# Today-mode pipeline: produce a complete PPT slide-10 layout table within ~3-5 hours
# on a single RTX 4060 (8 GB) using Qwen2-VL-7B + bitsandbytes NF4 and a 100-query
# oracle sample per dataset.
#
# Required env:
#   UPSTAGE_API_KEY  - for Upstage Document Parse (only gold pages of the first 100 queries)
#
# Optional env:
#   SAMPLE_LIMIT     - per-dataset query sample (default 100; set 0 for full)
#   GENERATOR_BACKEND - default qwen2vl7b_bnb4
#   TOPK             - top-k retrieved/gold pages used per query (default 1, PPT-aligned)
#   HF_CACHE_DIR     - default /tmp/hf_cache (avoids sandbox lock issues)
#
# What runs:
#   1) Upstage parse - only the gold corpus pages for the first SAMPLE_LIMIT queries
#      per dataset (cheap: ~SAMPLE_LIMIT pages × 4 datasets ≈ 400 calls total).
#   2) Skip BM25 retrieval - we use --oracle to give the generator the gold page,
#      isolating GENERATION method differences (image_only vs parsed_text_only vs parsed_visual).
#      Retrieval table can be measured separately later.
#   3) Qwen2-VL-7B + NF4 generation × 3 modes × 4 datasets.
#   4) PPT exporter -> markdown / csv / json table in results/ppt_format/.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
SAMPLE_LIMIT="${SAMPLE_LIMIT:-100}"
TOPK="${TOPK:-1}"
GENERATOR_BACKEND="${GENERATOR_BACKEND:-qwen2vl7b_bnb4}"
CACHE_DIR="${HF_CACHE_DIR:-/tmp/hf_cache}"
# Order: smallest images first so we catch issues early without burning hours.
# ChartQA: ~800x600 charts. MP-DocVQA/SlideVQA: full pages, ~1024x1320.
# InfoVQA: infographics up to 1024x6000+; the processor's max_pixels cap
# applied in benchmark/v12_on_visrag.py keeps these tractable on 8 GB GPU.
DATASETS=(ChartQA MP-DocVQA SlideVQA InfoVQA)
PARSED_DIR="data/parsed"
OUT_DIR="results/v12_on_visrag/today"
PPT_DIR="results/ppt_format"
mkdir -p "$PARSED_DIR" "$OUT_DIR" "$PPT_DIR"

LIMIT_FLAG=()
if [[ "$SAMPLE_LIMIT" != "0" ]]; then
  LIMIT_FLAG=(--limit "$SAMPLE_LIMIT")
fi

START_TS=$(date +%s)

# ---------------- Stage 1: Upstage parse (gold pages of first N queries) ----------------
# UPSTAGE_API_KEY is only required when a parse cache is missing. If all four
# first100 caches are present (e.g., on a fresh clone of the submitted bundle),
# Stages 2 and 3 can run without any API key.
for DATASET in "${DATASETS[@]}"; do
  PARSE_CACHE="${PARSED_DIR}/${DATASET}_first${SAMPLE_LIMIT}_qrels_upstage.jsonl"
  if [[ -s "$PARSE_CACHE" ]]; then
    echo "==> parse cache exists: $PARSE_CACHE  (skip)"
    continue
  fi
  if [[ -z "${UPSTAGE_API_KEY:-}" ]]; then
    echo "UPSTAGE_API_KEY required to parse $DATASET (no cache at $PARSE_CACHE)." >&2
    echo "Either export UPSTAGE_API_KEY=... or restore the cached JSONL." >&2
    exit 1
  fi
  echo "==> Upstage parse $DATASET first $SAMPLE_LIMIT qrels -> $PARSE_CACHE"
  "$PYTHON" scripts/parse_visrag_with_upstage.py \
    --dataset "$DATASET" \
    --cache-dir "$CACHE_DIR" \
    --qrels-for-first-queries "$SAMPLE_LIMIT" \
    --delay-sec 0.3 \
    --output "$PARSE_CACHE"
done

# ---------------- Stage 2: Generation x 3 modes x 4 datasets ----------------
EXPORTER_ARGS=()
for DATASET in "${DATASETS[@]}"; do
  PARSE_CACHE="${PARSED_DIR}/${DATASET}_first${SAMPLE_LIMIT}_qrels_upstage.jsonl"
  for MODE in image_only parsed_text_only parsed_visual; do
    OUT="${OUT_DIR}/${DATASET}_${MODE}_top${TOPK}_first${SAMPLE_LIMIT}.json"
    if [[ -s "$OUT" ]]; then
      echo "==> generation result exists: $OUT  (skip)"
      EXPORTER_ARGS+=(--v12-json "$OUT")
      continue
    fi
    CMD=("$PYTHON" benchmark/v12_on_visrag.py
         --dataset "$DATASET"
         --cache-dir "$CACHE_DIR"
         --oracle
         --topk "$TOPK"
         "${LIMIT_FLAG[@]}"
         --mode "$MODE"
         --generator-backend "$GENERATOR_BACKEND"
         --max-new-tokens 32
         --output "$OUT")
    if [[ "$MODE" != "image_only" ]]; then
      CMD+=(--parse-cache "$PARSE_CACHE")
    fi
    echo "==> ${CMD[*]}"
    "${CMD[@]}"
    EXPORTER_ARGS+=(--v12-json "$OUT")
  done
done

# ---------------- Stage 3: PPT layout exporter ----------------
echo "==> PPT exporter"
"$PYTHON" benchmark/ppt_table_exporter.py \
  "${EXPORTER_ARGS[@]}" \
  --output-markdown "${PPT_DIR}/today_results_table.md" \
  --output-csv "${PPT_DIR}/today_results_table.csv" \
  --output-json "${PPT_DIR}/today_results_table.json"

END_TS=$(date +%s)
echo "done. elapsed=$((END_TS - START_TS))s"
echo "table: ${PPT_DIR}/today_results_table.md"
