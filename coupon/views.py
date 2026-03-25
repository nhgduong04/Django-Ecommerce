from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from decimal import Decimal

from .services import validate_coupon, calculate_discount, CouponError, DEFAULT_SHIPPING_FEE, COUPON_SESSION_KEY

# COUPON_SESSION_KEY = 'applied_coupon_code'

@login_required
@require_POST
def apply_coupon(request):
    """
    AJAX endpoint: validate và lưu coupon vào session.

    POST body (form): coupon_code, cart_total
    Returns JSON: {success, message, cart_discount, shipping_fee, shipping_saved, grand_total}
    """
    code = request.POST.get('coupon_code', '').strip()
    if not code:
        return JsonResponse({'success': False, 'message': 'Vui lòng nhập mã giảm giá.'})

    from carts.services import get_cart_summary
    try:
        cart_summary = get_cart_summary(request=request, user=request.user)
        cart_total = cart_summary.total
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'Không thể lấy thông tin giỏ hàng. Vui lòng thử lại.'
        }, status=500)
    
    if cart_total <= 0:
        return JsonResponse({
            'success': False,
            'message': 'Giỏ hàng trống.'
        })

    try:
        coupon = validate_coupon(code, request.user, cart_total)
        result = calculate_discount(coupon, cart_total, DEFAULT_SHIPPING_FEE)
    except CouponError as e:
        return JsonResponse({'success': False, 'message': str(e)})

    grand_total = cart_total - result.cart_discount + result.shipping_fee

    # Lưu code vào session để dùng ở checkout và place_order
    request.session[COUPON_SESSION_KEY] = coupon.code
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'message': f'Áp dụng mã "{coupon.code}" thành công!',
        'coupon_code': coupon.code,
        'discount_type': coupon.discount_type,
        'cart_discount': int(result.cart_discount),
        'discount_amount': int(result.cart_discount),
        'shipping_saved': int(result.shipping_saved),
        'shipping_fee': int(result.shipping_fee),
        'grand_total': int(grand_total),
    })


@require_POST
def remove_coupon(request):
    """AJAX endpoint: xoá coupon khỏi session."""
    if COUPON_SESSION_KEY in request.session:
        del request.session[COUPON_SESSION_KEY]
        request.session.modified = True
    return JsonResponse({'success': True, 'message': 'Đã xóa mã giảm giá.'})
