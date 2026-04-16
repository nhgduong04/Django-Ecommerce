"""
LangChain Tools cho chatbot tư vấn (Django ORM).

Kiến trúc:
- Sử dụng chuẩn `@tool` decorator để tự động sinh Schema.
- Rất quan trọng cho Local LLM (Gemma) để nhận diện đúng tham số.
- Các tool được đóng gói trong build_tools(ctx) để sử dụng closure qua ToolContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.tools import tool


@dataclass(frozen=True)
class ToolContext:
    user_id: Optional[int] = None
    is_authenticated: bool = False


def _fmt_money(v) -> str:
    try:
        return f"{int(v):,}đ"
    except Exception:
        return str(v)


SIZE_ORDER = ['S', 'M', 'L', 'XL', 'XXL']


def _build_variant_breakdown(variants) -> tuple[str, int, list, list]:
    """
    Trả về (breakdown_text, total_stock, colors_list, sizes_list).
    `variants` phải được prefetch_related('variations') trước.
    """
    lines = []
    total = 0
    colors: set = set()
    sizes: set = set()

    for v in variants:
        color_name = None
        size_name = None
        for var in v.variations.all():  # dùng cache prefetch, không tốn thêm query
            if var.variation_category == 'color':
                color_name = var.get_display_name()
                colors.add(color_name)
            elif var.variation_category == 'size':
                size_name = var.get_display_name()
                sizes.add(size_name)

        label_parts = [p for p in (color_name, size_name) if p]
        label = " / ".join(label_parts) if label_parts else f"Biến thể #{v.id}"

        if v.stock > 0:
            lines.append(f"  ✓ {label}: {v.stock} chiếc")
            total += v.stock
        else:
            lines.append(f"  ✗ {label}: hết hàng")

    colors_sorted = sorted(colors)
    sizes_sorted = sorted(sizes, key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)
    return "\n".join(lines), total, colors_sorted, sizes_sorted


def build_tools(*, ctx: ToolContext) -> List:
    """
    Trả về danh sách các tool đã được bind context.
    Dùng closure để các tool truy cập được ctx (người dùng hiện tại).
    """

    @tool
    def search_products(query: str, limit: int = 5) -> str:
        """
        Tìm kiếm các sản phẩm theo tên hoặc từ khóa.
        Input: query (chuỗi tìm kiếm), limit (số lượng tối đa).
        Trả về: Danh sách sản phẩm kèm product_id, giá hiện tại và danh mục.
        Luôn dùng tool này trước để lấy product_id chính xác trước khi gọi check_stock.
        """
        from django.db.models import Q
        from products.models import Product

        q = (query or "").strip()
        if not q:
            return "Vui lòng cung cấp từ khóa tìm kiếm."

        limit_val = max(1, min(int(limit or 5), 10))
        qs = (
            Product.objects.select_related("category")
            .filter(Q(name__icontains=q) | Q(description__icontains=q))
            .order_by("-updated_at")[:limit_val]
        )

        items = list(qs)
        if not items:
            return f"Rất tiếc, shop chưa tìm thấy sản phẩm nào khớp với '{q}'."

        lines = []
        for p in items:
            try:
                price = p.get_price()
                disc = p.get_discount_percentage() or 0
            except Exception:
                price = p.price
                disc = 0
            cat = p.category.name if getattr(p, "category_id", None) else "N/A"
            lines.append(
                f"- [product_id={p.id}] {p.name} | {cat} | {_fmt_money(price)} | Giảm {disc}%"
            )
        return "Các sản phẩm tôi tìm thấy:\n" + "\n".join(lines)

    @tool
    def filter_products(
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        keyword: Optional[str] = None,
        in_stock_only: bool = True,
        limit: int = 8,
    ) -> str:
        """
        Lọc sản phẩm chuyên sâu theo danh mục, khoảng giá và từ khóa.
        Dùng khi khách hỏi 'váy dưới 500k' hoặc 'mũ đen'.
        """
        from django.db.models import Sum, Q
        from products.models import Product, ProductVariant, Category

        qs = Product.objects.select_related("category").all()

        if category:
            cat = category.strip()
            # Tìm danh mục khớp trước
            category_qs = Category.objects.filter(Q(name__icontains=cat) | Q(slug__icontains=cat))
            if category_qs.exists():
                qs = qs.filter(category__in=category_qs)
            else:
                # Nếu không khớp danh mục nào, tìm trong tên sản phẩm (fallback)
                qs = qs.filter(name__icontains=cat)

        if keyword:
            kw = keyword.strip()
            if kw:
                qs = qs.filter(Q(name__icontains=kw) | Q(description__icontains=kw))

        # Lấy danh sách thô trước để tính giá động
        items = list(qs.order_by("-updated_at")[:60])
        if not items:
            return "Không tìm thấy sản phẩm nào phù hợp với yêu cầu của bạn."

        def get_actual_price(p):
            try:
                return float(p.get_price())
            except Exception:
                return float(p.price or 0)

        # Lọc theo giá trong Python
        filtered = []
        for p in items:
            pr = get_actual_price(p)
            if max_price is not None and pr > max_price:
                continue
            if min_price is not None and pr < min_price:
                continue
            filtered.append((p, pr))

        if not filtered:
            return "Tôi tìm thấy sản phẩm nhưng không có cái nào nằm trong khoảng giá bạn yêu cầu."

        # Giới hạn kết quả trả về
        filtered = filtered[:max(1, min(int(limit or 8), 12))]

        # Lấy tồn kho hàng loạt
        product_ids = [p.id for (p, _) in filtered]
        stock_data = (
            ProductVariant.objects.filter(product_id__in=product_ids, is_active=True)
            .values("product")
            .annotate(total=Sum("stock"))
        )
        stock_map = {item["product"]: item["total"] or 0 for item in stock_data}

        lines = []
        for p, pr in filtered:
            stock = stock_map.get(p.id, 0)
            if in_stock_only and stock <= 0:
                continue
            
            try:
                disc = p.get_discount_percentage() or 0
            except Exception:
                disc = 0
            cat_name = p.category.name if getattr(p, "category_id", None) else "N/A"
            lines.append(f"- #{p.id} {p.name} | {cat_name} | {_fmt_money(pr)} | -{disc}% | Kho: {stock}")

        if not lines:
            return "Các sản phẩm phù hợp hiện đều đã hết hàng."
        
        return "Danh sách sản phẩm tôi lọc được cho bạn:\n" + "\n".join(lines)

    @tool
    def check_stock(product_id: int, color: Optional[str] = None, size: Optional[str] = None) -> str:
        """
        Kiểm tra tồn kho của một sản phẩm theo product_id.
        - Không có color/size: trả về bảng đầy đủ từng biến thể (màu/size) kèm số lượng tồn.
          Dùng khi khách hỏi sản phẩm còn hàng không, có những màu gì, size gì,
          biến thể nào còn/hết hàng.
        - Có color và/hoặc size: trả về tổng tồn kho cho đúng combo đó.
          Dùng khi khách hỏi "còn màu đỏ size M không?".
        """
        from django.db.models import Sum
        from products.models import Product, ProductVariant

        p = Product.objects.filter(id=product_id).first()
        if not p:
            return f"Không tìm thấy sản phẩm có mã #{product_id}."

        # ── Chế độ lọc (color / size được chỉ định) ──────────────────────
        if color or size:
            variants = ProductVariant.objects.filter(product=p, is_active=True)
            if color:
                variants = variants.filter(
                    variations__variation_category="color",
                    variations__variation_value__iexact=color.strip(),
                )
            if size:
                variants = variants.filter(
                    variations__variation_category="size",
                    variations__variation_value__iexact=size.strip(),
                )
            total = variants.aggregate(s=Sum("stock")).get("s") or 0
            suffix = []
            if color:
                suffix.append(f"màu {color}")
            if size:
                suffix.append(f"size {size}")
            desc = f"{p.name} ({', '.join(suffix)})"
            if total > 0:
                return f"{desc} hiện còn {total} chiếc trong kho."
            return f"Rất tiếc, {desc} hiện tại đã hết hàng."

        # ── Chế độ tổng quan (không lọc) — prefetch tránh N+1 ─────────────
        all_variants = list(
            ProductVariant.objects.filter(product=p, is_active=True)
            .prefetch_related('variations')
        )
        if not all_variants:
            return f"Sản phẩm {p.name} hiện chưa có biến thể nào."

        breakdown, total, colors, sizes = _build_variant_breakdown(all_variants)

        color_summary = ", ".join(colors) if colors else "không có dữ liệu"
        size_summary = ", ".join(sizes) if sizes else "không có dữ liệu"
        availability = "còn hàng" if total > 0 else "hết hàng toàn bộ"

        header = (
            f"Sản phẩm: {p.name}\n"
            f"Màu sắc ({len(colors)} màu): {color_summary}\n"
            f"Kích cỡ ({len(sizes)} size): {size_summary}\n"
            f"Trạng thái: {availability} (tổng {total} chiếc)\n"
            f"Chi tiết từng biến thể:"
        )
        return f"{header}\n{breakdown}"

    @tool
    def validate_coupon(code: str, order_value: float = 0) -> str:
        """
        Kiểm tra tính hợp lệ của mã giảm giá (coupon).
        Input: code (mã coupon), order_value (tổng giá trị đơn hàng hiện tại).
        """
        from django.utils import timezone
        from coupon.models import Coupon

        c = (code or "").strip().upper()
        if not c:
            return "Vui lòng cung cấp mã coupon."

        coupon = Coupon.objects.filter(code__iexact=c).first()
        if not coupon:
            return f"Mã coupon '{c}' không tồn tại trong hệ thống."
        if not coupon.is_active:
            return "Mã coupon này hiện đã bị tạm ngưng."
        
        now = timezone.now()
        if coupon.validate_from and now < coupon.validate_from:
            return "Mã coupon này chưa đến ngày bắt đầu sử dụng."
        if coupon.validate_to and now > coupon.validate_to:
            return "Mã coupon này đã hết hạn sử dụng."

        if order_value and float(coupon.min_order_value or 0) > float(order_value):
            return f"Mã này chỉ áp dụng cho đơn hàng từ {_fmt_money(coupon.min_order_value)} trở lên."

        desc = f"Giảm {coupon.discount_value}"
        if coupon.discount_type == "PERCENT":
            desc = f"Giảm {coupon.discount_value}%"
        
        return f"Mã '{coupon.code}' hợp lệ! {desc}. Chúc bạn mua sắm vui vẻ."

    @tool
    def get_my_recent_orders(limit: int = 3) -> str:
        """
        Lấy danh sách các đơn hàng gần nhất của người dùng hiện tại.

        """
        if not ctx.is_authenticated or not ctx.user_id:
            return "Bạn cần đăng nhập để xem lịch sử mua hàng cá nhân."
        
        from orders.models import Order
        limit_val = max(1, min(int(limit or 3), 5))
        orders = list(Order.objects.filter(user_id=ctx.user_id).order_by("-created_at")[:limit_val])
        
        if not orders:
            return "Bạn chưa có đơn hàng nào tại DUNE."

        lines = [f"- Đơn {o.order_number} | {o.status} | Tổng: {_fmt_money(o.grand_total)} | Ngày: {o.created_at.strftime('%d/%m/%Y')}" for o in orders]
        return "Đây là các đơn hàng gần nhất của bạn:\n" + "\n".join(lines)

    @tool
    def get_order_status(order_number: str) -> str:
        """
        Tra cứu trạng thái chi tiết của một đơn hàng cụ thể.
        Chỉ xem được đơn hàng của chính mình.
        """
        if not ctx.is_authenticated or not ctx.user_id:
            return "Vui lòng đăng nhập để tra cứu trạng thái đơn hàng."

        num = (order_number or "").strip().upper()
        if not num:
            return "Vui lòng cung cấp mã đơn hàng (ví dụ: #ORDER123)."
        
        # Xóa dấu # nếu khách nhập vào
        num = num.replace("#", "")

        from orders.models import Order
        o = Order.objects.filter(user_id=ctx.user_id, order_number__iexact=num).first()
        
        if not o:
            return f"Tôi không tìm thấy đơn hàng #{num} của bạn (hoặc bạn không có quyền xem đơn này)."

        return (
            f"Thông tin đơn hàng #{o.order_number}:\n"
            f"- Trạng thái: {o.status}\n"
            f"- Thanh toán: {o.payment_method} ({o.get_payment_status_display() if hasattr(o, 'get_payment_status_display') else o.payment_status})\n"
            f"- Tổng tiền: {_fmt_money(o.grand_total)}\n"
            f"- Ngày đặt: {o.created_at.strftime('%d/%m/%Y %H:%M')}"
        )

    @tool
    def sql_query(sql: str) -> str:
        """
        Thực thi câu lệnh SQL SELECT trên cơ sở dữ liệu (chế độ read-only).
        Dùng khi cần tính toán tổng hợp chính xác:
          - Top sản phẩm bán chạy nhất
          - Tổng tồn kho theo danh mục
          - Số đơn hàng theo trạng thái
          - Doanh thu theo khoảng thời gian
        KHÔNG dùng để tra cứu chi tiết từng sản phẩm (dùng search_products cho việc đó).
        Chỉ hỗ trợ SELECT. Không được dùng INSERT/UPDATE/DELETE.

        Các bảng được phép truy vấn:
          products_product, products_category, products_productvariant,
          products_variation, products_promotion, products_productgallery,
          products_review, orders_order, orders_orderitem,
          carts_cart, carts_cartitem, coupon_coupon, coupon_couponusage.

        Ví dụ — top 5 sản phẩm bán chạy:
          SELECT p.name, SUM(oi.quantity) as sold
          FROM products_product p
          JOIN orders_orderitem oi ON oi.product_id = p.id
          JOIN orders_order o ON o.id = oi.order_id
          WHERE o.is_ordered = 1
          GROUP BY p.id ORDER BY sold DESC LIMIT 5
        """
        from chatbot.sql_tool import execute_readonly_sql
        return execute_readonly_sql(sql)

    @tool
    def get_my_cart() -> str:
        """
        Lấy thông tin chi tiết các sản phẩm đang có trong giỏ hàng và tổng tiền.

        Trả về danh sách cart_item_id, sản phẩm, màu sắc, kích cỡ, số lượng.
        """
        if not ctx.is_authenticated or not ctx.user_id:
            return "Vui lòng đăng nhập để xem giỏ hàng."

        from django.contrib.auth.models import User
        from carts.services import get_cart_summary
        
        user = User.objects.filter(id=ctx.user_id).first()
        if not user:
            return "Không tìm thấy thông tin người dùng."

        summary = get_cart_summary(user=user)
        items = summary.items

        if not items:
            return "Giỏ hàng của bạn đang trống."

        lines = []
        for i in items:
            color = ""
            size = ""
            if hasattr(i, 'variations'):
                for v in i.variations.all():
                    if v.variation_category == "color":
                        color = v.variation_value
                    if v.variation_category == "size":
                        size = v.variation_value
            elif hasattr(i, 'variant') and i.variant:
                for v in i.variant.variations.all():
                    if v.variation_category == "color":
                        color = v.variation_value
                    if v.variation_category == "size":
                        size = v.variation_value
                        
            variant_desc = f"Màu: {color}" if color else ""
            if size:
                variant_desc += f", Size: {size}"
            
            lines.append(
                f"- [cart_item_id={i.id}] {i.variant.product.name} | {variant_desc} | Đơn giá: {_fmt_money(i.variant.get_price())} | Số lượng: {i.quantity} | Thành tiền: {_fmt_money(i.sub_total())}"
            )
        
        return "GIỎ HÀNG CỦA BẠN:\n" + "\n".join(lines) + f"\n\nTổng cộng: {_fmt_money(summary.total)} (Chưa gồm VAT, ship, coupon)."

    @tool
    def add_to_cart(product_id: int, color: str, size: str, quantity: int = 1) -> str:
        """
        Thêm một sản phẩm vào giỏ hàng.
        Bắt buộc phải có color (màu sắc) và size (kích cỡ) chính xác.
        Luôn gọi tool `check_stock(product_id)` TRƯỚC để xem tồn kho 
        và danh sách biến thể (color/size hợp lệ) nếu thiếu thông tin từ khách.
        """
        if not ctx.is_authenticated or not ctx.user_id:
            return "Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng."

        from django.contrib.auth.models import User
        from products.models import Product, ProductVariant
        from carts.services import add_variant_to_user_cart, OutOfStockError

        p = Product.objects.filter(id=product_id).first()
        if not p:
            return f"Không tìm thấy sản phẩm #{product_id}."

        variants = ProductVariant.objects.filter(product=p, is_active=True)
        if color:
             variants = variants.filter(variations__variation_category="color", variations__variation_value__iexact=color.strip())
        if size:
             variants = variants.filter(variations__variation_category="size", variations__variation_value__iexact=size.strip())
        
        variants = variants.distinct()
        var_count = variants.count()
        if var_count == 0:
             return f"Rất tiếc, sản phẩm #{product_id} không có (hoặc đã hết) màu '{color}' size '{size}'. Gọi lại tool check_stock({product_id}) để xem chi tiết."
        elif var_count > 1:
             return f"Tìm thấy nhiều hơn 1 biến thể với cấu hình ({color}, {size}). Hệ thống bị lỗi data không thể thêm vào giỏ."
             
        variant = variants.first()
        if quantity > variant.stock:
             return f"Rất tiếc không đủ hàng. Số lượng tồn kho hiện tại chỉ còn {variant.stock} chiếc."
             
        user = User.objects.get(id=ctx.user_id)
        try:
             cart_item, cart_qty = add_variant_to_user_cart(user=user, variant_id=variant.id, quantity=quantity)
             return f"Đã thêm thành công {quantity} sản phẩm '{p.name}' (Màu {color}, Size {size}) vào giỏ. Hiện giỏ hàng của bạn có {cart_qty} loại món khác nhau."
        except OutOfStockError as exc:
             return f"Hết hàng! Kho còn {exc.available} nhưng bạn đã có / yêu cầu tới {exc.requested} chiếc."
        except Exception as str_err:
             return f"Lỗi không xác định khi thêm vào giỏ: {str(str_err)}"

    @tool
    def modify_cart_item(cart_item_id: int, action: str, quantity: Optional[int] = None) -> str:
        """
        Sửa số lượng hoặc xóa một món hàng trong giỏ.
        action chỉ có thể là: 'update' (gán bằng quantity), 'add' (tăng 1), 'remove' (giảm 1), 'delete' (xóa hẳn).
        (Khi 'update', bắt buộc phải truyền parameter quantity).
        Để lấy được cart_item_id, AI phải gọi get_my_cart() trước.
        """
        if not ctx.is_authenticated or not ctx.user_id:
            return "Vui lòng đăng nhập để sửa giỏ hàng."
            
        from carts.models import CartItem
        
        item = CartItem.objects.filter(id=cart_item_id, user_id=ctx.user_id, is_active=True).first()
        if not item:
            return f"Không tìm thấy món hàng ID {cart_item_id} trong giỏ của bạn (hoặc bạn đã xóa nó)."
            
        variant = item.variant
        if not variant:
             return "Món hàng không map được tới sản phẩm hợp lệ."

        if action == "delete":
            item.delete()
            return f"Đã xóa thành công món ID {cart_item_id} khỏi giỏ."
            
        if action == "add":
            if item.quantity + 1 > variant.stock:
                return f"Không đủ sản phẩm trong kho. Kho chỉ còn {variant.stock} chiếc."
            item.quantity += 1
            item.save(update_fields=['quantity'])
            return f"Đã tăng thêm. Số lượng mới là {item.quantity}. Thành tiền: {_fmt_money(item.sub_total())}."
            
        if action == "remove":
            if item.quantity > 1:
                item.quantity -= 1
                item.save(update_fields=['quantity'])
                return f"Đã giảm số lượng. Mới: {item.quantity}. Thành tiền: {_fmt_money(item.sub_total())}."
            else:
                item.delete()
                return f"Đã xóa món ID {cart_item_id} vì số lượng về 0."

        if action == "update":
            if not quantity or quantity <= 0:
                item.delete()
                return "Đã xóa do số lượng <= 0."
            if quantity > variant.stock:
                return f"Không đủ sản phẩm trong kho. Kho chỉ còn {variant.stock} chiếc."
            item.quantity = quantity
            item.save(update_fields=['quantity'])
            return f"Cập nhật thành công. Số lượng mới: {item.quantity}. Thành tiền: {_fmt_money(item.sub_total())}"
            
        return "action không hợp lệ. Chọn 'update', 'add', 'remove', hoặc 'delete'."

    # Trả về danh sách tool đã được khởi tạo
    return [
        search_products,
        filter_products,
        check_stock,
        validate_coupon,
        get_my_recent_orders,
        get_order_status,
        sql_query,
        get_my_cart,
        add_to_cart,
        modify_cart_item,
    ]
