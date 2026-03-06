from django.urls import path
from django.contrib.auth.views import (
    PasswordResetView, 
    PasswordResetDoneView, 
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from . import views
from .forms import PasswordResetRequestForm, StyledSetPasswordForm

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    # 1. Trang nhập email
    path('password-reset/', 
        PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            form_class=PasswordResetRequestForm,
        ), 
        name='password_reset'),

    # 2. Trang thông báo đã gửi email
    path('password-reset/done/', 
        PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), 
        name='password_reset_done'),

    # 3. Trang đặt lại mật khẩu (nhận uidb64 và token từ URL)
    path('password-reset-confirm/<uidb64>/<token>/', 
        PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            form_class=StyledSetPasswordForm,
        ), 
        name='password_reset_confirm'),

    # 4. Trang thông báo đổi mật khẩu thành công
    path('password-reset-complete/', 
        PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), 
        name='password_reset_complete'),
    path('profile/', views.profile, name='profile'),
    path('profile/orders/', views.orders, name='orders'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/addresses/', views.addresses, name='addresses'),
]