"""
Agentic SQL Tool — LLM tự sinh SQL → validate → execute (read-only).

Nguyên tắc an toàn (3 lớp):
  1. Chỉ chấp nhận câu lệnh bắt đầu bằng SELECT
  2. Chặn các từ khóa nguy hiểm: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE,
     GRANT, REVOKE, CREATE, EXEC, EXECUTE, CALL, LOAD DATA, INTO OUTFILE, --, /*
  3. Whitelist bảng được phép — không có bảng auth_user hay accounts_*
"""
from __future__ import annotations

import logging
import re
from typing import Any

from django.db import connections

logger = logging.getLogger(__name__)

# ── Safety configuration ─────────────────────────────────────────────
MAX_ROWS = 20
DB_ALIAS = "chatbot_readonly"

# Bảng được phép truy vấn — chỉ dữ liệu sản phẩm/đơn hàng, không có user/auth
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "products_product",
        "products_category",
        "products_variation",
        "products_productvariant",
        "products_promotion",
        "products_productgallery",
        "products_review",
        "products_productvariant_variations",
        "products_promotion_products",
        "orders_order",
        "orders_orderitem",
        "carts_cart",
        "carts_cartitem",
        "coupon_coupon",
        "coupon_couponusage",
    }
)

# Từ khóa tuyệt đối bị chặn (case-insensitive)
_BLOCKED_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE"
    r"|EXEC|EXECUTE|CALL|LOAD\s+DATA|INTO\s+OUTFILE|xp_|sp_)\b"
    r"|--|/\*",
    re.IGNORECASE,
)

# Chỉ cho phép SELECT ở đầu câu lệnh
_SELECT_ONLY_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


def _validate_sql(sql: str) -> str | None:
    """
    Validate SQL query. Trả về thông báo lỗi nếu không hợp lệ, None nếu OK.
    """
    sql = sql.strip()
    if not sql:
        return "Câu lệnh SQL không được để trống."

    if not _SELECT_ONLY_PATTERN.match(sql):
        return "Chỉ cho phép câu lệnh SELECT. Không hỗ trợ INSERT/UPDATE/DELETE và các lệnh khác."

    if _BLOCKED_PATTERN.search(sql):
        return "Câu lệnh chứa từ khóa bị cấm. Chỉ được dùng SELECT thuần túy."

    # Kiểm tra bảng được truy vấn
    referenced_tables = set(re.findall(r"(?:FROM|JOIN)\s+`?(\w+)`?", sql, re.IGNORECASE))
    disallowed = referenced_tables - ALLOWED_TABLES
    if disallowed:
        return (
            f"Bảng không được phép truy vấn: {', '.join(sorted(disallowed))}. "
            f"Chỉ có thể truy vấn: {', '.join(sorted(ALLOWED_TABLES))}."
        )

    return None  # valid


def execute_readonly_sql(sql: str) -> str:
    """
    Thực thi SQL query trên read-only connection và trả về kết quả dạng text.
    Được gọi từ LangChain @tool trong tools.py.
    """
    error = _validate_sql(sql)
    if error:
        return f"SQL không hợp lệ: {error}"

    try:
        with connections[DB_ALIAS].cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in (cursor.description or [])]
            rows: list[tuple[Any, ...]] = cursor.fetchmany(MAX_ROWS)

        if not rows:
            return "Truy vấn thành công nhưng không có kết quả nào."

        # Format kết quả dạng bảng text
        header = " | ".join(columns)
        separator = "-" * len(header)
        lines = [header, separator]
        for row in rows:
            lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))

        note = f"\n(Hiển thị tối đa {MAX_ROWS} dòng)" if len(rows) == MAX_ROWS else ""
        return "\n".join(lines) + note

    except Exception as exc:
        logger.exception("Agentic SQL execution error")
        return f"Lỗi khi thực thi SQL: {exc}"