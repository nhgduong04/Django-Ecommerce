from django import forms
from .models import ProductVariant, Variation

class ProductVariantForm(forms.ModelForm):
    """Custom form that filters variations to only show those belonging to the selected product."""
    class Meta:
        model = ProductVariant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.product_id:
            # Editing existing variant — filter by its product
            self.fields['variations'].queryset = Variation.objects.filter(
                product=self.instance.product
            )
        elif 'product' in self.data:
            # Form submitted with product selected (e.g. adding new variant)
            try:
                product_id = int(self.data.get('product'))
                self.fields['variations'].queryset = Variation.objects.filter(
                    product_id=product_id
                )
            except (ValueError, TypeError):
                self.fields['variations'].queryset = Variation.objects.none()
        else:
            # New form with no product yet — show nothing
            self.fields['variations'].queryset = Variation.objects.none()

class ProductVariantInlineForm(forms.ModelForm):
    """Custom form for inline — filters variations by the parent product."""
    class Meta:
        model = ProductVariant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        # Lấy parent_product được truyền từ get_form_kwargs của formset
        parent_product = kwargs.pop('parent_product', None)
        super().__init__(*args, **kwargs)
        
        # Ưu tiên lọc theo parent_product (dành cho cả dòng cũ và dòng mới thêm)
        if parent_product:
            self.fields['variations'].queryset = Variation.objects.filter(product=parent_product)
        elif self.instance and self.instance.pk and self.instance.product_id:
            self.fields['variations'].queryset = Variation.objects.filter(product=self.instance.product)
        else:
            self.fields['variations'].queryset = Variation.objects.none()