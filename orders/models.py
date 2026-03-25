from django.db import models
from django.contrib.auth.models import User
from products.models import Product, ProductVariant


class Order(models.Model):
    STATUS = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    order_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(max_length=50)
    address = models.CharField(max_length=200)
    province = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    order_note = models.TextField(blank=True, null=True)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)  # Tổng tiền hàng
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=30000)  # Phí ship
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Số tiền giảm từ coupon
    shipping_saved = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Tổng cuối = order_total + shipping_fee - discount_amount - shipping_saved
    coupon = models.ForeignKey('coupon.Coupon', on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=100, blank=True) # 'COD', 'MoMo'
    payment_status = models.CharField(max_length=100, default='unpaid') # 'unpaid', 'paid'
    momo_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    ip = models.CharField(blank=True, max_length=45)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_products')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name}"