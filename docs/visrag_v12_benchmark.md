# VisRAG ↔ v12 비교 평가 환경 구축 기록

## 목표

- VisRAG 논문(arXiv:2410.10594)의 공개 데이터셋과 공식 평가 기준을 재현한다.
- 교량 도메인에 특화된 bridge-v12를 그대로 비교하지 않고, VisRAG 데이터셋에 맞춘 **domain-free v12-general / Parsed-Visual RAG** 변형을 설계한다.
- v12-general은 Upstage parsing → 일반 text RAG retrieval → VLM에 parsed text/table evidence와 원본 이미지를 함께 제공하는 구조로 둔다.
- 두 방법론을 같은 입력/평가 기준에서 비교할 수 있도록 실행 스크립트와 결과 집계기를 둔다.
- 결과는 팀원 PPT(`docs/VisRAG Multi Page Compression.pptx` slide 10) 양식과 동일한 표(`Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline`)로 산출한다. DocVQA == MP-DocVQA(`openbmb/VisRAG-Ret-Test-MP-DocVQA`).

자세한 설계는 `docs/domain_free_v12_experiment_design.md`, 구현 계획은 `docs/plans/domain_free_v12_implementation_plan.md`에 둔다.

## 논문 기준 요약

논문/README 기준 원문 근거:

- 논문: `https://arxiv.org/abs/2410.10594`
- 코드: `https://github.com/openbmb/visrag`
- 공식 README의 평가 커맨드: `visrag_scripts/eval_retriever/eval.sh 512 2048 16 8 wmean causal ArxivQA,ChartQA,MP-DocVQA,InfoVQA,PlotQA,SlideVQA <ckpt_path>`
- 논문 Table 1/실험 섹션 기준 데이터셋: `ArxivQA`, `ChartQA`, `MP-DocVQA`, `InfoVQA`, `PlotQA`, `SlideVQA` (6개)
- 팀원 PPT(`docs/VisRAG Multi Page Compression.pptx`) 비교 대상은 그 중 4개: `InfoVQA`, `ChartQA`, `MP-DocVQA(DocVQA로 표기)`, `SlideVQA`. 본 워크스페이스의 default도 이 4개로 맞춤. 6개 전체를 돌리려면 `python scripts/prepare_visrag_datasets.py --all-paper` 또는 `DATASETS=ArxivQA,ChartQA,MP-DocVQA,InfoVQA,PlotQA,SlideVQA` 환경변수로 override 가능.
- 검색 평가: `MRR@10`, `Recall@10`
- 생성 평가: answer `Accuracy`, 숫자형 응답은 5% 오차 허용 relaxed exact match

## 현재 작업공간 구조

```text
/home/chaemin/projects/AI algorithm study/
├── visrag/                         # openbmb/visrag shallow clone
├── v12_port/                       # paper_visual_rag v12 관련 모듈 이식본
├── benchmark/
│   ├── metrics.py                  # relaxed exact match / retrieval metrics
│   ├── parse_cache.py              # Upstage parse cache schema/helpers
│   ├── text_retrieval.py           # BM25 retrieval over parsed evidence
│   ├── v12_on_visrag.py            # domain-free generation: image_only/parsed_text_only/parsed_visual
│   ├── compare_results.py          # VisRAG/v12 결과 집계
│   └── ppt_table_exporter.py       # PPT slide-10 양식의 결과 표 markdown/csv/json
├── scripts/smoke_test_ppt_pipeline.sh  # 의존성 없는 dry-run 전체 파이프라인 점검
├── configs/visrag_paper_benchmark.json
├── scripts/
│   ├── parse_visrag_with_upstage.py
│   ├── run_parsed_text_retrieval.py
│   ├── evaluate_retrieval.py
│   ├── run_domain_free_v12_experiment.sh
│   ├── prepare_visrag_datasets.py
│   ├── run_visrag_retrieval.sh
│   ├── run_visrag_generation.sh
│   └── run_v12_bridge.py
└── results/
```

## 실행 순서

### 1) 데이터셋 manifest 생성

```bash
cd "/home/chaemin/projects/AI algorithm study"
python scripts/prepare_visrag_datasets.py --output data/visrag_dataset_manifest.json
```

### 2) VisRAG 공식 retrieval 평가

GPU/의존성 준비 후 실행:

```bash
cd "/home/chaemin/projects/AI algorithm study"
MODEL_PATH=openbmb/VisRAG-Ret GPUS_PER_NODE=1 bash scripts/run_visrag_retrieval.sh
```

논문 기본값은 `MAX_Q_LEN=512`, `MAX_P_LEN=2048`, `POOLING=wmean`, `ATTENTION=causal`이다.

### 3) VisRAG 공식 generation 평가

retrieval 결과 TREC 디렉터리를 `RESULTS_ROOT_DIR`로 지정한다.

```bash
DATASET_NAME=ArxivQA \
TASK_TYPE=multi_image \
TOPK=1 \
RESULTS_ROOT_DIR=results/visrag_retrieval \
OUTPUT_DIR=results/visrag_generation \
bash scripts/run_visrag_generation.sh
```

### 4) v12-general / Parsed-Visual RAG를 VisRAG 데이터셋 위에서 실행

먼저 Upstage parse cache를 만들고, parsed text retrieval TREC를 생성한다.

```bash
python scripts/parse_visrag_with_upstage.py \
  --dataset ChartQA \
  --limit 10 \
  --output data/parsed/ChartQA_upstage.jsonl

python scripts/run_parsed_text_retrieval.py \
  --dataset ChartQA \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --topk 10 \
  --output results/parsed_text_retrieval/ChartQA/test.trec
```

이후 같은 TREC 검색 결과로 generation mode를 바꿔 비교한다.

