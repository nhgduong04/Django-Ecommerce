"""
Middleware phân quyền Admin cho Staff.

Khi tài khoản staff (không phải superuser) truy cập trang chủ Admin (/admin/),
hệ thống sẽ tự động chuyển hướng họ sang trang Danh sách Đơn hàng.

Middleware này KHÔNG ảnh hưởng đến:
- Các URL admin khác (changelist, change, add, …)
- Superuser
- Người dùng chưa đăng nhập (Django sẽ redirect sang trang login)
"""

from django.shortcuts import redirect
from django.urls import reverse


class StaffAdminRedirectMiddleware:
    """
    Redirect staff (non-superuser) từ trang chủ Admin sang trang Đơn hàng.

    Chỉ can thiệp vào đúng URL /admin/ (exact match) với GET request.
    Mọi request khác đều được xử lý bình thường.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Chỉ can thiệp khi:
        # 1. Request là GET (không phải POST/AJAX)
        # 2. URL chính xác là /admin/ (trang chủ admin)
        # 3. User đã đăng nhập, là staff, nhưng KHÔNG phải superuser
        if (
            request.method == "GET"
            and request.path.rstrip("/") == reverse("admin:index").rstrip("/")
            and hasattr(request, "user")
            and request.user.is_authenticated
            and request.user.is_staff
            and not request.user.is_superuser
        ):
            # CHỈ redirect nếu staff có quyền xem đơn hàng để tránh lỗi 403
            if request.user.has_perm("orders.view_order"):
                return redirect(reverse("admin:orders_order_changelist"))

        return self.get_response(request)
