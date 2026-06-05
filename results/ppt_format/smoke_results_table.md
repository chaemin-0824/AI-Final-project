# Results (PPT slide-10 layout)

Dataset columns match `docs/VisRAG Multi Page Compression.pptx` slide 10.
DocVQA == MP-DocVQA (`openbmb/VisRAG-Ret-Test-MP-DocVQA`).

| Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline |
|---|---:|---:|---:|---:|---:|
| Baseline (순수 VisRAG, v12_on_visrag image_only) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |
| Parsed-Text Only (ablation) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | +0.00%p |
| Parsed-Visual RAG (v12-general) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | +0.00%p |

## Macro averages

| Method | Macro acc | Δ vs Baseline |
|---|---:|---:|
| Baseline (순수 VisRAG, v12_on_visrag image_only) | 0.0000 | — |
| Parsed-Text Only (ablation) | 0.0000 | +0.00%p |
| Parsed-Visual RAG (v12-general) | 0.0000 | +0.00%p |
