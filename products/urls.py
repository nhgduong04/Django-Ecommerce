from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('all-products/', views.products_list, name='products'),
    path('category/<slug:slug>/', views.category_list, name='category'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]