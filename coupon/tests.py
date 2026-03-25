from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Coupon
from .services import DEFAULT_SHIPPING_FEE, calculate_discount


class CalculateDiscountTests(TestCase):
    def _coupon(self, *, code: str, discount_type: str, discount_value: str = "0", max_discount_amount=None):
        now = timezone.now()
        return Coupon.objects.create(
            code=code,
            discount_type=discount_type,
            discount_value=Decimal(discount_value),
            min_order_value=Decimal("0"),
            max_discount_amount=Decimal(max_discount_amount) if max_discount_amount is not None else None,
            validate_from=now - timezone.timedelta(days=1),
            validate_to=now + timezone.timedelta(days=1),
            is_active=True,
        )

    def test_percent_coupon_returns_discount_result(self):
        coupon = self._coupon(
            code="P10",
            discount_type="PERCENT",
            discount_value="10",
            max_discount_amount="20000",
        )
        result = calculate_discount(coupon, Decimal("300000"))
        self.assertEqual(result.cart_discount, Decimal("20000"))
        self.assertEqual(result.shipping_fee, DEFAULT_SHIPPING_FEE)
        self.assertEqual(result.shipping_saved, Decimal("0"))

    def test_fixed_coupon_returns_discount_result(self):
        coupon = self._coupon(code="FIX50", discount_type="FIXED", discount_value="50000")
        result = calculate_discount(coupon, Decimal("30000"))
        self.assertEqual(result.cart_discount, Decimal("30000"))
        self.assertEqual(result.shipping_fee, DEFAULT_SHIPPING_FEE)
        self.assertEqual(result.shipping_saved, Decimal("0"))

    def test_t15_freeship_cart_100k_ship_30k(self):
        coupon = self._coupon(code="FS1", discount_type="FREESHIP")
        cart_total = Decimal("100000")
        result = calculate_discount(coupon, cart_total, DEFAULT_SHIPPING_FEE)
        grand_total = cart_total - result.cart_discount + result.shipping_fee

        self.assertEqual(result.cart_discount, Decimal("0"))
        self.assertEqual(result.shipping_fee, Decimal("0"))
        self.assertEqual(result.shipping_saved, Decimal("30000"))
        self.assertEqual(grand_total, Decimal("100000"))

    def test_t16_freeship_cart_20k_ship_30k(self):
        coupon = self._coupon(code="FS2", discount_type="FREESHIP")
        cart_total = Decimal("20000")
        result = calculate_discount(coupon, cart_total, DEFAULT_SHIPPING_FEE)
        grand_total = cart_total - result.cart_discount + result.shipping_fee

        self.assertEqual(result.cart_discount, Decimal("0"))
        self.assertEqual(result.shipping_fee, Decimal("0"))
        self.assertEqual(result.shipping_saved, Decimal("30000"))
        self.assertEqual(grand_total, Decimal("20000"))

    def test_t17_freeship_cart_0_edge(self):
        coupon = self._coupon(code="FS3", discount_type="FREESHIP")
        cart_total = Decimal("0")
        result = calculate_discount(coupon, cart_total, DEFAULT_SHIPPING_FEE)
        grand_total = cart_total - result.cart_discount + result.shipping_fee

        self.assertEqual(result.cart_discount, Decimal("0"))
        self.assertEqual(result.shipping_fee, Decimal("0"))
        self.assertEqual(result.shipping_saved, Decimal("30000"))
        self.assertEqual(grand_total, Decimal("0"))
