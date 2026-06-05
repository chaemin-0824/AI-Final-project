# Experiment contract: one corpus, one generator

This file records the user decision for the fair VisRAG comparison.

## Fixed components

| Component | Fixed choice |
|---|---|
| Generator VLM | `MiniCPM-V 2.6` |
| Generator model path | `openbmb/MiniCPM-V-2_6` |
| Dataset family | Official VisRAG benchmark HuggingFace datasets |
| Corpus source | One shared `corpus` split per dataset, e.g. `openbmb/VisRAG-Ret-Test-ChartQA` / `corpus` |
| Query source | Same `queries` split per dataset |
| Gold relevance | Same `qrels` split per dataset |
| Evaluation metric | VisRAG paper-style accuracy and retrieval MRR@10/Recall@10 |

## Variable component

Only the evidence format changes:

| Mode | Evidence sent to MiniCPM-V 2.6 |
|---|---|
| `image_only` | retrieved page image(s) from the shared corpus |
| `parsed_text_only` | Upstage parsed text/table evidence from the same corpus image(s) |
| `parsed_visual` | retrieved page image(s) + Upstage parsed text/table evidence from the same corpus image(s) |

## Meaning

All methods answer the same questions from the same dataset and use the same final VLM. This makes the experiment test the method design rather than differences in model strength or data source.

## Default command pattern

```bash
DATASETS=ChartQA \
GENERATOR_BACKEND=minicpmv26 \
MODEL=openbmb/MiniCPM-V-2_6 \
bash scripts/run_domain_free_v12_experiment.sh
```

If the machine has no GPU or MiniCPM dependencies are missing, use `--dry-run` for pipeline validation only. The only paper-aligned alternative generator is `--generator-backend gpt4o` (also used in the VisRAG paper). Other VLMs (Gemini, Claude, etc.) MUST NOT be used for benchmark numbers — they were never in the VisRAG paper, so results would not be comparable.
