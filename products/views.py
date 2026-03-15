from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from .models import Product, Category, Variation

SORT_OPTIONS = {
    'latest': '-created_at',
    'popularity': None,  # handled separately via annotation
    'price_asc': 'price',
    'price_desc': '-price',
}

def _apply_sort(queryset, sort_key):
    """Apply sorting to a product queryset."""
    if sort_key == 'popularity':
        return queryset.annotate(
            total_sold=Sum('orderitem__quantity', filter=Q(orderitem__is_ordered=True))
        ).order_by('-total_sold', '-created_at')
    order_field = SORT_OPTIONS.get(sort_key, '-created_at')
    return queryset.order_by(order_field)

# Create your views here.
def home(request):
    products = Product.objects.select_related('category').order_by('-created_at')[:4]
    return render(request, 'home.html', {'products': products})

def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    sort = request.GET.get('sort', 'latest')
    products = Product.objects.filter(category=category).select_related('category')
    products = _apply_sort(products, sort)

    keyword = request.GET.get('keyword', '').strip()
    if keyword:
        products = products.filter(name__icontains=keyword)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    colors = request.GET.getlist('color')
    sizes = request.GET.getlist('size')
    if colors:
        products = products.filter(
            variants__variations__variation_category='color',
            variants__variations__variation_value__in=colors,
            variants__is_active=True,
        )
    if sizes:
        products = products.filter(
            variants__variations__variation_category='size',
            variants__variations__variation_value__in=sizes,
            variants__is_active=True,
        )

    products = products.distinct()

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('products/snippets/product_grid.html', {'products': page_obj}, request=request)
        response = JsonResponse({'html': html})
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # Distinct colors/sizes scoped to this category's products
    category_products = Product.objects.filter(category=category)
    all_colors = (
        Variation.objects.filter(
            variation_category='color', is_active=True,
            product__in=category_products
        )
        .values_list('variation_value', flat=True)
        .distinct()
        .order_by('variation_value')
    )
    all_sizes = (
        Variation.objects.sizes()
        .filter(product__in=category_products)
        .values_list('variation_value', flat=True)
        .distinct()
    )

    context = {
        'products': page_obj,
        'category': category,
        'keyword': keyword,
        'min_price': min_price or 0,
        'max_price': max_price or 2000000,
        'all_colors': list(all_colors),
        'all_sizes': list(all_sizes),
        'selected_colors': colors,
        'selected_sizes': sizes,
    }
    return render(request, 'products/product_list.html', context)

def products_list(request):
    sort = request.GET.get('sort', 'latest')
    products = Product.objects.all()
    products = _apply_sort(products, sort)
    keyword = request.GET.get('keyword', '').strip()
    if keyword:
        products = products.filter(name__icontains=keyword)
    
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Color and size filters (multiple values supported)
    colors = request.GET.getlist('color')
    sizes = request.GET.getlist('size')
    if colors:
        products = products.filter(
            variants__variations__variation_category='color',
            variants__variations__variation_value__in=colors,
            variants__is_active=True,
        )
    if sizes:
        products = products.filter(
            variants__variations__variation_category='size',
            variants__variations__variation_value__in=sizes,
            variants__is_active=True,
        )

    products = products.distinct()

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # AJAX request -> return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('products/snippets/product_grid.html', {'products': page_obj}, request=request)
        response = JsonResponse({'html': html})
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # Distinct colors and sizes from active variations
    all_colors = (
        Variation.objects.filter(variation_category='color', is_active=True)
        .values_list('variation_value', flat=True)
        .distinct()
        .order_by('variation_value')
    )
    all_sizes = Variation.objects.sizes().values_list('variation_value', flat=True).distinct()

    context = {
        'products': page_obj,
        'keyword': keyword,
        'min_price': min_price or 0,
        'max_price': max_price or 2000000,
        'all_colors': list(all_colors),
        'all_sizes': list(all_sizes),
        'selected_colors': colors,
        'selected_sizes': sizes,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)

    related_products = (
        Product.objects
        .filter(category=product.category)
        .exclude(id=product.id)
        .order_by('-created_at')[:4]
    )

    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'products/product_detail.html', context)


def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    products = (
        Product.objects
        .filter(Q(name__icontains=query))
        .select_related('category')
        .only('name', 'slug', 'price', 'image', 'category__name')
        .order_by('-created_at')[:8]
    )

    suggestions = []
    for p in products:
        suggestions.append({
            'name': p.name,
            'slug': p.slug,
            'price': str(p.price),
            'image_url': p.image.url if p.image else '',
            'category': p.category.name,
            'detail_url': f'/product/{p.slug}/',
        })

    return JsonResponse({'suggestions': suggestions})