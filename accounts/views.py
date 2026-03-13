from django.db.models import Prefetch
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegistrationForm, LoginForm

from orders.models import Order, OrderItem

# Create your views here.
def register(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                form.add_error(None, 'Tài khoản đã bị vô hiệu hóa.')
            else:
                auth_login(request, user)
            
            # Check if there's a next path
            next_url = request.POST.get('next') or request.GET.get('next') # request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('/') 
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})

@login_required(login_url='login') # Đảm bảo chỉ người dùng đã đăng nhập mới có thể truy cập view này
def logout(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home') # Adjust 'home' to your actual url name

@login_required(login_url='login')
def profile(request):
    return render(request, 'accounts/profile.html')

@login_required(login_url='login')
def orders(request):
    # Map tab query param to Order.STATUS values
    TAB_STATUS_MAP = {
        'pending': 'PENDING',
        'processing': 'PROCESSING',
        'completed': 'COMPLETED',
    }

    active_tab = request.GET.get('status', 'pending').lower()
    if active_tab not in TAB_STATUS_MAP:
        active_tab = 'pending'

    order_status = TAB_STATUS_MAP[active_tab]

    # Prefetch order items with product + variant + variations for efficiency
    order_items_prefetch = Prefetch(
        'order_products',
        queryset=OrderItem.objects.select_related(
            'product', 'variant'
        ).prefetch_related('variant__variations'),
    )

    orders = (
        Order.objects
        .filter(user=request.user, is_ordered=True, status=order_status)
        .prefetch_related(order_items_prefetch)
        .order_by('-created_at')
    )

    context = {
        'orders': orders,
        'active_tab': active_tab,
    }
    return render(request, 'accounts/orders.html', context)

@login_required(login_url='login')
def change_password(request):
    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def addresses(request):
    return render(request, 'accounts/addresses.html')