# AI Algorithm Study: VisRAG vs Parsed-Visual RAG (PV-RAG)

This workspace was prepared to compare OpenBMB VisRAG (arXiv:2410.10594) with **Parsed-Visual RAG (PV-RAG)**, a domain-agnostic derivative of an internal RAG architecture in `/home/chaemin/projects/paper_visual_rag`.

## PPT-aligned result format

The end goal is a result table that matches `docs/VisRAG Multi Page Compression.pptx` slide 10:

```
Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline
```

- `DocVQA` in the PPT == `MP-DocVQA` from `openbmb/VisRAG-Ret-Test-MP-DocVQA`.
- Default dataset subset is therefore `InfoVQA, ChartQA, MP-DocVQA, SlideVQA` (4 of the 6 VisRAG paper datasets).
- Generator default is **`Qwen/Qwen2-VL-7B-Instruct` loaded with bitsandbytes 4-bit (NF4)** — same family as the teammate PPT baseline (Qwen2-VL-7B), fits ~5-6 GB VRAM. Paper-aligned MiniCPM-V 2.6 and GPT-4o remain available via `--generator-backend minicpmv26 | gpt4o`.

## Quick start (reproduce the PV-RAG result table)

```bash
cd "/home/chaemin/projects/AI algorithm study"
source .venv/bin/activate

# 0) Optional dry-run smoke test (archived; no API/GPU required).
SMOKE_LIMIT=2 bash backup/scripts/smoke_test_ppt_pipeline.sh

# 1) Inspect the 4 PPT datasets:
python scripts/prepare_visrag_datasets.py \
  --cache-dir /tmp/hf_cache \
  --output data/visrag_dataset_manifest.json

# 2) Build Upstage parse caches (per dataset, full corpus). The first100
#    caches needed for the submitted table are already shipped under
#    data/parsed/, so this step is only required to extend coverage.
UPSTAGE_API_KEY=... python scripts/parse_visrag_with_upstage.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --output data/parsed/ChartQA_upstage.jsonl

# 3) Optional: BM25 parsed-text retrieval + MRR@10/Recall@10.
python scripts/run_parsed_text_retrieval.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --topk 10 --output results/parsed_text_retrieval/ChartQA/test.trec

python scripts/evaluate_retrieval.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --trec results/parsed_text_retrieval/ChartQA/test.trec --k 10 \
  --output results/parsed_text_retrieval/ChartQA/metrics.json

# 4) PV-RAG generation in image_only / parsed_text_only / parsed_visual modes.
#    Default backend is Qwen2-VL-7B-Instruct + bitsandbytes NF4 (fits 8 GB GPU,
#    matches teammate PPT baseline).
DATASETS=InfoVQA,ChartQA,MP-DocVQA,SlideVQA \
bash scripts/run_domain_free_v12_experiment.sh

# To switch to paper-aligned MiniCPM-V 2.6 or GPT-4o:
# GENERATOR_BACKEND=minicpmv26 MODEL=openbmb/MiniCPM-V-2_6 bash scripts/run_domain_free_v12_experiment.sh
# GENERATOR_BACKEND=gpt4o      MODEL=gpt-4o                 bash scripts/run_domain_free_v12_experiment.sh

# 5) Render the PPT-format result table:
python benchmark/ppt_table_exporter.py \
  --v12-json results/v12_on_visrag/*_top1.json \
  --output-markdown results/ppt_format/results_table.md \
  --output-csv results/ppt_format/results_table.csv \
  --output-json results/ppt_format/results_table.json
```

For the official VisRAG retrieval+generation runs (separate GPU stack), use:

```bash
MODEL_PATH=openbmb/VisRAG-Ret GPUS_PER_NODE=1 bash scripts/run_visrag_retrieval.sh
DATASET_NAME=ChartQA TASK_TYPE=multi_image bash scripts/run_visrag_generation.sh
```

## Method naming

- `Baseline (순수 VisRAG)` — visual-only retrieval + visual-only generation (PPT baseline). In this repo this is the `image_only` mode of `benchmark/v12_on_visrag.py`, or the output of the official `visrag_scripts/generate/generate.py`.
- `Parsed-Text Only (ablation)` — `parsed_text_only` mode.
- **`Parsed-Visual RAG (PV-RAG)`** — `parsed_visual` mode (ours).

> Note on code names. The library files `benchmark/v12_on_visrag.py`, `backup/v12_port/`, etc. retain the original `v12` identifier from the source project's internal versioning. The published method name in the report and this README is **PV-RAG**; `v12` survives only as a file-path token.

Bridge-domain RAG components from the predecessor system (chapter inference, damage-history augmentation, etc.) are removed for this benchmark; the design rationale is in `backup/docs/domain_free_v12_experiment_design.md`.

## Deliverables

- `docs/report_v12_general_vs_visrag.docx` — academic-style technical report.
- `docs/VisRAG Multi Page Compression.pptx` — teammate's target result layout.
- `results/ppt_format/today_results_table.{md,csv,json}` — final PPT-layout table.
- `results/v12_on_visrag/today/*.json` — 12 underlying generation results (4 datasets × 3 modes).
- `data/parsed/*_first100_qrels_upstage.jsonl` — Upstage parse caches that ship with the submission (~3.7 MB) so the table can be reproduced without re-calling the Upstage API.

## Archived material

- `backup/docs/` — planning and design documents (`visrag_v12_benchmark.md`, `domain_free_v12_experiment_design.md`, `paper_aligned_vlm_and_inputs.md`, `experiment_contract_one_corpus_one_generator.md`, `plans/`).
- `backup/tests/` — pytest suite (16 unit tests).
- `backup/v12_port/` — bridge-domain RAG predecessor (not used by the PV-RAG pipeline).
- `backup/scripts/` — smoke test and bridge runner.
- `backup/results/`, `backup/logs/` — pilot, dryrun, and execution logs.
- `backup/README.md` — index of archived material.
