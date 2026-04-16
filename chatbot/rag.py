"""
RAG layer (ChromaDB) cho chatbot tư vấn.

- Index source: Product + Category + description (thông tin public)
- Persist: BASE_DIR/chroma_db (nên ignore khi dùng git)
"""

from __future__ import annotations

import functools
import os
from typing import Iterable, List


def _get_persist_dir() -> str:
    # Default: project root (myshop/) / chroma_db
    # Có thể override bằng env để dễ deploy
    return os.getenv("CHATBOT_CHROMA_DIR", os.path.join(os.getcwd(), "chroma_db"))


def _get_collection_name() -> str:
    return os.getenv("CHATBOT_CHROMA_COLLECTION", "products")


def _get_embed_model() -> str:
    return os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")


@functools.lru_cache(maxsize=1)
def _get_cached_vectorstore():
    """Module-level singleton. Created once per process lifetime."""
    return build_vectorstore()


def warmup() -> None:
    """Pre-load vectorstore into cache. Gọi từ AppConfig.ready()."""
    _get_cached_vectorstore()


def build_vectorstore():
    """
    Tạo/Load Chroma vectorstore.
    """
    from langchain_chroma import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embeddings = GoogleGenerativeAIEmbeddings(
        model=_get_embed_model(),
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    return Chroma(
        collection_name=_get_collection_name(),
        embedding_function=embeddings,
        persist_directory=_get_persist_dir(),
    )


def index_documents(docs: Iterable[dict]) -> int:
    """
    Index docs vào Chroma.

    doc format:
      - id: str (unique)
      - text: str
      - metadata: dict (optional)
    """
    from langchain_core.documents import Document

    vectorstore = _get_cached_vectorstore()
    documents: List[Document] = []
    ids: List[str] = []
    for d in docs:
        doc_id = str(d["id"])
        text = d.get("text") or ""
        if not text.strip():
            continue
        documents.append(Document(page_content=text, metadata=d.get("metadata") or {}))
        ids.append(doc_id)

    if not documents:
        return 0

    # Upsert theo ids (Chroma sẽ overwrite nếu id trùng)
    vectorstore.add_documents(documents=documents, ids=ids)
    _get_cached_vectorstore.cache_clear()  # force rebuild on next retrieve
    return len(documents)


def retrieve_context(query: str, *, k: int = 3) -> str:
    """
    Truy xuất ngữ nghĩa nhanh từ ChromaDB.
    """
    vectorstore = _get_cached_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    results = retriever.invoke(query)
    if not results:
        return ""
    chunks = []
    for doc in results:
        meta = doc.metadata or {}
        title = meta.get("title") or meta.get("name") or ""
        pid = meta.get("product_id")
        pid_txt = f" (product_id={pid})" if pid is not None else ""
        if title:
            chunks.append(f"- {title}{pid_txt}: {doc.page_content}")
        else:
            chunks.append(f"- {doc.page_content}{pid_txt}")
    return "KẾT QUẢ TÌM KIẾM NGỮ NGHĨA (RAG):\n" + "\n".join(chunks)

