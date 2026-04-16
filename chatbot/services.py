"""
Chatbot service – LangGraph ReAct Agent pipeline.

Kiến trúc:
  AI nhận câu hỏi → tự suy luận (Thought) → tự gọi tool (RAG / ORM)
  → đọc kết quả (Observation) → tổng hợp trả lời (Final Answer).

  Không còn heuristic thủ công (keyword matching).
  LangGraph tự xây graph: LLM ↔ Tools với vòng lặp tự động.
"""

from __future__ import annotations

import functools
import os
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from .tools import build_tools, ToolContext
from .rag import retrieve_context

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


@functools.lru_cache(maxsize=None)
def _get_cached_llm(model_name: str) -> "ChatGoogleGenerativeAI":
    """
    Stateless LLM instance, cached per model name.
    Safe to share across requests — ChatGoogleGenerativeAI holds no request state.
    API key is captured at first call; key rotation requires process restart.
    """
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Trợ lý tư vấn DUNE – thời trang.\n\n"
    "TOOLS:\n"
    "• rag_search – mô tả SP, chính sách, FAQ.\n"
    "• search_products – tìm SP theo tên, lấy product_id/giá/danh mục.\n"
    "• filter_products – lọc SP theo danh mục/keyword/khoảng giá.\n"
    "• check_stock – tồn kho + biến thể theo product_id (tùy chọn color/size).\n"
    "• validate_coupon – kiểm tra mã giảm giá.\n"
    "• get_my_recent_orders – đơn gần đây.\n"
    "• get_order_status – trạng thái đơn theo mã.\n"
    "• sql_query – SELECT tổng hợp (bán chạy, tồn kho, số đơn). KHÔNG dùng để tra SP cụ thể.\n"
    "• get_my_cart – Xem giỏ hàng hiện tại của khách.\n"
    "• add_to_cart – Thêm sản phẩm vào giỏ hàng (cần biết product_id, color, size).\n"
    "• modify_cart_item – Sửa/xóa một sản phẩm đang có trong giỏ (cần cart_item_id).\n\n"
    "DANH MỤC: TOPS (áo thun/phông/croptop/sơ mi) · BOTTOMS (quần/chân váy) · "
    "OUTERWEARS (khoác/gió/hoodie/jacket) · ACCESSORIES (mũ/phụ kiện/tất/kính)\n\n"
    "QUY TẮC:\n"
    "1. Chỉ trả lời trong phạm vi shop: SP, giá, tồn kho, đơn hàng, thanh toán, đổi trả, vận chuyển.\n"
    "2. Hỏi thông tin SP: gọi rag_search + search_products cùng lúc.\n"
    "3. Hỏi tồn kho/màu/size:\n"
    "   - Câu hỏi mới hoặc tiếp nối (biết tên SP từ lịch sử): search_products(tên SP) → lấy product_id → check_stock(product_id).\n"
    "   - Hỏi 'có màu gì / size gì': check_stock(product_id) KHÔNG truyền color/size → trả về toàn bộ màu + size còn hàng.\n"
    "   - Hỏi 'còn màu X size Y không': check_stock(product_id, color=X, size=Y).\n"
    "   KHÔNG tự bịa product_id mà không gọi search_products trước.\n"
    "4. Lọc SP theo danh mục/khoảng giá:\n"
    "   - Khách nói 'muốn mua X', 'tìm X', 'cho xem X' → gọi NGAY filter_products(category=DANH_MỤC, keyword=X). KHÔNG hỏi thêm trước.\n"
    "   - Câu trả lời về tài chính/budget ('dưới Y', 'không quá Y', 'khoảng Y', 'tài chính Y') → đây là max_price; kết hợp với SP/danh mục từ lịch sử chat rồi gọi filter_products.\n"
    "   - Quy đổi VND: 500k=500000 · 1tr/1triệu=1000000 · 1.5tr=1500000 · 2tr=2000000.\n"
    "   - Map tên VN → DANH MỤC: quần/jeans/short=BOTTOMS · áo/thun/sơmi/croptop=TOPS · khoác/hoodie/jacket=OUTERWEARS · mũ/phụkiện/tất=ACCESSORIES.\n"
    "5. Thống kê / đếm SP: dùng sql_query SELECT.\n"
    "   - Đếm SP theo danh mục: SELECT c.name, COUNT(p.id) FROM products_product p JOIN products_category c ON p.category_id=c.id GROUP BY c.name\n"
    "   - Bán chạy/doanh thu: thêm WHERE o.is_ordered=1 khi JOIN orders_order.\n"
    "   KHÔNG query bảng auth_user/accounts_* hay trả về email/mật khẩu.\n"
    "6. KHÔNG bịa số liệu – gọi tool nếu thiếu; vẫn thiếu thì hỏi lại ≤2 câu.\n"
    "7. KHÔNG tiết lộ dữ liệu người khác.\n"
    "8. Quản lý giỏ hàng:\n"
    "   - Khách muốn mua/thêm sản phẩm: Gọi search_products hoặc dùng ID có sẵn, hỏi màu/size/số lượng nếu chưa rõ -> gọi check_stock -> đủ thông tin thì gọi add_to_cart.\n"
    "   - Khách hỏi giỏ hàng hoặc thành tiền: Gọi get_my_cart.\n"
    "   - Khách muốn sửa/xóa mặt hàng: Gọi get_my_cart (để lấy cart_item_id) -> gọi modify_cart_item.\n"
    "9. KHÔNG thông báo trước hành động ('Tôi sẽ...', 'Xin chờ...', 'Đang tra...'). Gọi tool ngay, trả về kết quả.\n"
    "   Khi đã có đủ thông tin (danh mục hoặc tên SP), gọi tool TRƯỚC — KHÔNG hỏi thêm về kiểu dáng/màu/size khi chưa có kết quả.\n"
    "10. Trả lời tiếng Việt, ngắn gọn, dùng bullet khi liệt kê.\n"
)


