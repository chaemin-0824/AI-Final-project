# Prompt-bias hypothesis test (Image+Text cells)

Generator: Qwen2-VL-7B-Instruct (NF4 4-bit) | Metric: Relaxed Exact Match
Samples: Chaemin first100 (oracle qrels, topk=1) | DocVQA == MP-DocVQA
Environment: transformers 4.57.6 (vision-bug-free); local RTX 4060 8GB.

All 4 cells were re-run end-to-end on the same machine and same
transformers version, so prompt-variant deltas are within-config and free
of the 4.51 vision-encoder bug that depressed tf451 numbers.

| Method | Prompt | InfoVQA | ChartQA | MP-DocVQA | SlideVQA | Macro | Δ vs row 1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Image+Text (Upstage) | tf457 | 0.6800 | 0.7143 | 0.8600 | 0.5700 | 0.7061 | — (baseline) |
| Image+Text (Upstage) | image_first | 0.6900 | 0.7143 | 0.8800 | 0.6000 | 0.7211 | +1.50%p |
| Image+Text (Qwen OCR) | tf457 | 0.7100 | 0.6984 | 0.8600 | 0.6300 | 0.7246 | +1.85%p |
| Image+Text (Qwen OCR) | image_first | 0.7300 | 0.6984 | 0.8900 | 0.6200 | 0.7346 | +2.85%p |

## tf457 reference (different hardware, copied verbatim)

| Method | Prompt | InfoVQA | ChartQA | MP-DocVQA | SlideVQA |
|---|---|---:|---:|---:|---:|
| Image+Text (Qwen OCR) | tf457 | 0.7300 | 0.6667 | 0.8200 | 0.5800 |
| Image+Text (Upstage)  | tf457 | 0.5400 | 0.5079 | 0.8000 | 0.5200 |
