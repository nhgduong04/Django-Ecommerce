"""
Tests for orders app.

BUG-08: Signal rollback_coupon_on_cancel dùng transaction.on_commit().
  - TransactionTestCase: on_commit chạy vì mỗi op auto-commit.
  - TestCase: on_commit KHÔNG chạy (test wrap trong transaction rollback).
  → Dùng TransactionTestCase hoặc captureOnCommitCallbacks(execute=True).
"""
from decimal import Decimal
from django.test import TestCase
from django.test.utils import captureOnCommitCallbacks
from django.contrib.auth.models import User
from django.utils import timezone

from products.models import Product, Category, ProductVariant, Variation
from coupon.models import Coupon, CouponUsage
from orders.models import Order, OrderItem


class RollbackCouponOnCancelSignalTest(TestCase):
    """
    Test signal rollback coupon khi Order CANCELLED.
    Dùng TransactionTestCase thay vì TestCase vì signal gọi transaction.on_commit().
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        self.category = Category.objects.create(name='Test Category', slug='test-cat')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='Test',
            category=self.category,
            price=Decimal('100000'),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            is_active=True,
        )
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='TEST10',
            discount_type='PERCENT',
            discount_value=Decimal('10'),
            min_order_value=Decimal('50000'),
            validate_from=now,
            validate_to=now + timezone.timedelta(days=7),
            usage_limit=5,
            used_count=1,
        )

    def test_rollback_coupon_on_cancel_decrements_used_count(self):
        """Khi order CANCELLED, coupon.used_count phải giảm 1."""
        order = Order.objects.create(
            user=self.user,
            order_number='20240322001',
            full_name='Test',
            phone='0900000000',
            email='test@example.com',
            address='Test addr',
            province='HN',
            district='HBT',
            ward='Phường 1',
            order_total=Decimal('100000'),
            shipping_fee=Decimal('30000'),
            discount_amount=Decimal('10000'),
            grand_total=Decimal('120000'),
            coupon=self.coupon,
            payment_method='COD',
            payment_status='paid',
            status='PENDING',
            is_ordered=True,
        )
        CouponUsage.objects.create(
            user=self.user,
            coupon=self.coupon,
            order=order,
        )

        self.assertEqual(self.coupon.used_count, 1)
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 1)

        # Chuyển sang CANCELLED → signal chạy on_commit → rollback
        # BUG-08: captureOnCommitCallbacks để on_commit chạy trong TestCase
        with captureOnCommitCallbacks(execute=True):
            order.status = 'CANCELLED'
            order.save()

        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 0)
        self.assertFalse(CouponUsage.objects.filter(order=order).exists())
