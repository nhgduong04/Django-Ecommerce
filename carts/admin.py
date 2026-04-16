from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Cart, CartItem

# Register your models here.
@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ('cart_id', 'user', 'date_added')

@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    list_display = ('user', 'variant', 'cart', 'quantity', 'is_active')
    