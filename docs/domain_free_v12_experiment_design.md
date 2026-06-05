# Domain-free v12 Experiment Design for Fair VisRAG Comparison

## Decision

We should not compare the bridge-domain v12 architecture directly against VisRAG on the VisRAG paper datasets. The bridge-domain v12 contains components that are meaningful for bridge inspection reports only, especially:

- question type classifier tuned to bridge QA categories,
- target chapter inference,
- bridge-specific history/damage supplementation,
- neighbor-page expansion based on bridge report structure,
- bridge-specific prompts and metadata.

For the VisRAG paper datasets, these components would be domain leakage or irrelevant inductive bias. Therefore the fair comparison should use a **domain-free v12 variant** that keeps only the general methodological idea:

> Parse the document page into text/table evidence, retrieve using a normal text RAG pipeline, and give the VLM both the parsed evidence and the original page image at answer time.

Working name:

- `Parsed-Visual RAG`
- `Upstage-Parsed Multimodal RAG`
- `v12-general`

Avoid calling this the full bridge `v12` in the paper. Use `v12-general` or `Ours-general` for the VisRAG benchmark, and reserve `Bridge-v12` for the bridge inspection report experiment.

---

## What VisRAG proposes

The VisRAG paper proposes a visual RAG pipeline:

```text
PDF/page image
→ visual embedding retrieval with VisRAG-Ret
→ retrieved page image(s)
→ VLM generation
```

Core claim:

> Avoid OCR/parsing information loss by retrieving and generating directly from document page images.

On the VisRAG public benchmark, this is the prior-method baseline.

---

## What we propose for the fair comparison

For the VisRAG benchmark, our proposed method should be:

```text
page image
→ Upstage parsing
→ parsed text + table description cache
→ text retrieval over parsed evidence
→ retrieved page image(s) + parsed text/table evidence
→ VLM generation
```

Core claim:

> Visual-only RAG preserves layout, but parsing can expose explicit textual/table evidence that improves retrieval and answer grounding. A hybrid parsed-evidence + original-image generator can combine text/table precision with visual verification.

This is no longer bridge-domain v12. It is a **domain-free parsed multimodal RAG** derived from v12's most general principle: *text evidence and visual evidence should be used together at answer time*.

---

## Components to remove from bridge v12

Remove all bridge-specific parts:

| Bridge-v12 Component | Keep? | Reason |
|---|---:|---|
| Question category classifier: 성능변화/중대결함/C등급관리/등급통계 | No | Bridge-specific taxonomy |
| Target chapter inference | No | VisRAG datasets do not share bridge report chapters |
| Query decomposition tuned for bridge inspection | Optional/No for main | Can introduce unfair prompt engineering; keep only as ablation if desired |
| Hybrid retrieval with chapter filters | No | Domain-specific |
| History/damage document supplementation | No | Bridge-specific |
| Neighbor-page expansion based on report continuity | Optional | For SlideVQA multi-hop only, but not main method unless applied uniformly |
| Bridge-specific prompts | No | Domain-specific |
| Image + OCR text generation | Yes | General method |
| Table description passed to VLM | Yes | General method and directly relevant to ChartQA/PlotQA/InfoVQA |

---

## Proposed systems for the VisRAG benchmark

### Main comparison table

| System | Retrieval | Generation input | Role |
|---|---|---|---|
| TextRAG-OCR | BM25/dense over parsed text | parsed text only | text-only baseline |
| VisRAG | visual embedding over page images | page image(s) | prior visual RAG method |
| Proposed: Parsed-Visual RAG | text retrieval over Upstage parsed text/tables | page image(s) + parsed text/table evidence | ours |

### Optional ablations

| System | Difference | Purpose |
|---|---|---|
| Ours-no-image | parsed text/table only | tests value of original image evidence |
| Ours-no-table-desc | parsed text without explicit table serialization/description | tests value of table evidence |
| Ours-oracle-retrieval | gold page image + parsed evidence | isolates generation quality from retrieval quality |
| VisRAG-oracle-retrieval | gold page image only | fair generation-only comparison |

Do not include bridge-v12 components in this benchmark.

---

## Evaluation datasets

Use exactly the VisRAG paper datasets:

