import datetime
import json
import uuid
import hmac
import hashlib
import logging

import requests
from django.db.models import F
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Order, OrderItem
from .forms import OrderForm
from carts.models import CartItem
from carts.services import get_cart_summary

logger = logging.getLogger(__name__)


# ─── Helper Functions (private) ─────────────────────────────


def _generate_order_number(order_id):
    """Tạo mã đơn hàng dựa trên ngày hiện tại + order ID."""
    today = datetime.date.today()
    return today.strftime("%Y%m%d") + str(order_id)


def _create_momo_signature(raw_data, secret_key):
    """Tạo chữ ký HMAC-SHA256 cho request gửi đến MoMo."""
    h = hmac.new(
        key=secret_key.encode('ascii'),
        msg=raw_data.encode('ascii'),
        digestmod=hashlib.sha256,
    )
    return h.hexdigest()


def _verify_momo_signature(data, secret_key, received_signature):
    """
    Xác thực chữ ký HMAC-SHA256 từ MoMo IPN.
    Trả về True nếu signature hợp lệ, False nếu không.
    """
    # Xây dựng rawSignature theo đúng thứ tự alphabet mà MoMo yêu cầu
    raw_data = (
        f"accessKey={settings.MOMO_ACCESS_KEY}"
        # f"&amount={data['amount']}"
        # f"&extraData={data['extraData']}"
        # f"&message={data['message']}"
        # f"&orderId={data['orderId']}"
        # f"&orderInfo={data['orderInfo']}"
        # f"&orderType={data['orderType']}"
        # f"&partnerCode={data['partnerCode']}"
        # f"&payType={data['payType']}"
        # f"&requestId={data['requestId']}"
        # f"&responseTime={data['responseTime']}"
        # f"&resultCode={data['resultCode']}"
        # f"&transId={data['transId']}"

        f"&amount={str(data.get('amount', ''))}"          # ← FIX BUG 2 + 3
        f"&extraData={data.get('extraData', '')}"
        f"&message={data.get('message', '')}"
        f"&orderId={data.get('orderId', '')}"
        f"&orderInfo={data.get('orderInfo', '')}"
        f"&orderType={data.get('orderType', '')}"
        f"&partnerCode={data.get('partnerCode', '')}"
        f"&payType={data.get('payType', '')}"
        f"&requestId={data.get('requestId', '')}"
        f"&responseTime={str(data.get('responseTime', ''))}"
        f"&resultCode={str(data.get('resultCode', ''))}"
        f"&transId={str(data.get('transId', ''))}"
    )
    expected_signature = _create_momo_signature(raw_data, secret_key)
    return hmac.compare_digest(expected_signature, received_signature)


def _build_momo_payment_request(order):
    """
    Build payload và gọi MoMo API để tạo link thanh toán.
    Trả về response JSON từ MoMo.
    """
    order_id = str(order.order_number)
    request_id = str(uuid.uuid4())
    amount = str(int(order.order_total))
    order_info = f"Thanh toan don hang #{order.order_number}"
    extra_data = ""  # Có thể encode base64 nếu cần truyền thêm data

    # Xây dựng rawSignature theo thứ tự alphabet
    raw_signature = (
        f"accessKey={settings.MOMO_ACCESS_KEY}"
        f"&amount={amount}"
        f"&extraData={extra_data}"
        f"&ipnUrl={settings.MOMO_IPN_URL}"
        f"&orderId={order_id}"
        f"&orderInfo={order_info}"
        f"&partnerCode={settings.MOMO_PARTNER_CODE}"
        f"&redirectUrl={settings.MOMO_REDIRECT_URL}"
        f"&requestId={request_id}"
        f"&requestType=payWithMethod"
    )

    signature = _create_momo_signature(raw_signature, settings.MOMO_SECRET_KEY)

    # Payload gửi đến MoMo
    payload = {
        'partnerCode': settings.MOMO_PARTNER_CODE,
        'orderId': order_id,
        'partnerName': 'MoMo Payment',
        'storeId': 'MyShop',
        'ipnUrl': settings.MOMO_IPN_URL,
        'redirectUrl': settings.MOMO_REDIRECT_URL,
        'amount': amount,
        'lang': 'vi',
        'requestType': 'payWithMethod',
        'autoCapture': True,
        'orderInfo': order_info,
        'requestId': request_id,
        'extraData': extra_data,
        'signature': signature,
        'orderGroupId': '',
    }

    response = requests.post(
        settings.MOMO_API_ENDPOINT,
        json=payload,
        timeout=30,
    )

    return response.json()


