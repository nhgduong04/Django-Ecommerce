from django.db import models
from django.db.models import Case, When, Value, IntegerField
from django.urls import reverse

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
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = VariationManager() # gán manager tùy chỉnh cho model Variation

    class Meta:
        unique_together = ('product', 'variation_category', 'variation_value')

    def __str__(self):
        return f"{self.variation_category}: {self.variation_value}"

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    variations = models.ManyToManyField(Variation, related_name='product_variants') 
    stock = models.PositiveIntegerField(default=0)
    price_variant = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_price(self):
        #Hàm tiện ích để lấy giá chuẩn xác
        return self.price_variant if self.price_variant else self.product.price
    
    def __str__(self):
        return f"{self.product.name} - {', '.join([f'{v.variation_category}: {v.variation_value}' for v in self.variations.all()])}"