- ArxivQA
- ChartQA
- MP-DocVQA
- InfoVQA
- PlotQA
- SlideVQA

HuggingFace pattern:

```text
openbmb/VisRAG-Ret-Test-{dataset}
```

Each dataset provides:

- `queries`: query id, question, answer
- `corpus`: corpus id, page image
- `qrels`: ground-truth relevance labels

---

## Evaluation metrics

Follow VisRAG paper metrics:

### Retrieval

- MRR@10
- Recall@10

Evaluate:

1. VisRAG-Ret visual retrieval
2. Proposed text retrieval over Upstage parsed evidence
3. Optional BM25-only and dense-only variants

### Generation

- Accuracy
- Relaxed exact match for numeric answers, 5% tolerance

Report by dataset and average.

---

## Fairness rules

1. **Same dataset**: all methods use the same VisRAG public datasets.
2. **Same query split**: use the official evaluation queries.
3. **No bridge-specific heuristics**: no chapter inference, no bridge categories, no damage/history supplementation.
4. **Same generator family if possible**: use the same VLM backend for VisRAG-style and Proposed generation when running our reimplementation.
5. **Separate retrieval and generation**:
   - retrieval table: MRR@10 / Recall@10
   - generation table: Accuracy at top-k
   - oracle generation table: gold page(s) supplied to isolate answer-generation ability
6. **Parse cache fixed before evaluation**: Upstage parsing should be run once and cached; no query-dependent parsing.

---

## Proposed pipeline details

### Step 1: Build parse cache

For every corpus image:

```text
corpus-id
image
→ Upstage Document Parse
→ plain text
→ tables serialized as markdown
→ optional table description
→ cache JSONL
```

Suggested cache schema:

```json
{
  "dataset": "ChartQA",
  "corpus_id": "3960.png",
  "text": "...",
  "tables_markdown": ["| ... |"],
  "table_descriptions": ["A chart/table showing ..."],
  "raw_upstage": {},
  "parse_status": "ok"
}
```

### Step 2: Build retrieval index

Input document per corpus item:

```text
[TEXT]
{parsed_text}

[TABLES]
{tables_markdown}

[TABLE DESCRIPTIONS]
{table_descriptions}
```

Start with BM25 for simplicity and reproducibility. Add dense embedding only if needed.

### Step 3: Retrieve top-k

For each query:

```text
query → BM25/text index → top-k corpus IDs
```

Save TREC-style run so retrieval metrics can be computed against qrels.

### Step 4: Generate answer

For each query and retrieved document:

VLM input:

```text
- original page image(s)
- parsed text evidence
- table markdown/description
- question
```

Prompt principle:

```text
Use the parsed text/table evidence for exact values and labels.
Use the image to verify layout, chart/table relationships, and visual marks.
If evidence is insufficient, answer insufficient to answer.
Return only the final answer.
```

### Step 5: Evaluate

- Retrieval: MRR@10 / Recall@10
- Generation: relaxed exact-match Accuracy
- Optional: dataset-level breakdown and top-k curves.

---

## Recommended paper framing

Bad framing:

> We compare bridge-v12 directly with VisRAG.

Better framing:

> To compare with VisRAG on its original benchmark, we derive a domain-free variant of our architecture by removing bridge-specific routing and retaining only the general parsed-evidence + visual-grounding principle. This allows a fair comparison between visual-only RAG and parsed multimodal RAG on the same datasets.

Suggested method names:

- Prior work: `VisRAG`
- Baseline: `TextRAG-Parse`
- Ours: `Parsed-Visual RAG`
- Domain experiment: `Bridge-v12`

---

## Expected contribution claim

If results are positive:

> On VisRAG-style document VQA benchmarks, parsed textual/table evidence remains useful when combined with original page images. This suggests that the best document RAG design is not necessarily OCR-only or visual-only, but a parsed multimodal pipeline that uses parsing for retrieval precision and images for visual grounding.

If results are mixed:

> Visual-only retrieval is strong when parsing is noisy, while parsed multimodal generation improves table/numeric QA when parsing succeeds. This motivates dataset-dependent routing between visual retrieval and parsed-text retrieval.

Both outcomes are publishable because they clarify when parsing helps or hurts compared with VisRAG.
