from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Coupon(models.Model):
    DISCOUNT_TYPE = (
        ('PERCENT', 'Phần trăm (%)'),
        ('FIXED',   'Tiền mặt (VNĐ)'),
        ('FREESHIP','Miễn phí vận chuyển'),
    )

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)  # Tổng số lần có thể sử dụng
    used_count = models.PositiveIntegerField(default=0)  # Số lần đã được sử dụng
    usage_limit_per_user = models.PositiveIntegerField(null=True, blank=True)  # Số lần mỗi người dùng có thể sử dụng
    validate_from = models.DateTimeField()
    validate_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

class CouponUsage(models.Model):
    """Lịch sử dùng coupon — dùng để check per_user_limit và rollback khi huỷ đơn."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, null=True, blank=True)  # Liên kết đến đơn hàng nếu có
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'coupon', 'order')  # Đảm bảo mỗi user chỉ dùng coupon này 1 lần cho mỗi đơn hàng

    def __str__(self):
        return f"{self.user.username} used {self.coupon.code} at {self.used_at}"