from __future__ import annotations

from dataclasses import dataclass
from typing import List

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from products.models import ProductVariant, Product

from .models import CartItem
from .services import (
    InvalidCartRequest,
    OutOfStockError,
    add_variant_to_session_cart,
    add_variant_to_user_cart,
    get_session_cart,
    parse_selected_variations,
    resolve_variant_from_request,
    session_cart_total_quantity,
    set_session_cart,
    get_cart_summary
)

# Create your views here.
def _wants_json(request) -> bool:
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("accept") or "")
    )


@require_POST
def add_to_cart(request, product_id: int):
    """Add a product variant to cart.

    - Guest: stored in session (variant_id -> quantity)
    - Authenticated: stored in DB as CartItem(user, variant, quantity)

    Returns JSON for AJAX callers; otherwise redirects to cart.
    """
    quantity = request.POST.get("quantity")
    variant_id = request.POST.get("variant_id")

    product = None
    selected_variations: List = []
    if not variant_id:
        product = Product.objects.get(pk=product_id)
        selected_variations = parse_selected_variations(request=request, product=product)

    try:
        variant = resolve_variant_from_request(
            product=product,
            variant_id=variant_id,
            selected_variations=selected_variations,
        )
    except (InvalidCartRequest, ProductVariant.DoesNotExist, Product.DoesNotExist) as exc:
        if _wants_json(request):
            return JsonResponse({"success": False, "error": str(exc)}, status=400)
        return redirect("cart")

    try:
        if request.user.is_authenticated:
            cart_item, cart_quantity = add_variant_to_user_cart(
                user=request.user,
                variant_id=int(variant.pk),
                quantity=quantity,
            )
            item_quantity = int(cart_item.quantity)
        else:
            item_quantity, cart_quantity = add_variant_to_session_cart(
                request=request,
                variant=variant,
                quantity=quantity,
            )
    except OutOfStockError as exc:
        if _wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "error": "out_of_stock",
                    "message": "Not enough stock for this variant.",
                    "variant_id": variant.pk,
                    "available": exc.available,
                    "requested": exc.requested,
                },
                status=409,
            )
        return redirect("cart")

    if _wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "variant_id": int(variant.pk),
                "item_quantity": int(item_quantity),
                "cart_quantity": int(cart_quantity),
                "stock": int(variant.stock),
            }
        )
    return redirect("cart")


# @dataclass(frozen=True)
# class SessionCartItem:
#     id: int
#     variant: ProductVariant
#     quantity: int

#     @property
#     def product(self):
#         return self.variant.product

#     @property
#     def variations(self):
#         return self.variant.variations

#     def sub_total(self):
#         return self.variant.get_price() * self.quantity


def cart(request):
    from coupon.services import validate_coupon, calculate_discount, CouponError, DEFAULT_SHIPPING_FEE, COUPON_SESSION_KEY
    from decimal import Decimal

    cart = get_cart_summary(request=request, user=request.user)

    shipping_fee = DEFAULT_SHIPPING_FEE
    shipping_saved = Decimal('0')
    discount_amount = Decimal('0')
    applied_coupon = None

    coupon_code = request.session.get(COUPON_SESSION_KEY, '')
    if coupon_code and cart.total > 0:
        try:
            coupon = validate_coupon(coupon_code, request.user, cart.total)
            result = calculate_discount(coupon, cart.total, DEFAULT_SHIPPING_FEE)
            discount_amount = result.cart_discount
            shipping_fee = result.shipping_fee
            shipping_saved = result.shipping_saved
            applied_coupon = coupon
        except CouponError:
            del request.session[COUPON_SESSION_KEY]
            request.session.modified = True

    coupon_savings = discount_amount + shipping_saved
    grand_total = cart.total - discount_amount + shipping_fee if cart.total > 0 else Decimal('0')

    return render(
        request,
        "cart/cart.html",
        {
            "cart_items": cart.items,
            "total": cart.total,
            "quantity": cart.quantity,
            "shipping_fee": shipping_fee,
            "shipping_saved": shipping_saved,
            "discount_amount": discount_amount,
            "coupon_savings": coupon_savings,
            "grand_total": grand_total,
            "applied_coupon": applied_coupon,
        },
    )

