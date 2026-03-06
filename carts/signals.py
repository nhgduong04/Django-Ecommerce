from __future__ import annotations # type hint: 

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import merge_session_cart_into_user_cart


@receiver(user_logged_in) # decorator để đăng ký một function làm listener cho signal
# user login thành công thì user_logged_in signal sẽ được gửi đi, và function merge_cart_after_login sẽ được gọi
def merge_cart_after_login(sender, request, user, **kwargs):
    # Best-effort merge; any errors should not block login.
    try:
        merge_session_cart_into_user_cart(request=request, user=user)
    except Exception:
        # In production you might log this (Sentry, etc.).
        return
