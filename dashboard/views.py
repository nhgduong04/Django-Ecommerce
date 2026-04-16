from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone


def dashboard_callback(request, context):
    """
    Callback cho Unfold dashboard — truyền toàn bộ data vào template
    templates/admin/index.html.

    Dữ liệu được tính theo timezone local, window trượt theo thời điểm request.

    NOTE: Chỉ superuser mới nhìn thấy dữ liệu thống kê. Staff sẽ nhận
    context rỗng (và được middleware redirect sang trang Đơn hàng).
    """
    # ── Bảo vệ dữ liệu: chỉ superuser mới xem Dashboard ──
    if not request.user.is_superuser:
        return context
    from orders.models import Order, OrderItem
    from products.models import Product

    def month_start(dt):
        """Start of month (local tz)."""
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def add_months(dt, delta_months: int):
        """Add months while keeping local tz."""
        y = dt.year + (dt.month - 1 + delta_months) // 12
        m = (dt.month - 1 + delta_months) % 12 + 1
        return dt.replace(year=y, month=m, day=1)

    time_range = request.GET.get("time_range", "today")
    allowed = {"today", "last7", "this_month", "last_month", "year"}
    if time_range not in allowed:
        time_range = "today"

    now = timezone.now()
    local_now = timezone.localtime(now)

    # (curr_start <= created_at < curr_end) and (prev_start <= created_at < prev_end)
    if time_range == "today":
        curr_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        curr_end = local_now
        prev_start = curr_start - timedelta(days=1)
        prev_end = curr_start
        chart_mode = "hour"
        chart_title = "Doanh thu hôm nay"
        kpi_compare_label = "hôm qua"
        kpi_revenue_label = "Doanh thu hôm nay"
    elif time_range == "last7":
        # 7 ngày gần nhất (bao gồm hôm nay), tính theo mốc nửa đêm local.
        curr_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=6
        )
        curr_end = local_now
        prev_start = curr_start - timedelta(days=7)
        prev_end = curr_start
        chart_mode = "day"
        chart_title = "Doanh thu 7 ngày qua"
        kpi_compare_label = "7 ngày trước"
        kpi_revenue_label = "Doanh thu 7 ngày qua"
    elif time_range == "this_month":
        curr_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        curr_end = local_now
        prev_start_month = (curr_start - timedelta(days=1))
        prev_start = prev_start_month.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        prev_end = prev_start + timedelta(days=local_now.day)
        chart_mode = "day"
        chart_title = "Doanh thu tháng này"
        kpi_compare_label = "tháng trước"
        kpi_revenue_label = "Doanh thu tháng này"
    elif time_range == "last_month":
        curr_start = (local_now.replace(day=1) - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        curr_end = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (curr_start - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        prev_end = curr_start
        chart_mode = "day"
        chart_title = "Doanh thu tháng trước"
        kpi_compare_label = "tháng trước nữa"
        kpi_revenue_label = "Doanh thu tháng trước"
    else:  # year
        # 12 tháng gần nhất tính từ đầu tháng (local).
        end_month = month_start(local_now)
        curr_start = add_months(end_month, -11)
        curr_end = local_now
        duration = curr_end - curr_start
        prev_start = curr_start - duration
        prev_end = curr_start
        chart_mode = "month"
        chart_title = "Doanh thu 1 năm"
        kpi_compare_label = "1 năm trước"
        kpi_revenue_label = "Doanh thu 1 năm"

    context["selected_time_range"] = time_range
    context["chart_title"] = chart_title
    context["kpi_compare_label"] = kpi_compare_label

    # ─────────────────────────────────────────────
    # PHẦN 1 — KPI CARDS
    # ─────────────────────────────────────────────
    User = get_user_model()

    orders_curr = Order.objects.filter(created_at__gte=curr_start, created_at__lt=curr_end).count()
    orders_prev = Order.objects.filter(created_at__gte=prev_start, created_at__lt=prev_end).count()

    revenue_curr = (
        Order.objects.filter(created_at__gte=curr_start, created_at__lt=curr_end, is_ordered=True)
        .aggregate(t=Sum("grand_total"))["t"]
        or Decimal("0")
    )
    revenue_prev = (
        Order.objects.filter(created_at__gte=prev_start, created_at__lt=prev_end, is_ordered=True)
        .aggregate(t=Sum("grand_total"))["t"]
        or Decimal("0")
    )

    completed_curr_count = Order.objects.filter(
        created_at__gte=curr_start, created_at__lt=curr_end, is_ordered=True
    ).count()
    completed_prev_count = Order.objects.filter(
        created_at__gte=prev_start, created_at__lt=prev_end, is_ordered=True
    ).count()

    aov_curr = revenue_curr / completed_curr_count if completed_curr_count else Decimal("0")
    aov_prev = revenue_prev / completed_prev_count if completed_prev_count else Decimal("0")

    new_users_curr = User.objects.filter(
        date_joined__gte=curr_start, date_joined__lt=curr_end, is_staff=False
    ).count()
    new_users_prev = User.objects.filter(
        date_joined__gte=prev_start, date_joined__lt=prev_end, is_staff=False
    ).count()

    def growth(curr, prev):
        """Return % growth, positive = up, negative = down."""
        curr_f = float(curr)
        prev_f = float(prev)
        if prev_f == 0:
            return 100.0 if curr_f > 0 else 0.0
        return round((curr_f - prev_f) / prev_f * 100, 1)

    def fmt_growth(curr, prev):
        g = growth(curr, prev)
        return {"sign": "up" if g >= 0 else "down", "abs": abs(g), "growth_value": g}

    context["kpi_cards"] = [
        {
            "label": kpi_revenue_label,
            "value": f"{int(revenue_curr):,}".replace(",", ".") + " ₫",
            **fmt_growth(revenue_curr, revenue_prev),
        },
        {
            "label": "Tổng đơn hàng",
            "value": orders_curr,
            **fmt_growth(orders_curr, orders_prev),
        },
        {
            "label": "Giá trị đơn TB",
            "value": f"{int(aov_curr):,}".replace(",", ".") + " ₫",
            **fmt_growth(aov_curr, aov_prev),
        },
        {
            "label": "Khách hàng mới",
            "value": new_users_curr,
            **fmt_growth(new_users_curr, new_users_prev),
        },
    ]

    # ─────────────────────────────────────────────
    # PHẦN 2 — BIỂU ĐỒ ĐƯỜNG: doanh thu theo bucket thời gian
    # ─────────────────────────────────────────────
    chart_last_local = curr_end - timedelta(seconds=1)

    labels: list[str] = []
    buckets: dict = {}

    if chart_mode == "hour":
        for h in range(0, 24):
            labels.append(f"{h:02d}:00")
            buckets[h] = {"revenue": Decimal("0"), "orders": 0}
    elif chart_mode == "day":
        start_date = curr_start.date()
        end_date = chart_last_local.date()
        day_count = (end_date - start_date).days + 1
        for i in range(day_count):
            d = start_date + timedelta(days=i)
            labels.append(d.strftime("%d/%m"))
            buckets[d] = {"revenue": Decimal("0"), "orders": 0}
    else:  # month
        # 12 buckets, theo đầu tháng local.
        month0 = month_start(local_now)
        start_month = add_months(month0, -11)
        for i in range(0, 12):
            m_start = add_months(start_month, i)
            labels.append(m_start.strftime("%m/%y"))
            buckets[m_start] = {"revenue": Decimal("0"), "orders": 0}

    for order in (
        Order.objects.filter(
            created_at__gte=curr_start, created_at__lt=curr_end, is_ordered=True
        ).only("created_at", "grand_total")
    ):
        local_dt = timezone.localtime(order.created_at)
        if chart_mode == "hour":
            key = local_dt.hour
        elif chart_mode == "day":
            key = local_dt.date()
        else:
            key = local_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if key in buckets:
            buckets[key]["revenue"] += order.grand_total
            buckets[key]["orders"] += 1

    revenue_data = []
    order_data = []
    # Keep output order stable (same order as labels).
    for k in buckets.keys():
        revenue_data.append(float(buckets[k]["revenue"]))
        order_data.append(buckets[k]["orders"])

    context["chart_labels"] = json.dumps(labels)
    context["chart_revenue"] = json.dumps(revenue_data)
    context["chart_orders"] = json.dumps(order_data)

    # ─────────────────────────────────────────────
    # PHẦN 3 — DONUT: phân bố trạng thái đơn hàng trong cửa sổ hiện tại
    # ─────────────────────────────────────────────
    STATUS_CONFIG = [
        ("COMPLETED", "Hoàn thành", "#1D9E75"),
        ("PENDING", "Chờ xử lý", "#EF9F27"),
        ("PROCESSING", "Đang xử lý", "#378ADD"),
        ("CANCELLED", "Đã hủy", "#E24B4A"),
    ]
    status_counts = {
        s["status"]: s["c"]
        for s in Order.objects.filter(
            created_at__gte=curr_start, created_at__lt=curr_end
        ).values("status").annotate(c=Count("id"))
    }
    context["order_status_data"] = [
        {"label": label, "count": status_counts.get(key, 0), "color": color}
        for key, label, color in STATUS_CONFIG
    ]
    context["order_status_values"] = json.dumps(
        [status_counts.get(k, 0) for k, _, _ in STATUS_CONFIG]
    )
    context["order_status_colors"] = json.dumps([c for _, _, c in STATUS_CONFIG])

    # ─────────────────────────────────────────────
    # PHẦN 4 — TOP 5 SẢN PHẨM BÁN CHẠY (progress bar) trong cửa sổ hiện tại
    # ─────────────────────────────────────────────
    top_qs = (
        OrderItem.objects.filter(
            order__is_ordered=True, order__created_at__gte=curr_start, order__created_at__lt=curr_end
        )
        .values("product__name")
        .annotate(sold_count=Sum("quantity"))
        .order_by("-sold_count")[:5]
    )
    top_list = [{"name": r["product__name"], "sold_count": r["sold_count"] or 0} for r in top_qs]
    max_sold = top_list[0]["sold_count"] if top_list else 1
    for p in top_list:
        p["pct"] = round(p["sold_count"] / max_sold * 100)
    context["top_products"] = top_list

    # ─────────────────────────────────────────────
    # PHẦN 5 — BẢNG ĐƠN HÀNG CHỜ XỬ LÝ (PENDING) trong cửa sổ hiện tại
    # ─────────────────────────────────────────────
    context["pending_orders"] = (
        Order.objects.filter(
            status="PENDING", created_at__gte=curr_start, created_at__lt=curr_end
        )
        .select_related("user")
        .order_by("-created_at")[:8]
    )

    # ─────────────────────────────────────────────
    # PHẦN 6 — SỐ LIỆU TỔNG QUAN (sidebar nhỏ)
    # ─────────────────────────────────────────────
    context["total_products"] = Product.objects.count()
    context["total_users"] = User.objects.count()

    return context


def environment_callback(request):
    """Nhãn môi trường góc phải header Unfold."""
    from django.conf import settings

    if settings.DEBUG:
        return ["Development", "warning"]
    return ["Production", "success"]