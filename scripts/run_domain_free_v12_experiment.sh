#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
# PPT default = 4 datasets matching docs/VisRAG Multi Page Compression.pptx
DATASETS_CSV="${DATASETS:-InfoVQA,ChartQA,MP-DocVQA,SlideVQA}"
LIMIT_ARG=()
if [[ -n "${LIMIT:-}" ]]; then
  LIMIT_ARG=(--limit "$LIMIT")
fi
TOPK="${TOPK:-1}"
DRY_RUN="${DRY_RUN:-0}"
PARSE_WITH_UPSTAGE="${PARSE_WITH_UPSTAGE:-0}"
USE_ORACLE="${USE_ORACLE:-0}"
GENERATOR_BACKEND="${GENERATOR_BACKEND:-minicpmv26}"
MODEL="${MODEL:-}"

IFS=',' read -r -a DATASET_LIST <<< "$DATASETS_CSV"
SUMMARY_ARGS=()

for DATASET in "${DATASET_LIST[@]}"; do
  PARSE_CACHE="data/parsed/${DATASET}_upstage.jsonl"
  if [[ ! -s "$PARSE_CACHE" ]]; then
    if [[ "$PARSE_WITH_UPSTAGE" == "1" ]]; then
      "$PYTHON" scripts/parse_visrag_with_upstage.py --dataset "$DATASET" "${LIMIT_ARG[@]}" --output "$PARSE_CACHE"
    else
      echo "Missing parse cache: $PARSE_CACHE" >&2
      echo "Set PARSE_WITH_UPSTAGE=1 to create it, or provide cache manually." >&2
      exit 1
    fi
  fi

  TREC="results/parsed_text_retrieval/${DATASET}/test.trec"
  "$PYTHON" scripts/run_parsed_text_retrieval.py \
    --dataset "$DATASET" \
    --parse-cache "$PARSE_CACHE" \
    --topk 10 \
    "${LIMIT_ARG[@]}" \
    --output "$TREC"

  "$PYTHON" scripts/evaluate_retrieval.py \
    --dataset "$DATASET" \
    --trec "$TREC" \
    --k 10 \
    --output "results/parsed_text_retrieval/${DATASET}/metrics.json"

  for MODE in image_only parsed_text_only parsed_visual; do
    OUT="results/v12_on_visrag/${DATASET}_${MODE}_top${TOPK}.json"
    CMD=("$PYTHON" benchmark/v12_on_visrag.py --dataset "$DATASET" --topk "$TOPK" "${LIMIT_ARG[@]}" --mode "$MODE" --generator-backend "$GENERATOR_BACKEND" --output "$OUT")
    if [[ -n "$MODEL" ]]; then
      CMD+=(--model "$MODEL")
    fi
    if [[ "$USE_ORACLE" == "1" ]]; then
      CMD+=(--oracle)
    else
      CMD+=(--trec "$TREC")
    fi
    if [[ "$MODE" != "image_only" ]]; then
      CMD+=(--parse-cache "$PARSE_CACHE")
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
      CMD+=(--dry-run)
    fi
    "${CMD[@]}"
    SUMMARY_ARGS+=(--v12-json "$OUT")
  done
done

"$PYTHON" benchmark/compare_results.py "${SUMMARY_ARGS[@]}" --output results/domain_free_v12_summary.json
