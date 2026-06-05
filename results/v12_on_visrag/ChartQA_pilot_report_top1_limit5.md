# ChartQA Pilot: Same Dataset + Same VLM Comparison

## Setup

- Dataset: `openbmb/VisRAG-Ret-Test-ChartQA`
- Query subset: first 5 evaluation queries
- Generator VLM: `models/gemini-3.1-pro-preview` for every generation mode
- Retrieval source for reported generation: same TREC run from parsed-text BM25 retrieval
- Top-k for generation: 1
- Upstage parse cache: `data/parsed/ChartQA_pilot_qrels.jsonl`

## Pipeline

1. Parsed the gold pages for the first 5 ChartQA queries with Upstage Document Parse.
2. Built a BM25 retrieval run over the parsed evidence.
3. Used the same retrieved page for all answer-generation modes.
4. Generated answers with the same Gemini model in three modes:
   - `image_only`: original image only
   - `parsed_text_only`: parsed text/table evidence only
   - `parsed_visual`: original image + parsed text/table evidence

## Retrieval sanity check

The pilot retrieval index contains only the 5 gold pages for the pilot subset, so this is a controlled sanity check rather than a full-corpus retrieval result.

- Pilot query count: 5
- MRR@1 on the 5 pilot queries: 1.0
- Recall@1 on the 5 pilot queries: 1.0
- MRR@5 on the 5 pilot queries: 1.0
- Recall@5 on the 5 pilot queries: 1.0

The full-dataset metric script reports lower values when run against all 63 qrels because the pilot TREC contains only 5 queries.

## Generation results

| Mode | Evidence to same VLM | Correct / Total | Accuracy |
|---|---|---:|---:|
| `image_only` | page image | 3 / 5 | 0.60 |
| `parsed_text_only` | Upstage parsed text/table | 2 / 5 | 0.40 |
| `parsed_visual` | page image + parsed text/table | 3 / 5 | 0.60 |

## Per-question outputs

| QID | Gold answer | image_only | parsed_text_only | parsed_visual |
|---|---:|---|---|---|
| `3960.png-2` | `0.03` | `3` | `3` | `3` |
| `13750.png-1` | `2` | `2%` | `2%` | `2%` |
| `939.png-1` | `68` | `68` | `insufficient to answer` | `68` |
| `4554.png-2` | `0.01` | `insufficient to answer` | `insufficient to answer` | `insufficient to answer` |
| `OECD_DEATHS_FROM_CANCER_COL_CRI_SVN_000015.png-1` | `No` | `No` | `No` | `No` |

## Output files

- Parse cache: `data/parsed/ChartQA_pilot_qrels.jsonl`
- Retrieval TREC: `results/parsed_text_retrieval/ChartQA/pilot_qrels_limit5.trec`
- Retrieval metrics: `results/parsed_text_retrieval/ChartQA/pilot_qrels_limit5_metrics.json`
- image-only results: `results/v12_on_visrag/ChartQA_pilot_trec_image_only_top1_limit5.json`
- parsed-text-only results: `results/v12_on_visrag/ChartQA_pilot_trec_parsed_text_only_top1_limit5.json`
- parsed-visual results: `results/v12_on_visrag/ChartQA_pilot_trec_parsed_visual_top1_limit5.json`
- summary: `results/v12_on_visrag/ChartQA_pilot_trec_summary_top1_limit5.json`

## Interpretation

This is a tiny smoke-test pilot, not a statistically meaningful result. It confirms that the comparison protocol is working:

- same dataset,
- same retrieved page source,
- same generator VLM,
- only evidence type changes.

The pilot does not yet show a clear advantage for `parsed_visual` over `image_only`; both score 0.60 on 5 questions. The parsed-text-only mode is weaker at 0.40, suggesting that for ChartQA image evidence remains important. A larger run is needed before drawing conclusions.
