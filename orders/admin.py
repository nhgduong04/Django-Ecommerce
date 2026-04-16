from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
from unfold.decorators import display, action
from django.db.models import TextChoices
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect
from django.urls import reverse_lazy

from .models import Order, OrderItem


def format_vnd(amount):
    if amount is not None:
        return f"{int(amount):,}".replace(',', '.')
    return '-'

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    tab = True
    # 1. Khai báo 'fields' để ấn định thứ tự các cột (từ trái sang phải)
    fields = ('product', 'variant', 'quantity', 'formatted_product_price')
    # 2. Các trường readonly (không sửa đổi nội dung)
    readonly_fields = ('product', 'variant', 'quantity', 'formatted_product_price')

    @display(description='Product price')
    def formatted_product_price(self, obj):
        if not obj:
            return '-'
        return format_vnd(obj.product_price)


class UserStatus(TextChoices):
    PENDING = "PENDING", _("Pending")
    PROCESSING = "PROCESSING", _("Processing")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELLED = "CANCELLED", _("Cancelled")

@admin.register(Order)
class OrderAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('order_number', 'full_name', 'phone', 'address', 'formatted_grand_total', 'payment_method', 'payment_status', 'show_status_customized_color', 'is_ordered', 'created_at')
    list_filter = ('status', 'is_ordered', 'payment_method', 'payment_status')
    search_fields = ('order_number', 'full_name', 'email', 'phone')
    # list_editable = ('status',)
    readonly_fields = ('coupon',)
    import_form_class = ImportForm
    export_form_class = ExportForm
    inlines = [OrderItemInline]
    actions_row = ["view_selected_order", "delete_selected_order", "print_selected_order"]

    @action(
        description=_("View selected order"),
        url_path="view-selected-order",
        icon="visibility",
    )
    def view_selected_order(self, request: HttpRequest, object_id: int):
        return redirect(reverse_lazy("admin:orders_order_change", args=[object_id]))

    @action(
        description=_("Delete selected order"),
        url_path="delete-selected-order",
        icon="delete",
        attrs={"class": "!text-red-500"}
    )
    def delete_selected_order(self, request: HttpRequest, object_id: int):
        return redirect(reverse_lazy("admin:orders_order_delete", args=[object_id]))

    @action(
        description=_("Print invoice"),
        url_path="print-selected-order",
        icon="print",
        attrs={"target": "_blank"}
    )
    def print_selected_order(self, request: HttpRequest, object_id: int):
        return redirect(reverse_lazy("admin_order_print", args=[object_id]))

    fieldsets = (
        (
            ("Order"),
            {
                "classes": ["tab"],
                "fields": [
                    "order_number",
                    "shipping_fee",
                    "discount_amount",
                    "shipping_saved",
                    "grand_total",
                    "status",
                    "coupon",
                ],
            },
        ),
        (
            ("Customer"),
            {
                "classes": ["tab"],
                "fields": [
                    "user",
                    "full_name",
                    "phone",
                    "email",
                    "address",
                    "province",
                    "district",
                    "ward",
                ],
            },
        ),
        (
            ("Payment & Notes"),
            {
                "classes": ["tab"],
                "fields": [
                    "order_total",
                    "payment_method",
                    "payment_status",
                    "momo_transaction_id",
                    "is_ordered",
                    "order_note",
                ],
            },
        ),
    )

    @display(description='Grand total')
    def formatted_grand_total(self, obj):
        return format_vnd(obj.grand_total)

    @display(
        description=_("Status"),
        ordering="status",
        label={
            UserStatus.PENDING: "info",  # green
            UserStatus.PROCESSING: "warning",  # blue
            UserStatus.COMPLETED: "success",  # green
            UserStatus.CANCELLED: "danger",  # red
        },
    )
    def show_status_customized_color(self, obj):
        return obj.status


@admin.register(OrderItem)
class OrderItemAdmin(ModelAdmin):
    list_display = ('order', 'user', 'product', 'variant', 'quantity', 'formatted_product_price')

    @display(description='Product price')
    def formatted_product_price(self, obj):
        return format_vnd(obj.product_price)
