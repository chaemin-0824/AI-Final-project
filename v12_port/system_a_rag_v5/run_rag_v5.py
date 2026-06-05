"""RAG v5 파이프라인.

v3 기반 + Query Decomposition + Page-Level Context Expansion.
벡터스토어/enrichment는 v3 기존 것을 그대로 로드한다.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from questions import QUESTIONS
from system_a_rag.extractor import extract_all
from system_a_rag_v2.table_extractor import extract_tables_with_vlm
from system_a_rag_v2.table_enricher import enrich_tables
from system_a_rag_v3.context_enricher import enrich_text_chunks
from system_a_rag_v3.vectorstore_v3 import load_vectorstore_v3
from system_a_rag_v3.hybrid_retriever import HybridRetriever
from system_a_rag_v5.retriever_v5 import rag_answer_v5


def run_rag_v5_pipeline(bridge_name: str, question_ids: list[str] = None) -> dict:
    start_time = time.time()
    active_questions = [q for q in QUESTIONS if q["id"] in question_ids] if question_ids else QUESTIONS
    print(f"\n🚀 [RAG v5] {bridge_name} 분석 시작 ({len(active_questions)}문항)")

    results_dir = Path(config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"{bridge_name}_rag_v5_results.json"

    # Step 1: 텍스트 + VLM 표 추출 (캐시)
    text_docs = extract_all(bridge_name)
    vlm_tables = extract_tables_with_vlm(bridge_name)
    vlm_table_pages = [item["page"] for item in vlm_tables]
    print(f"📄 텍스트: {len(text_docs)}개, 📊 표: {sum(len(p['tables']) for p in vlm_tables)}개")

    # Step 2: v3 enrichment 로드 (캐시)
    enriched_tables = enrich_tables(vlm_tables, bridge_name)
    contextual_texts = enrich_text_chunks(text_docs, bridge_name, vlm_table_pages)

    # Step 3: v3 벡터스토어 로드 (새로 만들지 않음)
    vectorstore = load_vectorstore_v3(bridge_name)
    if vectorstore is None:
        raise RuntimeError(f"v3 벡터스토어가 없습니다: data/{bridge_name}/faiss_index_v3")
    print("🔍 벡터스토어 v3 로드 완료")

    # Step 4: 하이브리드 검색기 (v3 동일)
    all_docs = contextual_texts + enriched_tables
    hybrid_retriever = HybridRetriever(vectorstore, all_docs)
    print(f"🔍 하이브리드 검색기: {len(all_docs)}개 문서")

    # Step 5: QA (Query Decomposition + Page Expansion)
    print(f"\n── QA 실행 ({len(active_questions)}문항) ──")
    answers = []
    for i, q in enumerate(active_questions):
        print(f"▶ Q{q['id'][-2:]}/{len(active_questions)} 진행 중...")
        answer_result = None
        for attempt in range(3):
            try:
                answer_result = rag_answer_v5(
                    question=q["text"],
                    hybrid_retriever=hybrid_retriever,
                    all_docs=all_docs,
                    bridge_name=bridge_name,
                    question_id=q["id"],
                )
                answer_result["system"] = "rag_v5"
                answer_result["category"] = q["category"]
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  ⚠️ 에러 (시도 {attempt+1}/3): {e}")
                    time.sleep(30)
                else:
                    answer_result = {
                        "question_id": q["id"], "question": q["text"],
                        "answer": f"ERROR: {e}", "question_type": q["category"],
                        "category": q["category"], "subqueries": [],
                        "retrieved_contexts": [], "retrieved_pages": [],
                        "bridge": bridge_name, "system": "rag_v5",
                        "elapsed_sec": 0, "input_tokens": 0, "output_tokens": 0,
                    }
        answers.append(answer_result)
        if i < len(active_questions) - 1:
            time.sleep(2)

    final_result = {
        "bridge": bridge_name, "system": "rag_v5",
        "model": config.RAG_LLM_MODEL, "timestamp": datetime.now().isoformat(),
        "total_questions": len(answers), "results": answers,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"\n✅ 완료! {int(elapsed//60)}분 {int(elapsed%60):02d}초")
    return final_result
