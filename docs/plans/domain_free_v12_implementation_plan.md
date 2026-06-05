# Domain-free v12 Benchmark Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a fair VisRAG benchmark comparison where the proposed method removes bridge-domain components and uses Upstage parsing + text retrieval + VLM image/text generation.

**Architecture:** The pipeline has four independent stages: parse corpus images with Upstage and cache outputs; build a text retrieval index from parsed text/tables; generate answers using retrieved original images plus parsed evidence; evaluate retrieval and generation with VisRAG paper metrics.

**Tech Stack:** Python, HuggingFace `datasets`, Upstage Document Parse API, BM25 (`rank_bm25`), optional dense embeddings, paper-aligned VLM (MiniCPM-V 2.6 primary, GPT-4o fallback), JSONL cache, TREC run format.

---

## Task 1: Add parse-cache schema utilities

**Objective:** Create reusable read/write helpers for parsed corpus evidence.

**Files:**
- Create: `benchmark/parse_cache.py`
- Test: `tests/test_parse_cache.py`

**Step 1: Write tests**

Test cases:
- cache key is `{dataset}:{corpus_id}`
- JSONL cache can round-trip Korean/Unicode/table markdown
- failed parse rows are preserved with `parse_status="failed"`

**Step 2: Implement `ParsedDocument` dataclass**

Fields:

```python
@dataclass
class ParsedDocument:
    dataset: str
    corpus_id: str
    text: str = ""
    tables_markdown: list[str] = field(default_factory=list)
    table_descriptions: list[str] = field(default_factory=list)
    parse_status: str = "ok"
    error: str = ""
    raw_upstage: dict[str, Any] = field(default_factory=dict)
```

**Step 3: Add helpers**

Functions:

```python
def cache_key(dataset: str, corpus_id: str) -> str: ...
def load_parse_cache(path: str | Path) -> dict[str, ParsedDocument]: ...
def append_parse_cache(path: str | Path, doc: ParsedDocument) -> None: ...
def evidence_text(doc: ParsedDocument) -> str: ...
```

**Step 4: Verify**

Run:

```bash
.venv/bin/python -m pytest tests/test_parse_cache.py -v
```

Expected: all pass.

---

## Task 2: Implement Upstage corpus parser

**Objective:** Parse VisRAG HF corpus images with Upstage and cache text/table outputs.

**Files:**
- Create: `scripts/parse_visrag_with_upstage.py`

**CLI:**

```bash
python scripts/parse_visrag_with_upstage.py \
  --dataset ChartQA \
  --limit 10 \
  --output data/parsed/ChartQA_upstage.jsonl
```

**Required behavior:**
- Load `openbmb/VisRAG-Ret-Test-{dataset}`, subset `corpus`.
- Convert each PIL image to PNG/JPEG bytes.
- Send to Upstage Document Parse.
- Extract plain text, table markdown, and raw response.
- Skip already cached corpus IDs unless `--force`.
- Write one JSONL record per corpus item.

**Verification:**

Dry-run mode:

```bash
python scripts/parse_visrag_with_upstage.py --dataset ChartQA --limit 2 --dry-run
```

Expected: prints two corpus IDs without API calls.

---

## Task 3: Build BM25 text retrieval over parsed evidence

**Objective:** Retrieve documents using parsed text/table evidence and save a TREC-style run.

**Files:**
- Create: `benchmark/text_retrieval.py`
- Create: `scripts/run_parsed_text_retrieval.py`

**CLI:**

```bash
python scripts/run_parsed_text_retrieval.py \
  --dataset ChartQA \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --topk 10 \
  --output results/parsed_text_retrieval/ChartQA/test.trec
```

**Implementation:**
- Tokenize by simple whitespace + lowercase first.
- Use `rank_bm25.BM25Okapi`.
- Query from HF `queries` split.
- Output TREC rows:

```text
{qid} Q0 {corpus_id} {rank} {score} parsed_text_bm25
```

