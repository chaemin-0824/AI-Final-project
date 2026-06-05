# system_a_rag

- 역할: RAG-Base (v1) baseline 구현
- 논문 관련 섹션: Table 4: RAG-Base; Sections 4.2, 5

## 포함 항목
- __init__.py: 패키지 초기화 파일.
- extractor.py: v1 baseline의 OCR/텍스트 추출과 Camelot 표 추출.
- retriever.py: 질문 분류, 재랭킹, GPT-5.4 답변 생성 로직.
- run_rag.py: RAG-Base 전체 파이프라인 실행 스크립트 (Table 4: RAG-Base).
- vectorstore.py: v1 baseline FAISS 벡터스토어 구축/로드.
