from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from products.models import ProductVariant

@dataclass(frozen=True)
class SessionCartItemDTO:
    id: int # id tạm để nhận diện item trong cart session
    variant: ProductVariant
    quantity: int

    @property
    def product(self):
        return self.variant.product
    
    @property
    def variations(self):
        return self.variant.variations
    
    def sub_total(self):
        return self.variant.get_price() * self.quantity
    
@dataclass(frozen=True)
class CartSummaryDTO:
    items: list
    quantity: int
    total: Decimal

