from django.db import models
from django.contrib.auth.models import User

from products.models import Product, Variation, ProductVariant

# Create your models here.
class Cart(models.Model):
    cart_id = models.CharField(max_length=250, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cart_id or str(self.user)
    
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)
    variant = models.ForeignKey(ProductVariant, blank=True, on_delete=models.CASCADE, null=True)

    @property
    def product(self):
        return self.variant.product if self.variant else None

    @property
    def variations(self):
        return self.variant.variations if self.variant else Variation.objects.none()

    def sub_total(self): # tính thành tiền của một sản phẩm trong giỏ hàng
        if not self.variant:
            return 0
        return self.variant.get_price() * self.quantity

    def __str__(self):
        if not self.variant_id:
            return "(no variant)"
        return f"{self.variant.product.name} (variant #{self.variant_id})"