from django.urls import path
from . import views

urlpatterns = [
    path('place-order/', views.place_order_view, name='place_order'),
    path('order-successful/', views.order_success_view, name='order_successful'),
    path('payment/momo/ipn/', views.momo_ipn_view, name='momo_ipn'),
    path('payment/momo/return/', views.momo_return_view, name='momo_return'),
]