def update_cart(request):
    if request.method == 'POST':
        import json

        data = json.loads(request.body) 
        # vd request body: data = {"cart_item_id": 1, "action": "add"} hoặc {"cart_item_id": 1, "action": "remove"}
        # json.loads() sẽ chuyển chuỗi JSON thành một đối tượng Python (ở đây là dict) để chúng ta có thể truy cập các giá trị như data['cart_item_id'] và data['action'].
        cart_item_id = data.get('cart_item_id')
        action = data.get('action')
        
        try:
            if request.user.is_authenticated:
                item_deleted = False
                with transaction.atomic():
                    cart_item = (
                        CartItem.objects.select_for_update()
                        .select_related("variant__product")
                        .get(id=cart_item_id, user=request.user)
                    )
                    variant = (
                        ProductVariant.objects.select_for_update()
                        .get(pk=cart_item.variant_id, is_active=True)
                    )

                    if action == "add":
                        if cart_item.quantity + 1 > variant.stock:
                            raise OutOfStockError(
                                available=int(variant.stock),
                                requested=int(cart_item.quantity) + 1,
                            )
                        cart_item.quantity += 1
                        cart_item.save(update_fields=["quantity"])
                    elif action == "remove":
                        if cart_item.quantity > 1:
                            cart_item.quantity -= 1
                            cart_item.save(update_fields=["quantity"])
                        else:
                            cart_item.delete()
                            item_deleted = True
                    elif action == "delete":
                        cart_item.delete()
                        item_deleted = True

                cart_items = (
                    CartItem.objects.filter(user=request.user, is_active=True)
                    .select_related("variant__product")
                )
                total = sum(item.sub_total() for item in cart_items)
                quantity = cart_items.count()

                if item_deleted:
                    item_sub_total = 0
                    item_quantity = 0
                else:
                    item_sub_total = cart_item.sub_total()
                    item_quantity = int(cart_item.quantity)

            else:
                # Guest cart: treat cart_item_id as variant_id
                session_cart = get_session_cart(request)
                key = str(cart_item_id)

                if action == "add":
                    variant = ProductVariant.objects.get(pk=cart_item_id, is_active=True)
                    current = int(session_cart.get(key, 0))
                    if current + 1 > variant.stock:
                        raise OutOfStockError(available=int(variant.stock), requested=current + 1)
                    session_cart[key] = current + 1
                elif action == "remove":
                    current = int(session_cart.get(key, 0))
                    if current > 1:
                        session_cart[key] = current - 1
                    else:
                        session_cart.pop(key, None)
                elif action == "delete":
                    session_cart.pop(key, None)

                set_session_cart(request, session_cart)

                variant_ids = [int(k) for k in session_cart.keys() if str(k).isdigit()]
                variants = ProductVariant.objects.filter(pk__in=variant_ids, is_active=True).select_related(
                    "product"
                )
                variants_by_id = {v.pk: v for v in variants}

                total = 0
                quantity = session_cart_total_quantity(session_cart)
                for vid, qty in session_cart.items():
                    try:
                        vid_int = int(vid)
                        qty_int = int(qty)
                    except (TypeError, ValueError):
                        continue
                    v = variants_by_id.get(vid_int)
                    if not v:
                        continue
                    total += v.get_price() * qty_int

                item_quantity = int(session_cart.get(key, 0))
                v = variants_by_id.get(int(key))
                item_sub_total = (v.get_price() * item_quantity) if (v and item_quantity > 0) else 0

            # Tính coupon nếu có
            from coupon.services import validate_coupon, calculate_discount, CouponError, DEFAULT_SHIPPING_FEE, COUPON_SESSION_KEY
            from decimal import Decimal

            shipping_fee = DEFAULT_SHIPPING_FEE
            shipping_saved = Decimal('0')
            discount_amount = Decimal('0')
            coupon_code = request.session.get(COUPON_SESSION_KEY, '')

            if coupon_code and total > 0:
                try:
                    c = validate_coupon(coupon_code, request.user, total)
                    result = calculate_discount(c, total, DEFAULT_SHIPPING_FEE)
                    discount_amount = result.cart_discount
                    shipping_fee = result.shipping_fee
                    shipping_saved = result.shipping_saved
                except CouponError:
                    del request.session[COUPON_SESSION_KEY]
                    request.session.modified = True

            coupon_savings = discount_amount + shipping_saved
            grand_total = (total - discount_amount + shipping_fee) if total > 0 else 0

            return JsonResponse(
                {
                    "success": True,
                    "quantity": item_quantity,
                    "sub_total": float(item_sub_total),
                    "total": float(total),
                    "cart_quantity": int(quantity),
                    "shipping_fee": float(shipping_fee),
                    "shipping_saved": float(shipping_saved),
                    "discount_amount": float(discount_amount),
                    "coupon_savings": float(coupon_savings),
                    "grand_total": float(grand_total),
                }
            )
        except OutOfStockError as exc:
            return JsonResponse(
                {
                    "success": False,
                    "error": "out_of_stock",
                    "available": exc.available,
                    "requested": exc.requested,
                },
                status=409,
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required(login_url='login')
def checkout(request):
    '''Fetch cart items and calculate total'''
    from coupon.services import validate_coupon, calculate_discount, CouponError, DEFAULT_SHIPPING_FEE, COUPON_SESSION_KEY
    from coupon.models import Coupon
    from decimal import Decimal

    cart = get_cart_summary(request=request, user=request.user)
    if not cart.items:
        return redirect('cart')

    shipping_fee = DEFAULT_SHIPPING_FEE
    shipping_saved = Decimal('0')
    discount_amount = Decimal('0')
    applied_coupon = None

    coupon_code = request.session.get(COUPON_SESSION_KEY, '')
    if coupon_code:
        try:
            coupon = validate_coupon(coupon_code, request.user, cart.total)
            result = calculate_discount(coupon, cart.total, DEFAULT_SHIPPING_FEE)
            discount_amount = result.cart_discount
            shipping_fee = result.shipping_fee
            shipping_saved = result.shipping_saved
            applied_coupon = coupon
        except CouponError:
            # Coupon không còn hợp lệ → xoá khỏi session
            del request.session[COUPON_SESSION_KEY]
            request.session.modified = True

    coupon_savings = discount_amount + shipping_saved
    grand_total = cart.total - discount_amount + shipping_fee

    context = {
        'cart_items': cart.items,
        'total': cart.total,
        'quantity': cart.quantity,
        'shipping_fee': shipping_fee,
        'shipping_saved': shipping_saved,
        'discount_amount': discount_amount,
        'coupon_savings': coupon_savings,
        'grand_total': grand_total,
        'applied_coupon': applied_coupon,
        'coupon_code': applied_coupon.code if applied_coupon else '',
    }
    return render(request, 'cart/checkout.html', context)