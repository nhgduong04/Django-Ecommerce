from django.contrib import admin
from .models import Category, Product, Variation, ProductVariant, Promotion

# Register your models here.
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
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
    inlines = [ProductVariantInline]

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