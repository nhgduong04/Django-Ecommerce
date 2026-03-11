from django import forms
from .models import Order

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'phone', 'email', 'address', 'province', 'district', 'ward', 'order_note']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.isdigit():
            raise forms.ValidationError("Số điện thoại chỉ bao gồm các chữ số.")
        if len(phone) < 10 or len(phone) > 11:
            raise forms.ValidationError("Số điện thoại không hợp lệ.")
        return phone