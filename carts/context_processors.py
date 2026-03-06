from .models import CartItem
from .services import get_session_cart, session_cart_total_quantity

def counter(request):
    cart_count = 0
    # request.path: lấy đường dẫn URL hiện tại của request, ví dụ: "/admin/" hoặc "/cart/"
    if 'admin' in request.path: # Nếu đang ở trang admin thì không cần tính cart_count
        return {}
    else:
        if request.user.is_authenticated:
            for qty in CartItem.objects.filter(user=request.user, is_active=True).values_list(
                "quantity", flat=True
            ):
                cart_count += int(qty)
        else:
            cart = get_session_cart(request)
            cart_count = session_cart_total_quantity(cart)
    return dict(cart_count=cart_count)
