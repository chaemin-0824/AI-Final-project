#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISRAG_DIR="${VISRAG_DIR:-$ROOT_DIR/visrag}"
MODEL_NAME="${MODEL_NAME:-gpt4o}"
MODEL_PATH="${MODEL_PATH:-gpt-4o}"
DATASET_NAME="${DATASET_NAME:-ArxivQA}"
DATASET_PATH="${DATASET_PATH:-openbmb/VisRAG-Ret-Test-${DATASET_NAME}}"
RANK="${RANK:-0}"
WORLD_SIZE="${WORLD_SIZE:-1}"
TOPK="${TOPK:-1}"
TASK_TYPE="${TASK_TYPE:-multi_image}"
RESULTS_ROOT_DIR="${RESULTS_ROOT_DIR:-$ROOT_DIR/results/visrag_retrieval}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/results/visrag_generation}"

cd "$VISRAG_DIR"
args=(
  python visrag_scripts/generate/generate.py
  --model_name "$MODEL_NAME"
  --model_name_or_path "$MODEL_PATH"
  --dataset_name "$DATASET_NAME"
  --dataset_name_or_path "$DATASET_PATH"
  --rank "$RANK"
  --world_size "$WORLD_SIZE"
  --topk "$TOPK"
  --results_root_dir "$RESULTS_ROOT_DIR"
  --task_type "$TASK_TYPE"
  --output_dir "$OUTPUT_DIR"
)

if [[ "$TASK_TYPE" == "page_concatenation" ]]; then
  args+=(--concatenate_type "${CONCATENATE_TYPE:-vertical}")
fi
if [[ "$MODEL_NAME" == "gpt4o" ]]; then
  args+=(--openai_api_key "${OPENAI_API_KEY:?OPENAI_API_KEY is required for gpt4o}")
fi

exec "${args[@]}"
