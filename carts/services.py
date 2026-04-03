from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Sum

from products.models import Product, ProductVariant, Variation
from .dtos import CartSummaryDTO, SessionCartItemDTO

from .models import CartItem


SESSION_CART_KEY = "cart"  # maps str(variant_id) -> int(quantity)


class CartError(Exception):
    """Base cart error."""


class OutOfStockError(CartError):
    """Raised when requested quantity exceeds available stock."""

    def __init__(self, *, available: int, requested: int):
        super().__init__(f"Out of stock. Available={available}, requested={requested}")
        self.available = available
        self.requested = requested


class InvalidCartRequest(CartError):
    """Raised when request payload cannot be resolved to a variant."""


def _coerce_positive_int(value, default: int = 1) -> int:
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return default
    return value_int if value_int > 0 else default


def get_session_cart(request) -> Dict[str, int]:
    cart = request.session.get(SESSION_CART_KEY)
    if not isinstance(cart, dict):
        cart = {}
        request.session[SESSION_CART_KEY] = cart
    # Normalize values to ints
    normalized: Dict[str, int] = {}
    for key, quantity in cart.items():
        try:
            normalized[str(key)] = int(quantity)
        except (TypeError, ValueError):
            continue
    request.session[SESSION_CART_KEY] = normalized
    return normalized


def clear_session_cart(request) -> None:
    if SESSION_CART_KEY in request.session:
        del request.session[SESSION_CART_KEY]
        request.session.modified = True


def set_session_cart(request, cart: Dict[str, int]) -> None:
    request.session[SESSION_CART_KEY] = {str(k): int(v) for k, v in cart.items() if int(v) > 0}
    request.session.modified = True


def session_cart_total_quantity(cart: Dict[str, int]) -> int:
    return sum(1 for q in cart.values() if int(q) > 0)


def resolve_variant_from_request(
    *,
    product: Product | None,
    variant_id: str | int | None,
    selected_variations: Iterable[Variation],
) -> ProductVariant:
    if variant_id:
        qs = ProductVariant.objects.select_related("product").prefetch_related("variations").filter(
            pk=variant_id, is_active=True
        )
        if product:
            qs = qs.filter(product=product)
        return qs.get()

    if not product:
        raise InvalidCartRequest("Missing product context")

    variation_list = list(selected_variations)

    qs = ProductVariant.objects.filter(product=product, is_active=True)
    for variation in variation_list:
        qs = qs.filter(variations=variation)

    if variation_list:
        qs = qs.annotate(num_vars=Count("variations")).filter(num_vars=len(variation_list))

    qs = qs.select_related("product").prefetch_related("variations")

    variant = qs.first()
    if not variant:
        raise InvalidCartRequest("No matching variant for selected variations")
    return variant


def parse_selected_variations(*, request, product: Product) -> List[Variation]:
    selected: List[Variation] = []
    for key in request.POST:
        if key in {"csrfmiddlewaretoken", "quantity", "variant_id"}:
            continue
        value = request.POST.get(key)
        if value in (None, ""):
            continue
        try:
            selected.append(
                Variation.objects.get(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value,
                )
            )
        except Variation.DoesNotExist:
            continue
    return selected


def add_variant_to_session_cart(*, request, variant: ProductVariant, quantity: int) -> Tuple[int, int]:
    quantity = _coerce_positive_int(quantity, default=1)
    cart = get_session_cart(request)

    key = str(variant.pk)
    current_qty = int(cart.get(key, 0))
    requested_total = current_qty + quantity

    if requested_total > variant.stock:
        raise OutOfStockError(available=int(variant.stock), requested=requested_total)

    cart[key] = requested_total
    set_session_cart(request, cart)
    return requested_total, session_cart_total_quantity(cart)


@transaction.atomic
def add_variant_to_user_cart(*, user: User, variant_id: int, quantity: int) -> Tuple[CartItem, int]:
    quantity = _coerce_positive_int(quantity, default=1)

    # Lock the variant row for consistent stock validation under concurrency.
    variant = (
        ProductVariant.objects.select_for_update()
        .select_related("product")
        .get(pk=variant_id, is_active=True)
    )

    cart_item, _created = CartItem.objects.select_for_update().get_or_create(
        user=user,
        variant=variant,
        defaults={"quantity": 0, "is_active": True},
    )

    requested_total = int(cart_item.quantity) + quantity
    if requested_total > variant.stock:
        raise OutOfStockError(available=int(variant.stock), requested=requested_total)

    cart_item.quantity = requested_total
    cart_item.is_active = True
    cart_item.save(update_fields=["quantity", "is_active"]) 

    cart_count = CartItem.objects.filter(user=user, is_active=True).count()

    return cart_item, cart_count


