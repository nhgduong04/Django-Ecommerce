from django.contrib import admin
from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'min_order_value',
                    'usage_limit', 'used_count', 'validate_from', 'validate_to', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    readonly_fields = ('used_count',)


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'coupon', 'order', 'used_at')
    list_filter = ('coupon',)
    search_fields = ('user__username', 'coupon__code')
    raw_id_fields = ('order',)
