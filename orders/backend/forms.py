from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import User
from django import forms

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from django.contrib.auth import password_validation

class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')

class FormPasswordReset(forms.Form):
    email = forms.EmailField(label='Email', required=True)
    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise ValidationError(_('Такого пользователя нет, либо он неактивен'))
        return email

class FormPasswordChange(forms.ModelForm):
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )
    class Meta:
        model = User
        fields = ("password",)

    def _post_clean(self):
        super()._post_clean()
        # Validate the password after self.instance is updated with form data
        # by super().
        password = self.cleaned_data.get('password')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password', error)