@transaction.atomic
def merge_session_cart_into_user_cart(*, request, user: User) -> Dict[str, int]:
    """Merge session cart (variant_id -> qty) into DB cart.

    Returns summary stats for logging/diagnostics.
    """

    cart = get_session_cart(request)
    if not cart:
        return {"merged_items": 0, "skipped_items": 0}

    variant_ids: List[int] = []
    for key in cart.keys():
        try:
            variant_ids.append(int(key))
        except (TypeError, ValueError):
            continue

    if not variant_ids:
        clear_session_cart(request)
        return {"merged_items": 0, "skipped_items": 0}

    variants = list(
        ProductVariant.objects.select_for_update()
        .filter(pk__in=variant_ids, is_active=True)
        .select_related("product")
    )
    variant_by_id = {v.pk: v for v in variants}

    # De-duplicate any existing DB cart rows per variant (legacy data).
    existing_items = list(
        CartItem.objects.select_for_update()
        .filter(user=user, variant_id__in=variant_ids)
        .order_by("variant_id", "id")
    )
    existing_by_variant: Dict[int, List[CartItem]] = {}
    for item in existing_items:
        existing_by_variant.setdefault(int(item.variant_id), []).append(item)
        # exising_by_variant[item.variant_id] = item 
        # sẽ bị ghi đè nếu có nhiều CartItem cùng variant_id, nên cần dùng list để gom lại
    merged_items = 0
    skipped_items = 0

    for variant_id in variant_ids:
        variant = variant_by_id.get(variant_id) # lấy ra obj
        if not variant:
            skipped_items += 1
            continue

        desired_qty = _coerce_positive_int(cart.get(str(variant_id)), default=0)
        if desired_qty <= 0:
            continue

        existing_list = existing_by_variant.get(variant_id, [])
        if existing_list:
            keeper = existing_list[0]
            existing_qty = sum(int(i.quantity) for i in existing_list)
            if len(existing_list) > 1:
                CartItem.objects.filter(id__in=[i.id for i in existing_list[1:]]).delete()
        else:
            keeper = CartItem(user=user, variant=variant, quantity=0, is_active=True)
            existing_qty = 0

        new_qty = existing_qty + desired_qty
        if new_qty > variant.stock:
            new_qty = int(variant.stock)

        if new_qty <= 0:
            skipped_items += 1
            continue

        keeper.quantity = new_qty
        keeper.is_active = True
        keeper.save()
        merged_items += 1

    clear_session_cart(request)
    return {"merged_items": merged_items, "skipped_items": skipped_items}

def get_cart_summary(user=None, request=None) -> CartSummaryDTO:
    if user and user.is_authenticated:
        cart_items = list(
            CartItem.objects.filter(user=user, is_active=True)
            .select_related("variant__product")
            .prefetch_related("variant__variations")
        )
    else:
        session_cart = get_session_cart(request)
        variant_ids = [int(k) for k in session_cart.keys() if str(k).isdigit()]
        variants = (
            ProductVariant.objects.filter(pk__in=variant_ids, is_active=True)
            .select_related("product")
            .prefetch_related("variations")
        )
        variants_by_id = {v.pk: v for v in variants}
        # items = [
        #     SessionCartItemDTO(id=int(k), variant=variants_by_id[int(k)], quantity=int(q))
        #     for k, q in session_cart.items()
        #     if str(k).isdigit() and int(k) in variants_by_id and int(q) > 0
        # ]
        items: list[SessionCartItemDTO] = []
        for key, qty in session_cart.items():
            try:
                variant_id = int(key) 
                qty_int = int(qty)
            except (TypeError, ValueError):
                continue
            variant = variants_by_id.get(variant_id)
            if not variant or qty_int <= 0:
                continue
            items.append(SessionCartItemDTO(id=variant_id, variant=variant, quantity=qty_int))
        cart_items = items

    total = sum(cart_item.sub_total() for cart_item in cart_items)
    quantity = len(cart_items)
    return CartSummaryDTO(items=cart_items, total=total, quantity=quantity)