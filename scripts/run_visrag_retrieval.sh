#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISRAG_DIR="${VISRAG_DIR:-$ROOT_DIR/visrag}"
MODEL_PATH="${MODEL_PATH:-openbmb/VisRAG-Ret}"
# PPT default = 4 datasets. Set DATASETS=ArxivQA,ChartQA,MP-DocVQA,InfoVQA,PlotQA,SlideVQA for full 6-dataset paper run.
DATASETS="${DATASETS:-InfoVQA,ChartQA,MP-DocVQA,SlideVQA}"
MAX_Q_LEN="${MAX_Q_LEN:-512}"
MAX_P_LEN="${MAX_P_LEN:-2048}"
PER_DEV_BATCH_SIZE="${PER_DEV_BATCH_SIZE:-16}"
GPUS_PER_NODE="${GPUS_PER_NODE:-1}"
POOLING="${POOLING:-wmean}"
ATTENTION="${ATTENTION:-causal}"

cd "$VISRAG_DIR"
exec bash visrag_scripts/eval_retriever/eval.sh \
  "$MAX_Q_LEN" "$MAX_P_LEN" "$PER_DEV_BATCH_SIZE" "$GPUS_PER_NODE" \
  "$POOLING" "$ATTENTION" "$DATASETS" "$MODEL_PATH"
