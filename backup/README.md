# backup/ — 제출 외 보관 자료

본 디렉터리는 최종 제출(PPT slide-10 양식 표 재현)에 필수가 아닌 파일을 보관한다. 모두 git 히스토리에 포함되어 작업 흐름과 의사결정 추적이 가능하다. 최종 결과(`results/ppt_format/today_results_table.*`) 재현에는 사용되지 않는다.

## 분류

### 1. Smoke / Dry-run 스크립트 및 결과 (`scripts/`, `results/v12_on_visrag/smoke*/`, `results/v12_on_visrag/*_dryrun.json`, `results/*_summary_dryrun.json`, `results/ppt_format/smoke_*`)

파이프라인 코드 contract 검증용. 모델/API 호출 없이 모듈 import·argparse·메시지 빌드를 점검한다. 본 검증은 단발성이라 제출에 필수 아님.

### 2. Pilot 결과 (`data/parsed/ChartQA_pilot_qrels.jsonl`, `data/parsed/ChartQA_sample.jsonl`, `data/visrag_dataset_manifest_chartqa.json`, `results/parsed_text_retrieval/ChartQA/{pilot_*, sample.*}`)

초기 5문제 단위 동작 점검 산출물. 본 보고서의 측정 대상이 아님.

### 3. Bridge 도메인 v12 코드 (`v12_port/`, `scripts/run_v12_bridge.py`)

VisRAG 비교와는 별개 도메인 실험(교량 점검 보고서 QA)의 v12 풀 파이프라인 이식본. 본 제출의 비교 대상인 *v12-general*은 이 도메인 종속 컴포넌트(질문 분류기, 챕터 추론, 손상 이력 보강 등)를 제거한 변형이며, 본 제출의 어떤 결과도 `v12_port` 임포트에 의존하지 않는다. 출처 reference로 보관한다.

설계 근거: `../docs/domain_free_v12_experiment_design.md`.

### 4. Gemini pilot archive (`results/_archive/gemini_pilot/`)

이전에 빠른 검증을 위해 Gemini API로 돌렸던 ChartQA pilot 결과. 본 보고서는 paper-aligned generator(Qwen2-VL-7B / MiniCPM-V 2.6 / GPT-4o)만 사용하므로 benchmark 숫자에 포함되지 않음. 결정 이력 보존을 위해 보관.

### 5. 실행 로그 (`logs/`)

- `run_today.log` — 최종 today 파이프라인 실행 로그 (~150 KB)
- `run_today.log.first_try.failed` — 첫 시도(InfoVQA stuck) 로그

## 본 폴더 내용에 의존하지 않음을 보장하는 방법

```bash
# 1) submit 단독 재현 가능성 확인
cd "/home/chaemin/projects/AI algorithm study"
test -s data/parsed/ChartQA_first100_qrels_upstage.jsonl
test -s data/parsed/InfoVQA_first100_qrels_upstage.jsonl
test -s data/parsed/MP-DocVQA_first100_qrels_upstage.jsonl
test -s data/parsed/SlideVQA_first100_qrels_upstage.jsonl
# 모두 OK면, UPSTAGE_API_KEY 없이도 Stage 2,3 재실행 가능
env -u UPSTAGE_API_KEY bash scripts/run_today_ppt_pipeline.sh

# 2) unit test 통과 확인
.venv/bin/python -m pytest tests/ -q
```

## 만약 bridge 도메인 실험을 살리고 싶다면

`backup/v12_port`와 `backup/scripts/run_v12_bridge.py`를 원래 경로(`v12_port/`, `scripts/run_v12_bridge.py`)로 옮기고, `backup/v12_port/config.py`의 PDF 경로(`/home/chaemin/projects/paper_visual_rag/data/{교량}/`)가 유효한지 확인. 본 제출의 VisRAG 비교에는 사용되지 않으므로 비활성화 상태가 권장 기본값이다.