**Verification:**

Run with dry-run/limit:

```bash
python scripts/run_parsed_text_retrieval.py --dataset ChartQA --parse-cache data/parsed/ChartQA_upstage.jsonl --topk 3 --limit 5
```

Expected: output has 15 rows.

---

## Task 4: Add retrieval metrics

**Objective:** Compute MRR@10 and Recall@10 against HF qrels.

**Files:**
- Modify: `benchmark/metrics.py`
- Create: `scripts/evaluate_retrieval.py`

**Functions:**

```python
def mrr_at_k(run: dict[str, list[str]], qrels: dict[str, set[str]], k: int = 10) -> float: ...
def recall_at_k(run: dict[str, list[str]], qrels: dict[str, set[str]], k: int = 10) -> float: ...
```

**Verification:**
- Unit test with synthetic qrels/run.
- Run on a small generated TREC file.

---

## Task 5: Replace `v12_on_visrag.py` with domain-free parsed-visual generation

**Objective:** Make generation consume parse cache and retrieved doc IDs, without bridge-specific v12 logic.

**Files:**
- Modify: `benchmark/v12_on_visrag.py`

**CLI additions:**

```bash
--parse-cache data/parsed/ChartQA_upstage.jsonl
--mode parsed_visual | parsed_text_only | image_only
```

**Modes:**
- `image_only`: original image(s), no parsed evidence. VisRAG-style generation baseline.
- `parsed_text_only`: parsed text/table evidence, no image.
- `parsed_visual`: parsed text/table evidence + original image(s). Proposed method.

**Prompt:**

```text
Use parsed text/table evidence for exact labels and values.
Use images to verify visual/layout evidence.
Answer only the final answer.
```

**Verification:**

Dry-run:

```bash
python benchmark/v12_on_visrag.py \
  --dataset ChartQA \
  --oracle \
  --topk 1 \
  --limit 2 \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --mode parsed_visual \
  --dry-run
```

Expected: rows include `method="parsed_visual"` and `ocr_context_available=true` for cached docs.

---

## Task 6: Add experiment runner

**Objective:** Run all systems/datasets consistently.

**Files:**
- Create: `scripts/run_domain_free_v12_experiment.sh`

**Runs:**
- parse if cache missing
- parsed text retrieval
- retrieval evaluation
- generation for modes:
  - `image_only`
  - `parsed_text_only`
  - `parsed_visual`
- result summary

**Verification:**

Small run:

```bash
DATASETS=ChartQA LIMIT=5 bash scripts/run_domain_free_v12_experiment.sh
```

Expected outputs:

```text
results/parsed_text_retrieval/ChartQA/test.trec
results/v12_on_visrag/ChartQA_image_only_top1.json
results/v12_on_visrag/ChartQA_parsed_text_only_top1.json
results/v12_on_visrag/ChartQA_parsed_visual_top1.json
results/domain_free_v12_summary.json
```

---

## Task 7: Update documentation

**Objective:** Document exact experimental framing and commands.

**Files:**
- Modify: `docs/visrag_v12_benchmark.md`
- Keep: `docs/domain_free_v12_experiment_design.md`

**Required language:**
- Do not call this full bridge-v12.
- Call it `Parsed-Visual RAG` or `v12-general`.
- State bridge-specific components are removed.
- State that this enables fair comparison on VisRAG datasets.

---

## Acceptance Criteria

- [ ] No bridge-specific classifier/chapter logic is used in VisRAG benchmark scripts.
- [ ] Upstage parse cache is query-independent and reusable.
- [ ] Parsed text retrieval outputs TREC format.
- [ ] Retrieval metrics match VisRAG paper metric names.
- [ ] Generation can run in image-only, parsed-text-only, parsed-visual modes.
- [ ] Results can be summarized per dataset and averaged.
- [ ] Documentation clearly distinguishes `VisRAG`, `v12-general`, and `Bridge-v12`.
