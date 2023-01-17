from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import User, Product, OrderItem, ProductInfo, Order, Contact
from django import forms

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from django.contrib.auth import password_validation

class CustomUserCreationForm(UserCreationForm): #регистрация

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2', 'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')
    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            if user.email_confirmed:
                raise ValidationError(_(f'Пользователь с указанным email уже существует.'))
            else:  # В случае если не подтверждена почта user.email_confirmed=False. Например, при повторной регистрации без подтверждения первой. Или кто-то указал до этого эту почту как не свою.
                user.delete()  # Удаляем неподтвержденного пользователя, чтобы пересоздать с возможно новыми полями
        return email

class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')

class PasswordResetForm(forms.Form):
    email = forms.EmailField(label='Email', required=True)
    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise ValidationError(_('Такого пользователя нет, либо он неактивен'))
        return email

class PasswordChangeForm(forms.ModelForm):
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


class ProductForm(forms.ModelForm): #для карточки товара
    product_info = forms.ModelChoiceField(label='Offer', queryset=ProductInfo.objects.all(), required=True)
    class Meta:
        model = Product
        fields = ('product_info',)

    def __init__(self, instance=None, *args, **kwargs): #нужно загрузить в форму объект product для инициализации предложений поставщиков
        super(ProductForm, self).__init__(*args, **kwargs)
        if instance:
            self.fields['product_info'].queryset = ProductInfo.objects.filter(product__id=instance.id)

class OrderItemForm(forms.ModelForm): #для каждой позиции в корзине. для использования в from django.forms import formset_factory
    product_info_id = forms.ModelChoiceField(label='Offer', queryset=ProductInfo.objects.all(), required=True)
    class Meta:
        model = OrderItem
        fields = ('quantity', 'product_info_id')

    def __init__(self, instance=None, *args, **kwargs): #нужно загрузить в форму объект orderitem для инициализации и предоставления выбора предложений по конкретному продукту
        super(OrderItemForm, self).__init__(*args, **kwargs)
        if instance:
            self.fields['product_info_id'].queryset = ProductInfo.objects.filter(product__id=instance.product_info_id.product_id.id)
            self.fields['product_info_id'].initial = instance.product_info_id
            self.fields['quantity'].initial = instance.quantity

class OrderConfirmForm(forms.ModelForm): #для размещения заказы из корзины
    contact_id = forms.ModelChoiceField(label='Contact', queryset=Contact.objects.all(), widget = forms.RadioSelect, required=True)
    class Meta:
        model = Order
        fields = ('contact_id',)

    def __init__(self, instance=None, *args, **kwargs): #нужно загрузить в форму объект order для инициализации контактов
        super(OrderConfirmForm, self).__init__(*args, **kwargs)
        if instance:
            self.fields['contact_id'].queryset = Contact.objects.filter(user_id=instance.user_id.id)
            self.fields['contact_id'].initial = instance.contact_id
