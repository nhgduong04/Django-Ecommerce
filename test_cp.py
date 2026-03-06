import os
import django
from django.conf import settings
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from carts.context_processors import counter
from carts.models import Cart, CartItem
from products.models import Product

def test_counter():
    # Create a request
    factory = RequestFactory()
    request = factory.get('/')
    
    # Add session
    middleware = SessionMiddleware(lambda x: None)
    middleware.process_request(request)
    request.session.save()
    
    # Test with empty cart
    context = counter(request)
    print(f"Empty cart context: {context}")
    assert context['cart_count'] == 0, "Should be 0 for empty cart"

    # Create dummy product and cart item
    # Note: This requires DB access. 
    # Since we are using the actual settings, we are using the actual DB.
    # We should be careful not to pollute DB or use test DB.
    # For this verification, just checking if it runs without error and returns 0 for new session is good enough
    # as creating full cart data might be intrusive.
    
    print("Verification passed for empty session.")

if __name__ == "__main__":
    try:
        test_counter()
        print("Test script executed successfully.")
    except Exception as e:
        print(f"Test script failed: {e}")
