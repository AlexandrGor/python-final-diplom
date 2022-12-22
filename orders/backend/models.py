from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.tokens import get_token_generator
from datetime import datetime, timedelta
from django.conf import settings
import hashlib
import os
import jwt

STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),

)


# Create your models here.
class UserManager(BaseUserManager):
    """
    Миксин для управления пользователями
    """
    use_in_migrations = True

    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        if password is None:
            raise TypeError('Superusers must have a password.')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """
    Стандартная модель пользователей
    """
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()
    username = None
    email = models.EmailField(_('email address'), db_index=True, max_length=255, unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    middle_name = models.CharField(_('middle name'), max_length=150, blank=True)
    company = models.CharField(_('company'), max_length=40, blank=True)
    position = models.CharField(_('position'), max_length=40, blank=True)
    type = models.CharField(_('type of user'), choices=USER_TYPE_CHOICES, max_length=5, default='buyer')
    # Временная метка создания объекта.
    created_at = models.DateTimeField(auto_now_add=True)
    # Временная метка показывающая время последнего обновления объекта.
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """ Строковое представление модели (отображается в консоли) """
        return f'{self.email}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)

    @property
    def token(self):
        """
        Позволяет получить токен пользователя путем вызова user.token, вместо
        user._generate_jwt_token(). Декоратор @property выше делает это
        возможным.
        """
        return self._generate_jwt_token()

    @property
    def token_password_reset(self):
        return self._generate_jwt_token_password_reset()

    def get_full_name(self):
        """
        Этот метод требуется Django для таких вещей, как обработка электронной
        почты.
        """
        full_name = '%s %s %s' % (self.last_name, self.first_name, self.first_name)
        return full_name.strip()

    def _generate_jwt_token(self):
        """
        Генерирует веб-токен JSON, в котором хранится идентификатор этого
        пользователя, срок действия токена составляет 1 час от создания
        """
        dt = datetime.now() + timedelta(hours=1)

        token = jwt.encode({
            'id': self.pk,
            'exp': int(dt.strftime('%s'))
        }, settings.SECRET_KEY, algorithm='HS256')

        return token #.decode('utf-8') для str не нужен

    def _generate_jwt_token_password_reset(self):
        """
        Генерирует веб-токен JSON, в котором хранится идентификатор этого
        пользователя + 'reset' , срок действия токена составляет 1 час от создания
        """
        dt = datetime.now() + timedelta(hours=1)

        token = jwt.encode({
            'id': str(self.pk)+'reset',
            'exp': int(dt.strftime('%s'))
        }, settings.SECRET_KEY, algorithm='HS256')

        return token #.decode('utf-8') для str не нужен

class Contact(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь',
                             related_name='contacts', blank=True,
                             on_delete=models.CASCADE)
    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=100, verbose_name='Улица')
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=15, verbose_name='Корпус', blank=True)
    building = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.CharField(max_length=100, verbose_name='Электронная почта', blank=True)
    class Meta:
        verbose_name = 'Контакты пользователя'
        verbose_name_plural = "Список контактов пользователя"

    def __str__(self):
        return f'{self.city} {self.street} {self.house}'

class ConfirmEmailToken(models.Model):
    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'

    @staticmethod
    def generate_key():
        """ generates a pseudo random code using os.urandom and binascii.hexlify """
        return get_token_generator().generate_token()

    user = models.ForeignKey(
        User,
        related_name='confirm_email_tokens',
        on_delete=models.CASCADE,
        verbose_name=_("The User which is associated to this password reset token")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("When was this token generated")
    )

    # Key field, though it is not the primary key of the model
    key = models.CharField(
        _("Key"),
        max_length=64,
        db_index=True,
        unique=True
    )

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return "Password reset token for user {user}".format(user=self.user)

class Shop(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название', unique=True) #unique, чтобы сущетсвующий бренд был закреплен только за одним пользователем
    url = models.URLField(verbose_name='Ссылка', null=True, blank=True)
    user_id = models.OneToOneField(User, verbose_name='ID пользователя',
                                blank=True, null=True,
                                on_delete=models.CASCADE)
    state = models.BooleanField(verbose_name='статус получения заказов', default=True)
    # filename

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=40, verbose_name='Название', unique=True)
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', related_name='categories', blank=True, through='ShopCategory')
    #parent = models.ForeignKey("self") #подкатегория
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class ShopCategory(models.Model):
    shop_id = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='shop_categories', verbose_name='Магазин')
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='shop_categories', verbose_name='Категория')
    is_main = models.BooleanField(default=False, verbose_name='Основная категория')
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['shop_id', 'category_id'], name='unique_shop_category')
        ]
        verbose_name = 'Категория товара в магазине'
        verbose_name_plural = 'Список категорий товаров в магазинах'
        ordering = ['-is_main']

class Product(models.Model):
    name = models.CharField(max_length=80, verbose_name='Название')
    category_id = models.ForeignKey(Category, verbose_name='Категория', related_name='products', blank=True,
                                 on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = "Список продуктов"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class ProductInfo(models.Model):
    model = models.CharField(max_length=80, verbose_name='Модель', blank=True) #None в нашем случае будет равен пустой строке, так как это charfield https://django.fun/ru/docs/django/4.1/ref/models/fields/#null
    external_id = models.PositiveIntegerField(verbose_name='Внешний ИД')
    product_id = models.ForeignKey(Product, verbose_name='Продукт', related_name='product_infos', on_delete=models.CASCADE)
    shop_id = models.ForeignKey(Shop, verbose_name='Магазин', related_name='product_infos', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Рекомендуемая розничная цена')

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Информационный список о продуктах"
        constraints = [
            models.UniqueConstraint(fields=['product_id', 'shop_id', 'external_id'], name='unique_product_info'),
        ]

class Parameter(models.Model):
    name = models.CharField(max_length=40, verbose_name='Название', unique=True)

    class Meta:
        verbose_name = 'Имя параметра'
        verbose_name_plural = "Список имен параметров"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info_id = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте',
                                     related_name='product_parameters',
                                     on_delete=models.CASCADE)
    parameter_id = models.ForeignKey(Parameter, verbose_name='Параметр', related_name='product_parameters',
                                     on_delete=models.CASCADE)
    value = models.CharField(verbose_name='Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"
        constraints = [
            models.UniqueConstraint(fields=['product_info_id', 'parameter_id'], name='unique_product_parameter'),
        ]

class Order(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь',
                             related_name='orders', blank=True,
                             on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True)
    status = models.CharField(verbose_name='Статус', choices=STATE_CHOICES, max_length=15)
    contact = models.ForeignKey(Contact, verbose_name='Контакт',
                                blank=True, null=True,
                                on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказ"
        ordering = ('-dt',)

    def __str__(self):
        return str(self.dt)

    # @property
    # def sum(self):
    #     return self.ordered_items.aggregate(total=Sum("quantity"))["total"]

class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name='Заказ', related_name='ordered_items', blank=True,
                              on_delete=models.CASCADE)

    product_info = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте', related_name='ordered_items',
                                     blank=True,
                                     on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = 'Заказанная позиция'
        verbose_name_plural = "Список заказанных позиций"
        constraints = [
            models.UniqueConstraint(fields=['order', 'product_info'], name='unique_order_item'),
        ]

