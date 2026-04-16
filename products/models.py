from django.db import models
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField, Max
from django.urls import reverse
from decimal import Decimal

# Create your models here.
class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_discount_percentage(self):
        active_promotions = self.promotions.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
        if active_promotions.exists():
            return active_promotions.aggregate(max_discount=Max('discount_percentage'))['max_discount']
        return 0

    def get_price(self):
        discount = self.get_discount_percentage()
        if discount > 0:
            discount_amount = self.price * (Decimal(str(discount)) / Decimal('100'))
            return self.price - discount_amount
        return self.price

    def get_original_price(self):
        return self.price

    def __str__(self):
        return self.name
    
class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    # Sử dụng get_absolute_url để tạo liên kết đến trang danh mục
    # Dễ maintain hơn khi thay đổi URL patterns (maintainability)
    def get_absolute_url(self):
        # from django.urls import reverse
        return reverse('category', args=[self.slug]) # tạo URL từ tên URL pattern 'category' và slug của category
                                                     # args -> kwargs={'slug': self.slug} dạng dict

    def __str__(self):
        return self.name
    
class VariationManager(models.Manager):
    def colors(self):
        # return super(VariationManager, self).filter(Variation_category='color', is_active=True)
        return self.filter(variation_category='color', is_active=True)

    def sizes(self):
        SIZE_ORDER = ['S', 'M', 'L', 'XL', 'XXL']
        ordering = Case(
            *[When(variation_value=size, then=Value(i)) for i, size in enumerate(SIZE_ORDER)],
            default=Value(len(SIZE_ORDER)),
            output_field=IntegerField(),
        )
        return self.filter(variation_category='size', is_active=True).annotate(size_order=ordering).order_by('size_order')
    
Variation_category_choice = (
    ('color', 'color'), # (field_value, human_readable_name)
    ('size', 'size'), # (giá trị lưu trong database, giá trị hiển thị trên form / admin)
)
    
class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations') # related_name để truy cập các variation của một product dễ dàng hơn (product.variations.all())
    variation_category = models.CharField(max_length=100, choices=Variation_category_choice) # vd: color, size
    variation_value = models.CharField(max_length=100) # vd: red, blue, S, M, L
    label = models.CharField(max_length=100, blank=True, null=True, help_text="Tên hiển thị (VD: Wash, Denim)")
    color_image = models.ImageField(upload_to='variations/colors/', blank=True, null=True, help_text="Ảnh hiển thị (Render ra UI)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = VariationManager() # gán manager tùy chỉnh cho model Variation

    class Meta:
        unique_together = ('product', 'variation_category', 'variation_value')

    def get_display_name(self):
        return self.label if self.label else self.variation_value

    def __str__(self):
        return f"{self.variation_category}: {self.get_display_name()}"

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    variations = models.ManyToManyField(Variation, related_name='product_variants', blank=True) 
    stock = models.PositiveIntegerField(default=0)
    price_variant = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_original_price(self):
        #Hàm tiện ích để lấy giá gốc ban đầu
        return self.price_variant if self.price_variant else self.product.get_original_price()

    def get_price(self):
        #Hàm tiện ích để lấy giá chuẩn xác (đã bao gồm discount nếu có)
        original_price = self.get_original_price()
        discount = self.product.get_discount_percentage()
        if discount > 0:
            discount_amount = original_price * (Decimal(str(discount)) / Decimal('100'))
            return original_price - discount_amount
        return original_price
    
    def get_image(self):
        """Trả về ảnh theo thứ tự ưu tiên:
            1. color_variation.color_image (ảnh gắn trực tiếp trên variation)
            2. ProductGallery linked với color variation
            3. product.image (fallback)
        """
        color_variation = self.variations.filter(variation_category='color').first()
        if color_variation:
            if color_variation.color_image:
                return color_variation.color_image
            gallery_img = ProductGallery.objects.filter(
                product=self.product,
                variation=color_variation
            ).first()
            if gallery_img:
                return gallery_img.image
        return self.product.image

    def __str__(self):
        return self.sku if self.sku else f"ID: {self.id}"

class Promotion(models.Model):
    name = models.CharField(max_length=255)
    discount_percentage = models.PositiveIntegerField() # vd: 10 cho 10% giảm giá
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    products = models.ManyToManyField(Product, related_name='promotions', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class ProductGallery(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    variation = models.ForeignKey(
        'Variation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gallery_images'
    )
    image = models.ImageField(upload_to='gallery/')
    alt_text = models.CharField(max_length=255, blank=True) #SEO-friendly alt text
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"Image for {self.product.name}"
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, blank=True)
    review = models.TextField(max_length=500, blank=True)
    rating = models.FloatField()
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject if self.subject else f"Review by {self.user.username}"