def _create_order_with_items(form, user, cart_summary, payment_method):
    """
    Tạo Order + OrderItems bên trong transaction.atomic().
    Trả về order vừa tạo.
    """
    with transaction.atomic():
        # 1. Tạo Order
        order = form.save(commit=False)
        order.user = user
        order.order_total = cart_summary.total
        order.payment_method = payment_method
        order.payment_status = 'unpaid'
        order.status = 'PENDING'
        order.is_ordered = True
        order.save()

        # 2. Sinh mã đơn hàng
        order.order_number = _generate_order_number(order.id)
        order.save(update_fields=['order_number'])

        # 3. Tạo OrderItems (snapshot giá tại thời điểm đặt hàng)
        cart_items = CartItem.objects.filter(
            user=user, is_active=True
        ).select_related('variant__product')
        

        for item in cart_items:
            # # Lock variant row để tránh race condition khi nhiều người mua cùng lúc
            # variant = item.variant.__class__.objects.select_for_update().get(pk=item.variant.pk)
            # # Kiểm tra tồn kho
            # if variant.stock < item.quantity:
            #     raise ValueError(
            #         f"Sản phẩm '{variant}' chỉ còn {variant.stock} trong kho, "
            #         f"không đủ cho {item.quantity} sản phẩm yêu cầu."
            #     )
            # # Trừ stock bằng F() expression (atomic ở DB level)
            # variant.stock = F('stock') - item.quantity
            # variant.save(update_fields=['stock'])
            OrderItem.objects.create(
                order=order,
                user=user,
                product=item.variant.product,
                variant=item.variant,
                quantity=item.quantity,
                product_price=item.variant.get_price(),
                is_ordered=True,
            )

    return order


# ─── Views ───────────────────────────────────────────────────


@login_required
@require_POST
def place_order_view(request):
    """
    Xử lý POST đặt hàng. Phân nhánh theo payment method:
      - 'cod': tạo order → xóa cart → redirect trang thành công
      - 'momo': tạo order → gọi MoMo API → redirect đến payUrl
    """
    # Kiểm tra giỏ hàng có sản phẩm không
    cart_summary = get_cart_summary(request=request, user=request.user)
    if not cart_summary.items:
        return redirect('cart')

    # Validate form thông tin giao hàng
    form = OrderForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Vui lòng điền đầy đủ thông tin để đặt hàng.')
        return redirect('checkout')

    payment_method = request.POST.get('payment', '')

    # ── COD (Thanh toán khi nhận hàng) ──
    if payment_method == 'cod':
        try:
            order = _create_order_with_items(
                form, request.user, cart_summary, payment_method='COD'
            )
            # Xóa cart ngay vì COD không cần xác nhận thanh toán
            CartItem.objects.filter(user=request.user, is_active=True).delete()
            return redirect('order_successful')
        
        except ValueError as e:
            # Hết hàng hoặc không đủ tồn kho
            logger.warning("Hết hàng khi đặt COD: %s", e)
            messages.error(request, str(e))
            return redirect('cart')

        except Exception:
            logger.exception("Lỗi khi tạo đơn hàng COD")
            messages.error(request, 'Đã xảy ra lỗi khi đặt hàng. Vui lòng thử lại.')
            return redirect('cart')

    # ── MoMo ──
    elif payment_method == 'momo':
        try:
            order = _create_order_with_items(
                form, request.user, cart_summary, payment_method='MOMO'
            )

        except ValueError as e:
            # Hết hàng hoặc không đủ tồn kho
            logger.warning("Hết hàng khi đặt MoMo: %s", e)
            messages.error(request, str(e))
            return redirect('cart')

        except Exception:
            logger.exception("Lỗi khi tạo đơn hàng MoMo")
            messages.error(request, 'Đã xảy ra lỗi khi đặt hàng. Vui lòng thử lại.')
            return redirect('cart')

        # Gọi MoMo API để lấy link thanh toán
        try:
            momo_response = _build_momo_payment_request(order)
            pay_url = momo_response.get('payUrl')

            if pay_url:
                return redirect(pay_url)
            else:
                # MoMo trả về lỗi (resultCode != 0)
                error_msg = momo_response.get('message', 'Lỗi không xác định từ MoMo')
                logger.error("MoMo API error: %s", momo_response)
                messages.error(request, f'Lỗi thanh toán MoMo: {error_msg}')
                # Hủy order vừa tạo vì không thể thanh toán
                order.status = 'CANCELLED'
                order.save(update_fields=['status'])
                return redirect('checkout')

        except requests.RequestException:
            logger.exception("Không thể kết nối đến MoMo API")
            messages.error(request, 'Không thể kết nối đến cổng thanh toán. Vui lòng thử lại.')
            order.status = 'CANCELLED'
            order.save(update_fields=['status'])
            return redirect('checkout')

    # ── Phương thức không hợp lệ ──
    else:
        messages.error(request, 'Phương thức thanh toán không hợp lệ.')
        return redirect('checkout')


