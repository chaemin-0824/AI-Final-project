# AI Algorithm Study: VisRAG vs v12 Benchmark Workspace

This workspace was prepared to compare OpenBMB VisRAG (arXiv:2410.10594) with the v12 architecture from `/home/chaemin/projects/paper_visual_rag`.

## PPT-aligned result format

The end goal is a result table that matches `docs/VisRAG Multi Page Compression.pptx` slide 10:

```
Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline
```

- `DocVQA` in the PPT == `MP-DocVQA` from `openbmb/VisRAG-Ret-Test-MP-DocVQA`.
- Default dataset subset is therefore `InfoVQA, ChartQA, MP-DocVQA, SlideVQA` (4 of the 6 VisRAG paper datasets).
- Generator default is **`Qwen/Qwen2-VL-7B-Instruct` loaded with bitsandbytes 4-bit (NF4)** — same family as the teammate PPT baseline (Qwen2-VL-7B), fits ~5-6 GB VRAM. Paper-aligned MiniCPM-V 2.6 and GPT-4o remain available via `--generator-backend minicpmv26 | gpt4o`.

## Quick start

```bash
cd "/home/chaemin/projects/AI algorithm study"
source .venv/bin/activate

# 0) Dry-run smoke test for the whole pipeline (no API/GPU required):
SMOKE_LIMIT=2 bash scripts/smoke_test_ppt_pipeline.sh

# 1) Inspect the 4 PPT datasets:
python scripts/prepare_visrag_datasets.py \
  --cache-dir /tmp/hf_cache \
  --output data/visrag_dataset_manifest.json

# 2) Build Upstage parse caches (per dataset, full corpus):
UPSTAGE_API_KEY=... python scripts/parse_visrag_with_upstage.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --output data/parsed/ChartQA_upstage.jsonl

# 3) BM25 parsed-text retrieval + MRR@10/Recall@10:
python scripts/run_parsed_text_retrieval.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --topk 10 --output results/parsed_text_retrieval/ChartQA/test.trec

python scripts/evaluate_retrieval.py \
  --dataset ChartQA --cache-dir /tmp/hf_cache \
  --trec results/parsed_text_retrieval/ChartQA/test.trec --k 10 \
  --output results/parsed_text_retrieval/ChartQA/metrics.json

# 4) v12-general generation in image_only / parsed_text_only / parsed_visual modes:
#    Default backend is Qwen2-VL-7B-Instruct + bitsandbytes NF4 (fits 8 GB GPU, matches teammate PPT baseline).
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

- `Baseline (순수 VisRAG)` — visual-only retrieval + visual-only generation (PPT baseline). Inside this repo this is the `image_only` mode of `benchmark/v12_on_visrag.py`, OR the official `visrag_scripts/generate/generate.py` output.
- `Parsed-Text Only (ablation)` — `parsed_text_only` mode.
- `Parsed-Visual RAG (v12-general)` — `parsed_visual` mode (ours).

Bridge-specific v12 components (chapter inference, damage history, etc.) are removed for this comparison; see `docs/domain_free_v12_experiment_design.md`.

## Reference docs

- `docs/visrag_v12_benchmark.md` — full procedure.
- `docs/domain_free_v12_experiment_design.md` — why bridge-v12 is replaced by v12-general here.
- `docs/paper_aligned_vlm_and_inputs.md` — generator / input format reasoning.
- `docs/experiment_contract_one_corpus_one_generator.md` — fixed components for fair comparison.
- `docs/VisRAG Multi Page Compression.pptx` — teammate's target result layout.
