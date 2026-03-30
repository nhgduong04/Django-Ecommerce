from django.contrib import admin
from django.http import JsonResponse
from django.urls import path as url_path
from .models import Category, Product, Variation, ProductVariant, Promotion, ProductGallery
from .forms import ProductVariantForm, ProductVariantInlineForm


# Register your models here.
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    form = ProductVariantInlineForm
    extra = 0

    def get_formset(self, request, obj=None, **kwargs):
        formset_class = super().get_formset(request, obj, **kwargs)
        
        class ClosureFormset(formset_class):
            def get_form_kwargs(self, index):
                kwargs = super().get_form_kwargs(index)
                kwargs['parent_product'] = obj # obj là sản phẩm hiện tại đang edit
                return kwargs
                
        return ClosureFormset

class ProductGalleryInline(admin.TabularInline):
    model = ProductGallery
    extra = 1
    fields = ('image', 'variation', 'alt_text', 'order')

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    form = ProductVariantForm
    list_display = ('product', 'sku', 'stock', 'is_active')
    list_editable = ('stock', 'is_active')
    filter_horizontal = ('variations',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'created_at', 'category')
    list_filter = ('category__name', 'price')
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductGalleryInline]

@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active', 'created_at')

    class Media:
        js = ('admin/js/variation_color_picker.js',)

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_percentage', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)
    filter_horizontal = ('products',)

@admin.register(ProductGallery)
class ProductGalleryAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation', 'order')
    list_filter = ('product',)
    list_editable = ('order',)