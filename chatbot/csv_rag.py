"""
CSV Knowledge Loader — đọc CSV files và chuẩn bị documents để index vào ChromaDB.

Tách biệt khỏi DB-based indexing để có thể cập nhật riêng.
CSV files là dữ liệu TĨNH — chỉ cần reindex khi file thay đổi.

Document format khớp với index_documents() trong rag.py:
    {"id": str, "text": str, "metadata": dict}
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


# ── Product static descriptions ───────────────────────────────────────

def _iter_products_static() -> Generator[dict, None, None]:
    path = KNOWLEDGE_DIR / "products_static.csv"
    if not path.exists():
        logger.warning("products_static.csv not found — skipping")
        return
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Skip rows with no meaningful content
            name = (row.get("name") or "").strip()
            if not name:
                continue

            parts = [f"Sản phẩm: {name}"]
            if row.get("category"):
                parts.append(f"Danh mục: {row['category']}")
            if row.get("material"):
                parts.append(f"Chất liệu: {row['material']}")
            if row.get("description"):
                parts.append(f"Mô tả: {row['description']}")
            if row.get("care_instructions"):
                parts.append(f"Bảo quản: {row['care_instructions']}")
            if row.get("tags"):
                parts.append(f"Tags: {row['tags']}")

            yield {
                "id": f"product_static_{row['id']}",
                "text": "\n".join(parts),
                "metadata": {
                    "type": "product_static",
                    "name": name,
                    "category": row.get("category", ""),
                },
            }


# ── Shop policies ─────────────────────────────────────────────────────

def _iter_policies() -> Generator[dict, None, None]:
    path = KNOWLEDGE_DIR / "policies.csv"
    if not path.exists():
        logger.warning("policies.csv not found — skipping")
        return
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = (row.get("title") or "").strip()
            content = (row.get("content") or "").strip()
            if not title and not content:
                continue
            yield {
                "id": f"policy_{row['id']}",
                "text": f"{title}\n{content}",
                "metadata": {
                    "type": "policy",
                    "topic": row.get("topic", ""),
                    "title": title,
                },
            }


# ── FAQ ───────────────────────────────────────────────────────────────

def _iter_faq() -> Generator[dict, None, None]:
    path = KNOWLEDGE_DIR / "faq.csv"
    if not path.exists():
        logger.warning("faq.csv not found — skipping")
        return
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            question = (row.get("question") or "").strip()
            answer = (row.get("answer") or "").strip()
            if not question and not answer:
                continue
            yield {
                "id": f"faq_{row['id']}",
                "text": f"Hỏi: {question}\nĐáp: {answer}",
                "metadata": {
                    "type": "faq",
                    "tags": row.get("tags", ""),
                },
            }


# ── Public API ────────────────────────────────────────────────────────

def load_csv_documents() -> list[dict]:
    """Trả về tất cả documents từ mọi CSV files, sẵn sàng để index vào ChromaDB."""
    docs: list[dict] = []
    for gen in (_iter_products_static, _iter_policies, _iter_faq):
        docs.extend(gen())
    logger.info("CSV knowledge loaded: %d documents", len(docs))
    return docs