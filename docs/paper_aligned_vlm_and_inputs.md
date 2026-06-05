# Paper-aligned generator and input data notes

## Which VLM did the VisRAG paper use?

The paper did not use a single generator only. It reports several generator settings:

| Paper section/table setting | Generator | Input type |
|---|---|---|
| TextRAG-Gen | MiniCPM or GPT-4o | OCR/extracted text |
| VisRAG-Gen single-image | MiniCPM-V 2.0 | one image; top-k pages are concatenated or weighted-selected |
| VisRAG-Gen multi-image | MiniCPM-V 2.6 or GPT-4o | multiple page images |

For our fair comparison, use one answer generator across methods. Recommended paper-aligned choice:

```text
model_name: MiniCPMV2.6
model_name_or_path: openbmb/MiniCPM-V-2_6
```

Reason: MiniCPM-V 2.6 is used in the VisRAG paper and supports multi-image input, so it can evaluate `image_only` and `parsed_visual` without changing the generator. If local GPU memory is insufficient, GPT-4o is also paper-used and easier through API, but it is not an open local model.

## What exactly is the input data?

The official benchmark data is loaded from Hugging Face with this pattern:

```text
openbmb/VisRAG-Ret-Test-{dataset}
```

Datasets:

- ArxivQA
- ChartQA
- MP-DocVQA
- InfoVQA
- PlotQA
- SlideVQA

Each dataset has three important splits/configs:

### 1. `queries`

Question records. Example from ChartQA:

```json
{
  "query-id": "3960.png-2",
  "query": "How many more people felt inspired frequently than depressed frequently?",
  "answer": "0.03",
  "options": null,
  "is_numerical": 0
}
```

### 2. `corpus`

Document/page records. The document itself is an image.

```json
{
  "corpus-id": "41699051005347.png",
  "image": "PIL image object, e.g. 850x600 RGBA"
}
```

In generation, retrieved `corpus-id`s are used to fetch these original page images.

### 3. `qrels`

Ground-truth relevance labels mapping query to the positive page(s).

```json
{
  "query-id": "3960.png-2",
  "corpus-id": "3960.png",
  "score": 1
}
```

## Official generation input flow

For non-oracle generation:

```text
query-id
→ retrieval TREC run gives top-k corpus-id(s)
→ corpus split maps corpus-id to image
→ generator receives text or image inputs depending on method
→ prediction is compared with queries.answer
```

For oracle generation:

```text
query-id
→ qrels gives gold corpus-id(s)
→ corpus split maps gold corpus-id to image
→ generator answers with gold evidence
```

## How we should adjust our experiment

Replace Gemini with paper-aligned generator:

1. Primary: MiniCPM-V 2.6 (`openbmb/MiniCPM-V-2_6`) if GPU allows.
2. Fallback: GPT-4o if local GPU is not enough.

Keep these fixed across methods:

- same dataset,
- same queries,
- same corpus images,
- same qrels/answers,
- same answer generator,
- same evaluation metric.

Only change evidence format:

- `image_only`: retrieved image(s), no parsed text.
- `parsed_text_only`: parsed text/table evidence, no image.
- `parsed_visual`: retrieved image(s) + parsed text/table evidence.
