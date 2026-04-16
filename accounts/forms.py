from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Email", required=True)
    first_name = forms.CharField(label="First Name", max_length=30, required=True)
    last_name = forms.CharField(label="Last Name", max_length=30, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email'] 
        # note: password đã được bao gồm trong UserCreationForm, nên không cần thêm vào fields ở đây

    def __init__(self, *args, **kwargs): # ghi đè constructor của form
        super().__init__(*args, **kwargs) # gọi constructor của lớp cha-UserCreationForm để khởi tạo form như bình thường
                                          # Nếu không có dòng này, form sẽ không được khởi tạo đúng cách và sẽ thiếu các trường mặc định như password1 và password2
        for field in self.fields:
            self.fields[field].widget.attrs.update({ # inject CSS class và placeholder vào tất cả các trường của form
                'class': 'form-control border-0 bg-secondary',
                'placeholder': f"{self.fields[field].label}"
            })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng.")
        return email

class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control border-0 bg-secondary',
                'placeholder': f"{self.fields[field].label}"
            })


class PasswordResetRequestForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control border-0 bg-secondary',
                'placeholder': f"{self.fields[field].label}",
            })


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control border-0 bg-secondary',
                'placeholder': f"{self.fields[field].label}",
            })