# ── RAG wrapper tool ─────────────────────────────────────────────────
def _build_rag_tool() -> StructuredTool:
    """Bọc retrieve_context thành tool để Agent tự quyết định gọi."""

    def rag_search(query: str) -> str:
        """Tìm kiếm ngữ nghĩa (semantic search) trong knowledge base.
        Chứa mô tả sản phẩm, chính sách shop, thông tin chung.
        Dùng khi cần tìm sản phẩm theo đặc điểm/chất liệu hoặc tra chính sách.
        Input: query – câu tìm kiếm tự nhiên."""
        result = retrieve_context(query, k=3)
        return result or "Không tìm thấy thông tin liên quan trong knowledge base."

    return StructuredTool.from_function(
        func=rag_search,
        name="rag_search",
        description=(
            "Tìm kiếm ngữ nghĩa trong knowledge base (mô tả sản phẩm, chính sách "
            "shop, chất liệu, FAQ). Dùng khi khách hỏi chung về sản phẩm hoặc "
            "chính sách. Input: query (chuỗi tìm kiếm)."
        ),
    )


# ── Session history → LangChain messages ─────────────────────────────
def _build_chat_history(history: list[dict] | None) -> list[HumanMessage | AIMessage]:
    """Chuyển lịch sử session (list[dict]) → LangChain messages (5 cặp)."""
    messages: list[HumanMessage | AIMessage] = []
    for m in (history or [])[-10:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role in ("assistant", "bot"):
            messages.append(AIMessage(content=content))
    return messages


# ── Chính: Agent pipeline ────────────────────────────────────────────
def get_chat_reply_text(
    user_input: str,
    *,
    model: Optional[str] = None,
    user=None,
    history: list[dict] | None = None,
) -> str:
    """
    LangGraph ReAct Agent pipeline:
      1. Khởi tạo ChatGoogleGenerativeAI + tools (ORM + RAG)
      2. create_react_agent xây graph tự động: LLM ↔ Tools
      3. Agent tự suy luận, tự gọi tool, tự tổng hợp
      4. Xem reasoning trong terminal log
    """
    try:
        # ── 1. LLM ──────────────────────────────────────────────────
        llm = _get_cached_llm(model or DEFAULT_MODEL)

        # ── 2. Tools (ORM + RAG) ────────────────────────────────────
        ctx = ToolContext(
            user_id=getattr(user, "id", None),
            is_authenticated=bool(getattr(user, "is_authenticated", False)),
        )
        tools = build_tools(ctx=ctx)
        tools.append(_build_rag_tool())

        # ── 3. Agent graph ──────────────────────────────────────────
        #   create_react_agent tạo graph: LLM → quyết định gọi tool
        #   → nhận observation → lặp lại cho đến khi có final answer
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )

        # ── 4. Build messages ───────────────────────────────────────
        chat_history = _build_chat_history(history)
        messages = [
            *chat_history,
            HumanMessage(content=user_input),
        ]

        # ── 5. Invoke ──────────────────────────────────────────────
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": 12},
        )

        # ── 6. Trích xuất final answer ──────────────────────────────
        all_msgs = result.get("messages", [])
        if all_msgs:
            last = all_msgs[-1]
            content = getattr(last, "content", None)
            # Gemini (langchain_google_genai) đôi khi trả content dạng list[Part]
            # thay vì plain str — cần flatten thành string trước khi kiểm tra.
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
                content = " ".join(parts).strip()
            if content and isinstance(content, str) and content.strip():
                return content.strip()

        return "Mình chưa có câu trả lời phù hợp."

    except Exception:
        logger.exception("Chatbot Agent Error")
        return "Xin lỗi, hệ thống chatbot đang bận. Bạn thử lại sau giúp mình nhé."