from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q, Sum, Avg
from django.contrib import messages
from django.template.loader import render_to_string
from .models import Product, Category, Variation, Review
from .forms import ReviewForm

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
    best_sellers = (
        Product.objects.select_related('category')
        .annotate(total_sold=Sum('orderitem__quantity', filter=Q(orderitem__is_ordered=True)))
        .order_by('-total_sold', '-created_at')[:4]
    )
    return render(request, 'home.html', {'products': products, 'best_sellers': best_sellers})

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

    # Dùng select_related('user') để tránh N+1 khi render review.user.username trong template
    reviews = (
        Review.objects
        .filter(product=product, status=True)
        .select_related('user')
        .order_by('-created_at')
    )
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()

    user_pending_reviews = []
    if request.user.is_authenticated:
        user_pending_reviews = (
            Review.objects
            .filter(product=product, user=request.user, status=False)
            .select_related('user')
            .order_by('-created_at')
        )

    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'user_pending_reviews': user_pending_reviews,
        'average_rating': average_rating,
        'review_count': review_count,
    }
    return render(request, 'products/product_detail.html', context)

def submit_review(request, product_id):
    # Fallback URL an toàn nếu Referer bị browser/proxy xoá
    product = get_object_or_404(Product, id=product_id)
    url = request.META.get('HTTP_REFERER') or reverse('product_detail', args=[product.slug])
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # ── Auth guard ────────────────────────────────────────────────────
    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Vui lòng đăng nhập để đánh giá.'}, status=401)
        messages.error(request, 'Vui lòng đăng nhập để đánh giá.')
        return redirect(url)

    if request.method != 'POST':
        return redirect(url)

    # ── Cập nhật review cũ hoặc tạo mới ──────────────────────────────
    existing = Review.objects.filter(user=request.user, product=product).first()
    if existing:
        form = ReviewForm(request.POST, instance=existing)
        msg = "Cảm ơn bạn! Đánh giá của bạn đã được cập nhật và đang chờ duyệt."
    else:
        form = ReviewForm(request.POST)
        msg = "Cảm ơn bạn! Đánh giá của bạn đã được gửi và đang chờ duyệt."

    if form.is_valid():
        review_obj = form.save(commit=False)
        review_obj.ip     = request.META.get('REMOTE_ADDR', '')
        review_obj.product = product
        review_obj.user   = request.user
        review_obj.status = False  # Luôn chờ duyệt sau mỗi lần gửi/cập nhật
        review_obj.save()

        if is_ajax:
            return JsonResponse({'success': True, 'message': msg})
        messages.success(request, msg)
        return redirect(url)

    # Form không hợp lệ
    if is_ajax:
        return JsonResponse({'success': False, 'errors': form.errors.as_json()}, status=400)
    messages.error(request, 'Dữ liệu không hợp lệ. Vui lòng kiểm tra lại.')
    return redirect(url)


def product_quick_view(request, slug):
    """
    Return a small HTML fragment for the quick add-to-cart modal.

    Loaded via AJAX from the product list page to keep initial page load fast.
    """
    product = get_object_or_404(
        Product.objects.prefetch_related("variants__variations"),
        slug=slug,
    )

    html = render_to_string(
        "products/snippets/quick_view.html",
        {"product": product},
        request=request,
    )
    return JsonResponse({"html": html})


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