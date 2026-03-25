from django.urls import path
from . import views

urlpatterns = [
    path('coupon/apply/',  views.apply_coupon,  name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='remove_coupon'),
]
