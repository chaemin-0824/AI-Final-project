# Results (PPT slide-10 layout)

Dataset columns match `docs/VisRAG Multi Page Compression.pptx` slide 10.
DocVQA == MP-DocVQA (`openbmb/VisRAG-Ret-Test-MP-DocVQA`).

| Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline |
|---|---:|---:|---:|---:|---:|
| Baseline (순수 VisRAG, v12_on_visrag image_only) | 0.2000 | 0.3651 | 0.1700 | 0.1800 | — |
| Parsed-Text Only (ablation) | 0.5400 | 0.5238 | 0.7600 | 0.5200 | +35.72%p |
| Parsed-Visual RAG (v12-general) | 0.5400 | 0.5079 | 0.8000 | 0.5200 | +36.32%p |

## Macro averages

| Method | Macro acc | Δ vs Baseline |
|---|---:|---:|
| Baseline (순수 VisRAG, v12_on_visrag image_only) | 0.2288 | — |
| Parsed-Text Only (ablation) | 0.5860 | +35.72%p |
| Parsed-Visual RAG (v12-general) | 0.5920 | +36.32%p |