def order_success_view(request):
    """Hiển thị trang đặt hàng thành công."""
    return render(request, 'orders/order_successful.html')


@csrf_exempt
@require_POST
def momo_ipn_view(request):
    """
    Nhận webhook IPN (server-to-server) từ MoMo.
    Đây là nơi DUY NHẤT đánh dấu order là 'paid'.

    Bảo mật:
      - Verify chữ ký HMAC-SHA256 trước khi xử lý
      - csrf_exempt vì MoMo gọi từ server bên ngoài
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'message': 'Invalid JSON'}, status=400)

    # 1. Verify chữ ký HMAC
    received_signature = data.get('signature', '')
    if not _verify_momo_signature(data, settings.MOMO_SECRET_KEY, received_signature):
        logger.warning("MoMo IPN: Chữ ký không hợp lệ! Data: %s", data)
        return JsonResponse({'message': 'Invalid signature'}, status=403)

    # 2. Lấy thông tin từ IPN
    order_id = data.get('orderId', '')
    try:
        result_code = int(data.get('resultCode', -1))
    except (ValueError, TypeError):
        result_code = -1
    trans_id = str(data.get('transId', ''))

    # 3. Tìm order trong database
    try:
        order = Order.objects.get(order_number=order_id)
    except Order.DoesNotExist:
        logger.warning("MoMo IPN: Không tìm thấy order %s", order_id)
        return JsonResponse({'message': 'Order not found'}, status=404)

    # 4. Xử lý kết quả thanh toán
    if result_code == 0:
        # Thanh toán thành công
        order.payment_status = 'paid'
        order.momo_transaction_id = trans_id
        order.save(update_fields=['payment_status', 'momo_transaction_id'])

        # 2. Trừ stock từng variant
        order_items = OrderItem.objects.filter(order=order).select_related('variant')
        for item in order_items:
            variant = item.variant
            variant.stock = max(0, variant.stock - item.quantity)
            variant.save(update_fields=['stock'])

        # Xóa cart của user (sau khi thanh toán MoMo thành công)
        CartItem.objects.filter(user=order.user, is_active=True).delete()

        logger.info("MoMo IPN: Đơn hàng %s đã thanh toán thành công", order_id)
    else:
        # Thanh toán thất bại
        order.status = 'CANCELLED'
        order.save(update_fields=['status'])
        logger.info("MoMo IPN: Đơn hàng %s thanh toán thất bại (code=%s)", order_id, result_code)

    # 5. Trả response cho MoMo (bắt buộc)
    return JsonResponse({'message': 'OK'}, status=200)


def momo_return_view(request):
    """
    Nhận redirect từ MoMo sau khi user thanh toán xong.

    LƯU Ý: View này KHÔNG đánh dấu paid — chỉ dùng để hiển thị
    kết quả cho user. Việc xác nhận thanh toán chỉ qua IPN.
    """
    try:
        result_code = int(request.GET.get('resultCode', -1))
    except (ValueError, TypeError):
        result_code = -1

    if result_code == 0:
        # Thanh toán thành công → hiển thị trang thành công
        return redirect('order_successful')
    else:
        # Thanh toán thất bại hoặc bị hủy
        messages.error(request, 'Thanh toán MoMo không thành công. Vui lòng thử lại.')
        return render(request, 'orders/order_failed.html')
