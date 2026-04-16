from django import forms
from .models import ProductVariant, Variation, ProductGallery, Review

class ReviewForm(forms.ModelForm):
    rating = forms.FloatField(
        min_value=1,
        max_value=5,
        error_messages={
            'required': 'Vui lòng chọn số sao đánh giá.',
            'min_value': 'Điểm đánh giá tối thiểu là 1 sao.',
            'max_value': 'Điểm đánh giá tối đa là 5 sao.',
        }
    )

    class Meta:
        model = Review
        fields = ['subject', 'review', 'rating']

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
    """Custom form for inline."""
    class Meta:
        model = ProductVariant
        fields = '__all__'

    # Việc lọc variation sẽ được thực hiện ở Admin class thông qua formfield_for_manytomany


class ProductGalleryForm(forms.ModelForm):
    """Custom form that filters variation to only show those belonging to the selected product."""
    class Meta:
        model = ProductGallery
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.product_id:
            # Editing existing gallery image
            self.fields['variation'].queryset = Variation.objects.filter(
                product=self.instance.product
            )
        elif 'product' in self.data:
            # Form submitted with product selected (e.g. adding new gallery image via separate admin)
            try:
                product_id = int(self.data.get('product'))
                self.fields['variation'].queryset = Variation.objects.filter(
                    product_id=product_id
                )
            except (ValueError, TypeError):
                self.fields['variation'].queryset = Variation.objects.none()
        else:
            # New form with no product yet — show nothing
            self.fields['variation'].queryset = Variation.objects.none()

class ProductGalleryInlineForm(forms.ModelForm):
    """Custom form for inline."""
    class Meta:
        model = ProductGallery
        fields = '__all__'

    # Việc lọc variation sẽ được thực hiện ở Admin class thông qua formfield_for_foreignkey
