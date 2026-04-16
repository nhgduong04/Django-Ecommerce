"""
Signal: rollback coupon khi Order chuyển sang trạng thái CANCELLED.

Flow:
  Admin / staff đổi order.status = 'CANCELLED' → save() → signal này chạy
  → coupon.used_count -= 1, CouponUsage bị xóa.

BUG-08: Signal dùng transaction.on_commit() → khi viết test cho hành vi rollback:
  - Dùng TransactionTestCase (mỗi op auto-commit, on_commit chạy), HOẶC
  - Dùng TestCase + captureOnCommitCallbacks(execute=True) (Django 4.2+).
"""
from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Order

@receiver(pre_save, sender=Order)
def rollback_coupon_on_cancel(sender, instance, **kwargs):
    """
    Phát hiện khi Order chuyển từ trạng thái khác → CANCELLED.
    Nếu order có coupon → rollback lượt dùng.
    """
    if not instance.pk:
        # Order mới tạo, chưa có pk → bỏ qua
        return

    if instance.status != 'CANCELLED':
        # Không phải hủy → bỏ qua
        return

    try:
        previous = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if previous.status == 'CANCELLED':
        return

    # Order mới chuyển sang CANCELLED → rollback coupon nếu có
    if not previous.coupon_id:
        return

    # Chạy trong transaction để đảm bảo rollback coupon và order update là atomic
    transaction.on_commit(lambda: _do_rollback(instance.pk))


def _do_rollback(order_pk: int) -> None:
    """
    Thực hiện rollback coupon sau khi transaction cancel-order commit xong.
    Dùng on_commit để tránh deadlock với transaction đang save Order.
    """
    from coupon.services import rollback_coupon_usage
    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        return
    
    # re-verify sau khi re-fetch
    if order.status != 'CANCELLED':
        return
    rollback_coupon_usage(order)


@receiver(pre_save, sender=Order)
def sync_payment_status_on_completion(sender, instance, **kwargs):
    """
    Tự động cập nhật payment_status thành 'paid' nếu đơn hàng
    được chuyển sang trạng thái 'COMPLETED'.
    """
    if instance.status == 'COMPLETED' and instance.payment_status != 'paid':
        instance.payment_status = 'paid'