```bash
python benchmark/v12_on_visrag.py \
  --dataset ChartQA \
  --trec results/parsed_text_retrieval/ChartQA/test.trec \
  --parse-cache data/parsed/ChartQA_upstage.jsonl \
  --mode parsed_visual \
  --generator-backend minicpmv26 \
  --model openbmb/MiniCPM-V-2_6 \
  --topk 1 \
  --limit 20 \
  --output results/v12_on_visrag/ChartQA_parsed_visual_top1.json
```

스모크 테스트만 할 때는 API 호출 없이 image-only 모드 또는 sample cache를 사용한다.

```bash
python benchmark/v12_on_visrag.py --dataset ChartQA --oracle --topk 1 --limit 2 --mode image_only --generator-backend minicpmv26 --dry-run
python benchmark/v12_on_visrag.py --dataset ChartQA --oracle --topk 1 --limit 2 --mode parsed_visual --generator-backend minicpmv26 --parse-cache data/parsed/ChartQA_sample.jsonl --dry-run
```

### 5) 이식된 v12 bridge 파이프라인 확인

```bash
python scripts/run_v12_bridge.py --bridge 대안천교 --question-ids Q01 Q02 --dry-run
```

실제 실행은 Gemini API와 기존 PDF/청크 캐시가 필요하다. 현재 `/home/chaemin/projects/paper_visual_rag/data/{교량}/upstage_v10_chunks.json`은 존재하지만, `v10_embeddings.npy`는 없으므로 첫 실제 실행 시 Gemini 임베딩을 새로 생성해 저장한다.

```bash
python scripts/run_v12_bridge.py --bridge 대안천교 --question-ids Q01 Q02
```

### 6) 결과 비교 (간단 JSON 집계)

```bash
python benchmark/compare_results.py \
  --visrag-history results/visrag_generation/.../*_history.jsonl \
  --v12-json results/v12_on_visrag/ChartQA_parsed_visual_top1.json \
  --output results/comparison_summary.json
```

### 7) PPT slide-10 양식 표 산출

`benchmark/ppt_table_exporter.py`는 PPT의 4-dataset × 방법별 표를 markdown/csv/json으로 만든다. DocVQA 컬럼은 자동으로 MP-DocVQA에 매핑된다.

```bash
# v12-general 결과만으로 PPT 표를 만들 때 (baseline = image_only 모드)
python benchmark/ppt_table_exporter.py \
  --v12-json results/v12_on_visrag/InfoVQA_image_only_top1.json \
              results/v12_on_visrag/InfoVQA_parsed_text_only_top1.json \
              results/v12_on_visrag/InfoVQA_parsed_visual_top1.json \
              results/v12_on_visrag/ChartQA_image_only_top1.json \
              results/v12_on_visrag/ChartQA_parsed_text_only_top1.json \
              results/v12_on_visrag/ChartQA_parsed_visual_top1.json \
              results/v12_on_visrag/MP-DocVQA_image_only_top1.json \
              results/v12_on_visrag/MP-DocVQA_parsed_text_only_top1.json \
              results/v12_on_visrag/MP-DocVQA_parsed_visual_top1.json \
              results/v12_on_visrag/SlideVQA_image_only_top1.json \
              results/v12_on_visrag/SlideVQA_parsed_text_only_top1.json \
              results/v12_on_visrag/SlideVQA_parsed_visual_top1.json

# VisRAG 공식 generation 결과를 baseline 행으로 쓸 때
python benchmark/ppt_table_exporter.py \
  --v12-json results/v12_on_visrag/*_top1.json \
  --visrag-history results/visrag_generation/<...>/InfoVQA_history.jsonl \
                   results/visrag_generation/<...>/ChartQA_history.jsonl \
                   results/visrag_generation/<...>/MP-DocVQA_history.jsonl \
                   results/visrag_generation/<...>/SlideVQA_history.jsonl \
  --baseline-method visrag_official
```

### 8) 의존성 없는 smoke 점검

```bash
SMOKE_LIMIT=2 bash scripts/smoke_test_ppt_pipeline.sh
```

API/GPU 호출 없이 4 dataset × 3 mode × dry-run을 돌리고 PPT 양식 표까지 만들어 본다. 모든 cell이 0.0000으로 출력되면 정상(prediction=DRY_RUN).

## 비교 설계 원칙

1. **Retrieval은 별도 보고**: 논문과 같이 `MRR@10`, `Recall@10`을 사용한다.
2. **Generation은 같은 top-k 문서로 비교**: 동일 TREC run을 VisRAG-Gen과 v12_on_visrag에 넣어 생성부 차이를 분리한다.
3. **End-to-end는 top-k별로 보고**: `topk=1,2,3`을 각각 저장해 논문 Table 3 형식으로 비교한다.
4. **bridge-v12와 v12-general을 분리**: 교량 QA용 bridge-v12의 챕터 추론/도메인 보강은 VisRAG 공개 벤치마크에서 제거한다. VisRAG 데이터셋 비교에는 Upstage parsing + 일반 text retrieval + image/text VLM generation만 남긴 `Parsed-Visual RAG`를 사용한다.

## 주의

- VisRAG-Ret 및 MiniCPM 계열 실행은 GPU 메모리를 크게 요구한다. 공식 demo README는 파이프라인 실행에 약 40GB GPU 메모리를 언급한다.
- v12_on_visrag은 현재 OCR sidecar가 없으면 이미지 기반 생성만 수행하되, 프롬프트/입출력 구조는 v12의 “이미지 + 선택적 OCR 텍스트” 구조로 맞춰 두었다.
- 공정한 방법론 비교에서는 `--trec`로 같은 검색 결과를 공급하는 방식을 우선 사용한다.
