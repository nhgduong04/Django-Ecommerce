from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('order', 'user', 'product', 'variant', 'quantity', 'product_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'full_name', 'email', 'phone', 'address', 'order_total', 'payment_method', 'payment_status', 'status', 'is_ordered', 'created_at')
    list_filter = ('status', 'is_ordered', 'payment_method', 'payment_status')
    search_fields = ('order_number', 'full_name', 'email', 'phone')
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'user', 'product', 'variant', 'quantity', 'product_price')
