# system_a_rag_v5

- 역할: RAG-Enhanced 핵심 단계인 query decomposition 구현
- 논문 관련 섹션: Table 4: RAG-Enhanced; Sections 3.4, 4.2, 5

## 포함 항목
- __init__.py: 패키지 초기화 파일.
- query_decomposer.py: Gemini Flash-Lite 기반 서브쿼리 분해기 (Section 3.4).
- retriever_v5.py: Query decomposition + page-level context expansion 로직 (Section 3.4).
- run_rag_v5.py: RAG-Enhanced 전체 파이프라인 실행 스크립트.
