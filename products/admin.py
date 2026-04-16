from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Category, Product, Variation, ProductVariant, Promotion, ProductGallery, Review
from .forms import ProductVariantForm, ProductVariantInlineForm, ProductGalleryForm, ProductGalleryInlineForm
from unfold.decorators import action, display
from unfold.contrib.filters.admin import SliderNumericFilter
from unfold.paginator import InfinitePaginator
from django.utils.translation import gettext_lazy as _
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy


# Register your models here.
class ProductVariantInline(TabularInline):
    model = ProductVariant
    form = ProductVariantInlineForm
    extra = 0
    tab = True

    def get_queryset(self, request):
        """Tối ưu hóa query để tránh N+1 và đệ quy."""
        return super().get_queryset(request).prefetch_related('variations')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Lọc danh sách variations theo product hiện tại."""
        if db_field.name == "variations":
            # Lấy product_id từ URL
            product_id = request.resolver_match.kwargs.get('object_id')
            if product_id:
                # Sử dụng .only() để giảm tải dữ liệu khi render list
                kwargs["queryset"] = Variation.objects.filter(product_id=product_id).only('id', 'variation_value', 'variation_category')
            else:
                kwargs["queryset"] = Variation.objects.none()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ProductGalleryInline(TabularInline):
    model = ProductGallery
    form = ProductGalleryInlineForm
    extra = 0
    tab = True 
    fields = ('image', 'variation', 'alt_text', 'order')
    ordering_field = "order"  
    ordering = ["order"] 

    def get_queryset(self, request):
        """Tối ưu hóa query."""
        return super().get_queryset(request).select_related('variation')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Lọc variation theo product hiện tại."""
        if db_field.name == "variation":
            product_id = request.resolver_match.kwargs.get('object_id')
            if product_id:
                kwargs["queryset"] = Variation.objects.filter(product_id=product_id).only('id', 'variation_value', 'variation_category')
            else:
                kwargs["queryset"] = Variation.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    form = ProductVariantForm
    list_display = ('product', 'sku', 'stock', 'is_active')
    list_editable = ('stock', 'is_active')
    filter_horizontal = ('variations',)
    paginator = InfinitePaginator
    show_full_result_count = False
    list_per_page = 10

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

class CustomSliderNumericFilter(SliderNumericFilter):
    MAX_DECIMALS = 2
    STEPS = 1000

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('id', 'name', 'formated_price', 'created_at', 'category')
    list_filter = ('category__name', ('price', CustomSliderNumericFilter))
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductGalleryInline]
    actions_row = ["view_selected_product", "delete_selected_product"]
    paginator = InfinitePaginator
    show_full_result_count = False
    list_per_page = 10
    @display(description=("Price"))
    def formated_price(self, obj):
        if obj.price is not None:
            # Ép kiểu về int để bỏ phần thập phân (,00)
            # Dùng format {value:,} để thêm dấu phẩy hàng nghìn (VD: 550,000)
            # Dùng replace để đổi dấu phẩy thành dấu chấm chuẩn VN (VD: 550.000)
            return f"{int(obj.price):,}".replace(',', '.')
        return '-'

    @action(
        description=_("View selected product"),
        url_path="view-selected-product",
        icon="visibility",
    )
    def view_selected_product(self, request: HttpRequest, object_id: int):
        return redirect(reverse_lazy("admin:products_product_change", args=[object_id]))

    @action(
        description=_("Delete selected product"),
        url_path="delete-selected-product",
        icon="delete",
        attrs={"class": "!text-red-500"}
    )
    def delete_selected_product(self, request: HttpRequest, object_id: int):
        return redirect(reverse_lazy("admin:products_product_delete", args=[object_id]))

@admin.register(Variation)
class VariationAdmin(ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active', 'created_at')

    class Media:
        js = ('admin/js/variation_color_picker.js',)

@admin.register(Promotion)
class PromotionAdmin(ModelAdmin):
    list_display = ('name', 'discount_percentage', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)
    filter_horizontal = ('products',)

@admin.register(ProductGallery)
class ProductGalleryAdmin(ModelAdmin):
    form = ProductGalleryForm
    list_display = ('product', 'variation', 'order')
    list_filter = ('product',)
    list_editable = ('order',)
    sortable_by = 'order'
    ordering = ["order"]
@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ('product', 'user', 'subject', 'rating', 'status', 'created_at')
    list_filter = ('status', 'rating', 'product')
    search_fields = ('subject', 'review', 'user__username', 'product__name')
    list_editable = ('status',)
    readonly_fields = ('ip', 'created_at', 'updated_at')
