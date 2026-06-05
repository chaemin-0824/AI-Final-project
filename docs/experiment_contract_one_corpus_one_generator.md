# Experiment contract: one corpus, one generator

This file records the user decision for the fair VisRAG comparison.

## Fixed components

| Component | Fixed choice |
|---|---|
| Generator VLM (workspace default) | `Qwen2-VL-7B-Instruct-AWQ` (int4) — matches teammate PPT baseline; 8 GB GPU OK |
| Paper-aligned alternative | `MiniCPM-V 2.6` (`openbmb/MiniCPM-V-2_6`) — VisRAG paper main model |
| API fallback | `GPT-4o` — VisRAG paper API model |
| Dataset family | Official VisRAG benchmark HuggingFace datasets |
| Corpus source | One shared `corpus` split per dataset, e.g. `openbmb/VisRAG-Ret-Test-ChartQA` / `corpus` |
| Query source | Same `queries` split per dataset |
| Gold relevance | Same `qrels` split per dataset |
| Evaluation metric | VisRAG paper-style accuracy and retrieval MRR@10/Recall@10 |

Whichever generator is picked must be used identically across `image_only`, `parsed_text_only`, and `parsed_visual` rows so the experiment isolates evidence format, not model strength.

## Variable component

Only the evidence format changes:

| Mode | Evidence sent to the chosen VLM |
|---|---|
| `image_only` | retrieved page image(s) from the shared corpus |
| `parsed_text_only` | Upstage parsed text/table evidence from the same corpus image(s) |
| `parsed_visual` | retrieved page image(s) + Upstage parsed text/table evidence from the same corpus image(s) |

## Meaning

All methods answer the same questions from the same dataset and use the same final VLM. This makes the experiment test the method design rather than differences in model strength or data source.

## Default command pattern

```bash
# Default = Qwen2-VL-7B-Instruct-AWQ (int4), runs on 8 GB GPU. Matches PPT teammate baseline.
DATASETS=ChartQA bash scripts/run_domain_free_v12_experiment.sh

# Paper-aligned alternatives (require larger GPU or API key):
# GENERATOR_BACKEND=qwen2vl7b   MODEL=Qwen/Qwen2-VL-7B-Instruct bash scripts/run_domain_free_v12_experiment.sh
# GENERATOR_BACKEND=minicpmv26  MODEL=openbmb/MiniCPM-V-2_6     bash scripts/run_domain_free_v12_experiment.sh
# GENERATOR_BACKEND=gpt4o       MODEL=gpt-4o                    bash scripts/run_domain_free_v12_experiment.sh
```

If the machine has no GPU or required deps are missing, use `--dry-run` for pipeline validation only. Allowed generators are Qwen2-VL-7B(+AWQ), MiniCPM-V 2.6, and GPT-4o. Other VLMs (Gemini, Claude, etc.) MUST NOT be used for benchmark numbers — they were never in the VisRAG paper nor in the teammate PPT, so results would not be comparable.
