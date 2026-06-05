"""FAISS 벡터스토어 구축 모듈.

TableAwareTextSplitter: 표 구조를 인식하여 청크 크기를 조절.
build_vectorstore: 문서 리스트 → FAISS 인덱스 생성/저장.
load_vectorstore: 저장된 FAISS 인덱스 로드.
"""

import re
import sys
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# 표 포함 여부 판단 패턴
TABLE_PATTERNS = re.compile(
    r'㎡|개소|S[1-3]|P[1-2]|A[1-2]|등급|결함도|상태평가|안전성'
)

# 핵심 손상 키워드
CRITICAL_DAMAGE_KEYWORDS = ["철근노출", "박락", "박리", "잡철근노출"]


class TableAwareTextSplitter:
    """표 구조를 인식하여 청크 크기를 조절하는 텍스트 분할기.

    표 포함 텍스트: chunk_size=3000, chunk_overlap=500
    일반 텍스트: chunk_size=1000, chunk_overlap=200
    핵심 손상 키워드 포함 시 chunk_type="critical_damage" 태그 부여.
    """

    def __init__(self):
        self.table_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=500,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _is_table_content(self, text: str) -> bool:
        """텍스트에 표 관련 패턴이 포함되어 있는지 확인."""
        return bool(TABLE_PATTERNS.search(text))

    def _has_critical_damage(self, text: str) -> bool:
        """텍스트에 핵심 손상 키워드가 포함되어 있는지 확인."""
        return any(kw in text for kw in CRITICAL_DAMAGE_KEYWORDS)

    def split_documents(self, docs: list[Document]) -> list[Document]:
        """문서 리스트를 표 구조를 인식하여 청크로 분할한다.

        Args:
            docs: LangChain Document 리스트.

        Returns:
            분할된 Document 리스트 (metadata에 chunk_type 포함).
        """
        result = []

        for doc in docs:
            text = doc.page_content
            metadata = doc.metadata.copy()

            # 이미 table_data로 분류된 문서
            if metadata.get("chunk_type") == "table_data":
                if self._is_table_content(text):
                    chunks = self.table_splitter.split_text(text)
                else:
                    chunks = self.table_splitter.split_text(text)

                for chunk in chunks:
                    chunk_meta = metadata.copy()
                    if self._has_critical_damage(chunk):
                        chunk_meta["chunk_type"] = "critical_damage"
                    result.append(Document(page_content=chunk, metadata=chunk_meta))
                continue

            # 일반 문서: 표 포함 여부에 따라 분할 전략 결정
            if self._is_table_content(text):
                chunks = self.table_splitter.split_text(text)
            else:
                chunks = self.text_splitter.split_text(text)

            for chunk in chunks:
                chunk_meta = metadata.copy()
                if self._has_critical_damage(chunk):
                    chunk_meta["chunk_type"] = "critical_damage"
                elif self._is_table_content(chunk):
                    chunk_meta["chunk_type"] = "table_data"
                else:
                    chunk_meta["chunk_type"] = "text"
                result.append(Document(page_content=chunk, metadata=chunk_meta))

        return result


def build_vectorstore(bridge_name: str, documents: list[Document]) -> FAISS:
    """문서 리스트로부터 FAISS 벡터스토어를 생성하고 저장한다.

    Args:
        bridge_name: 교량 이름.
        documents: LangChain Document 리스트 (텍스트 + 표).

    Returns:
        FAISS 벡터스토어 객체.
    """
    save_dir = Path(config.PROJECT_ROOT) / "data" / bridge_name / "faiss_index"

    # TableAwareTextSplitter로 청킹
    splitter = TableAwareTextSplitter()
    chunks = splitter.split_documents(documents)
    print(f"🔍 청킹 완료: {len(chunks)}개 청크")

    # 임베딩 생성 + FAISS 벡터스토어 구축
    embeddings = OpenAIEmbeddings(
        model=config.RAG_EMBEDDING_MODEL,
        openai_api_key=config.OPENAI_API_KEY,
    )
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # 저장
    save_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(save_dir))
    print(f"✅ 벡터스토어 구축 완료: {len(chunks)}개 청크")

    return vectorstore


def load_vectorstore(bridge_name: str) -> Optional[FAISS]:
    """저장된 FAISS 벡터스토어를 로드한다.

    Args:
        bridge_name: 교량 이름.

    Returns:
        FAISS 벡터스토어 객체. 없으면 None.
    """
    load_dir = Path(config.PROJECT_ROOT) / "data" / bridge_name / "faiss_index"

    if not load_dir.exists():
        return None

    embeddings = OpenAIEmbeddings(
        model=config.RAG_EMBEDDING_MODEL,
        openai_api_key=config.OPENAI_API_KEY,
    )
    vectorstore = FAISS.load_local(
        str(load_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vectorstore
