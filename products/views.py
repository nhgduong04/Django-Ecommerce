from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .models import Product, Category

# Create your views here.
def home(request):
    products = Product.objects.select_related('category').order_by('-created_at')[:4]
    return render(request, 'home.html', {'products': products})

def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = (
        Product.objects.filter(category=category)
        .select_related('category')
        .order_by('-created_at')
    )
    return render(request, 'products/product_list.html', {'products': products, 'category': category})

def products_list(request):
    products = Product.objects.all().order_by('-created_at')
    keyword = request.GET.get('keyword')
    if keyword:
        products = products.filter(name__icontains=keyword)
    
    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number) # get_page() will return the page object

    context = {
        'products': products,
        'keyword': keyword,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'products/product_detail.html', {'product': product})