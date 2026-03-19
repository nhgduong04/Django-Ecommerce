from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('all-products/', views.products_list, name='products'),
    path('api/search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('category/<slug:slug>/', views.category_list, name='category'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('product/<slug:slug>/quick-view/', views.product_quick_view, name='product_quick_view'),
]