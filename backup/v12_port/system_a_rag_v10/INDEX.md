# system_a_rag_v10

- 역할: VDU-RAG 구현: Upstage parsing + structured chunking + chapter-filtered hybrid retrieval
- 논문 관련 섹션: Sections 3.2–3.4; Table 4: VDU-RAG

## 포함 항목
- __init__.py: 패키지 초기화 파일.
- chunker.py: 구조화 청킹: 표+캡션+후속 문단 묶음, 장/절 메타데이터 부여 (Section 3.3).
- embeddings.py: Gemini embedding wrapper와 임베딩 생성 로직 (Section 3.4).
- retriever_v10.py: 장 필터링 하이브리드 검색, 질문 분류, 도메인 보충 (Section 3.4).
- run_rag_v10.py: VDU-RAG / v10 계열 실행 진입점.
- upstage_loader.py: Upstage parse cache 로더 (Section 3.2).
