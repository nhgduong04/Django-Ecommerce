from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from .models import Coupon, CouponUsage

DEFAULT_SHIPPING_FEE = Decimal('30000')
COUPON_SESSION_KEY = 'applied_coupon_code'


class CouponError(Exception):
    """Lỗi khi validate coupon."""


@dataclass
class DiscountResult:
    cart_discount: Decimal
    shipping_fee: Decimal
    shipping_saved: Decimal


def validate_coupon(code: str, user: User, cart_total: Decimal) -> Coupon:
    """
    Kiểm tra coupon có hợp lệ không.
    Trả về Coupon object nếu hợp lệ, raise CouponError nếu không.
    """
    try:
        coupon = Coupon.objects.get(code__iexact=code.strip())
    except Coupon.DoesNotExist:
        raise CouponError("Mã giảm giá không tồn tại.")

    if not coupon.is_active:
        raise CouponError("Mã giảm giá đã bị vô hiệu hóa.")

    now = timezone.now()
    if now < coupon.validate_from or now > coupon.validate_to:
        raise CouponError("Mã giảm giá đã hết hạn hoặc chưa đến ngày áp dụng.")

    if cart_total < coupon.min_order_value:
        raise CouponError(
            f"Đơn hàng tối thiểu {int(coupon.min_order_value):,}đ để dùng mã này."
        )

    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise CouponError("Mã giảm giá đã hết lượt sử dụng.")

    if user.is_authenticated and coupon.usage_limit_per_user is not None:
        user_used = CouponUsage.objects.filter(user=user, coupon=coupon).count()
        if user_used >= coupon.usage_limit_per_user:
            raise CouponError("Bạn đã sử dụng hết lượt dùng mã này.")

    return coupon


def calculate_discount(
    coupon: Coupon,
    cart_total: Decimal,
    shipping_fee: Decimal = DEFAULT_SHIPPING_FEE,
) -> DiscountResult:
    """
    Tính số tiền giảm trên cart và phí ship sau coupon.

    Returns:
        DiscountResult
    """
    if coupon.discount_type == 'PERCENT':
        discount = cart_total * coupon.discount_value / Decimal('100')
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
        return DiscountResult(
            cart_discount=discount.quantize(Decimal('1')),
            shipping_fee=shipping_fee,
            shipping_saved=Decimal('0'),
        )

    elif coupon.discount_type == 'FIXED':
        return DiscountResult(
            cart_discount=min(coupon.discount_value, cart_total).quantize(Decimal('1')),
            shipping_fee=shipping_fee,
            shipping_saved=Decimal('0'),
        )

    elif coupon.discount_type == 'FREESHIP':
        return DiscountResult(
            cart_discount=Decimal('0'),
            shipping_fee=Decimal('0'),
            shipping_saved=shipping_fee.quantize(Decimal('1')),
        )

    return DiscountResult(
        cart_discount=Decimal('0'),
        shipping_fee=shipping_fee,
        shipping_saved=Decimal('0'),
    )


def record_coupon_usage(coupon: Coupon, user: User, order) -> None:
    """
    Ghi nhận coupon đã được sử dụng sau khi order tạo thành công.
    Phải gọi bên trong transaction.atomic() cùng với việc tạo order.

    - Tạo bản ghi CouponUsage liên kết user + coupon + order.
    - Tăng coupon.used_count bằng SELECT FOR UPDATE để tránh race condition.
    - BUG-01 FIX: Double-check usage_limit inside lock để tránh 2 request đồng thời
      vượt qua slot cuối cùng.
    """
    # Lock row coupon để đếm chính xác trong môi trường concurrent
    locked_coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)

    # Double-check usage_limit inside lock (race condition fix)
    if locked_coupon.usage_limit is not None and locked_coupon.used_count >= locked_coupon.usage_limit:
        raise CouponError("Mã giảm giá đã hết lượt sử dụng.")

    # Double-check usage_limit_per_user inside lock
    if user.is_authenticated and locked_coupon.usage_limit_per_user is not None:
        user_used = CouponUsage.objects.filter(user=user, coupon=locked_coupon).count()
        if user_used >= locked_coupon.usage_limit_per_user:
            raise CouponError("Bạn đã sử dụng hết lượt dùng mã này.")

    locked_coupon.used_count += 1
    locked_coupon.save(update_fields=['used_count'])

    CouponUsage.objects.create(
        user=user,
        coupon=locked_coupon,
        order=order,
    )


def rollback_coupon_usage(order) -> None:
    with transaction.atomic():
        usage = CouponUsage.objects.select_related('coupon').filter(order=order).first()
        if not usage:
            return  # Đơn hàng không dùng coupon, không cần rollback

        try:
            coupon = Coupon.objects.select_for_update().get(pk=usage.coupon_id)
            coupon.used_count = max(0, coupon.used_count - 1)
            coupon.save(update_fields=['used_count'])
        except Coupon.DoesNotExist:
            pass  # Nếu coupon đã bị xóa, chỉ cần xóa usage là đủ

        usage.delete() # luôn xóa usage dù coupon có tồn tại hay không
