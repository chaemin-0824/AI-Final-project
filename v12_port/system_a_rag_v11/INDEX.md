# system_a_rag_v11

- 역할: VDU-Image-RAG(v11)와 VDU-Visual-RAG(v12)의 visual answer generation 구현
- 논문 관련 섹션: Section 3.5; Table 4: VDU-Image-RAG / VDU-Visual-RAG

## 포함 항목
- __init__.py: 패키지 초기화 파일.
- retriever_v11.py: VDU-Image-RAG: v10r 검색 + 이미지 전용 생성 (Section 3.5).
- retriever_v12.py: VDU-Visual-RAG: 이미지 + OCR 텍스트 기반 생성 (Section 3.5).
- visual_generator.py: PDF 페이지 렌더링과 Gemini 멀티모달 답변 생성.
