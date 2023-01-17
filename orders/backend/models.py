from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Sum, Count, Q
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
from django.conf import settings
import jwt

STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    # подразумевается сервис, в котором доставка до покупателя осуществляется только
    # полностью укопмлектованного по всем позициям заказа, т.е. сервис "разовой доставки или выдачи",
    # где учет собранных позиций в заказе (OrderItem'ов) ведётся видимо партнёром,
    # который принимает решение о смене статуса заказа через админку.
    # Для сервиса "частичной выдачи" нужно status указывать не для Order, а для OrderItem'a.
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),

)

COST_OF_ONE_DELIVERY = 200 #фиксированная стоимость доставки от одного магазина

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
    # Полe is_active при регистрации будет false, а после подтверждения email - true
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    # Временная метка создания объекта.
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    # Временная метка показывающая время последнего обновления объекта.
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    # Служебное поле email_confirmed. Нужно, например, для проверки при повторной регистрации без подтверждения по email первой
    # (или если кто-то указал до этого эту почту как не свою),
    # так как поле is_active недостаточно для этой роли (оно может играть роль бана).
    # Так как при регистрации сначала указываются все из доступных полей, а потом подтверждается email и
    # is_active становится True, создаётся предварительная запись в БД пользователя с указанными в запросе полями.
    email_confirmed = models.BooleanField(_('email confirmed'), default=False)

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

    @property
    def token_email_confirm(self):
        return self._generate_jwt_token_email_confirm()

    @property
    def full_name(self):
        return self.get_full_name()

    def get_full_name(self):
        """
        Этот метод требуется Django для таких вещей, как обработка электронной
        почты.
        """
        full_name = '%s %s %s' % (self.last_name, self.first_name, self.middle_name)
        return full_name.strip()

    def _generate_jwt_token(self):
        """
        Генерирует веб-токен JSON, в котором хранится идентификатор этого
        пользователя, срок действия токена составляет 12 часов от создания
        """
        dt = datetime.now() + timedelta(hours=12)

        token = jwt.encode({
            'id': self.pk,
            'exp': int(dt.strftime('%s'))
        }, settings.SECRET_KEY, algorithm='HS256')

        return token #.decode('utf-8') для str не нужен

    def _generate_jwt_token_password_reset(self): #для восстановления пароля
        """
        Генерирует веб-токен JSON, в котором хранится идентификатор этого
        пользователя + 'reset' , срок действия токена составляет 30 минут от создания
        """
        dt = datetime.now() + timedelta(minutes=30)

        token = jwt.encode({
            'id': str(self.pk)+'reset',
            'exp': int(dt.strftime('%s'))
        }, settings.SECRET_KEY, algorithm='HS256')

        return token #.decode('utf-8') для str не нужен

    def _generate_jwt_token_email_confirm(self): #для подтверждения почты
        """
        Генерирует веб-токен JSON, в котором хранится идентификатор этого
        пользователя + 'email' , срок действия токена составляет 7 дней от создания
        """
        dt = datetime.now() + timedelta(days=7)

        token = jwt.encode({
            'id': str(self.pk)+'email',
            'exp': int(dt.strftime('%s'))
        }, settings.SECRET_KEY, algorithm='HS256')

        return token #.decode('utf-8') для str не нужен

class Contact(models.Model):
    user_id = models.ForeignKey(User, verbose_name='Пользователь',
                             related_name='contacts', blank=True,
                             on_delete=models.CASCADE)
    city = models.CharField(max_length=50, verbose_name='Город', blank=True)
    street = models.CharField(max_length=100, verbose_name='Улица', blank=True)
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=15, verbose_name='Корпус', blank=True) #корпус
    building = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)
    is_active = models.BooleanField(_('active'), default=True)  #чтобы можно было не удалять, для архивности (для истории заказов и указаных им адресов)
    class Meta:
        verbose_name = 'Контакты пользователя'
        verbose_name_plural = "Список контактов пользователя"
        constraints = [ #минимальный контакт может быть двух типов: с телефоном, с адрессом. Контакт только с телефоном может быть полезен при самовывозе
            models.CheckConstraint(check=(~Q(city='') & ~Q(street='') & ~Q(house=''))
                                         | ~Q(phone=''), name='phone_or_address_reqiured')
        ]

    def __str__(self):
        return f'{self.phone} {self.city} {self.street} {self.house}'



class Shop(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название', unique=True) #unique, чтобы сущетсвующий бренд был закреплен только за одним пользователем
    url = models.URLField(verbose_name='Ссылка', null=True, blank=True)
    user_id = models.OneToOneField(User, verbose_name='ID пользователя', #shop <-> user отношение 1к1, чтобы под одним email был один магазин
                                blank=True, null=True,
                                on_delete=models.CASCADE)
    is_active = models.BooleanField(_('active'), default=True)  # для включения и отключения приема заказов


    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=40, verbose_name='Название', unique=True)
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', related_name='categories', blank=True, through='ShopCategory')
    parent_id = models.ForeignKey("self", on_delete=models.CASCADE, related_name='childs', verbose_name='Родительская категория', null=True, blank=True)
    is_active = models.BooleanField(_('active'), default=True) #для того, чтобы не удалять категории, так как при их удалении удаляться и продукты, и предложения по ним, и order_item'ы (не будут отображаться информация по позициям в архивных заказах)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class ShopCategory(models.Model):
    shop_id = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='shop_categories', verbose_name='Магазин')
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='shop_categories', verbose_name='Категория')
    is_main = models.BooleanField(default=False, verbose_name='Основная категория') #допускается несколько основных категорий
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['shop_id', 'category_id'], name='unique_shop_category')
        ]
        verbose_name = 'Категория товара в магазине'
        verbose_name_plural = 'Список категорий товаров в магазинах'
        ordering = ['-is_main']

    def __str__(self): #для вызова из ShopsSerializer
        return self.category_id.name

class Product(models.Model):
    name = models.CharField(max_length=80, verbose_name='Название')
    category_id = models.ForeignKey(Category, verbose_name='Категория', related_name='products', blank=True,
                                 on_delete=models.CASCADE)
    is_active = models.BooleanField(_('active'), default=False) #для того, чтобы не удалять записи product_info, так как при их удалении удаляться и order_item'ы (не будут отображаться информация по позиции в архивных заказах)

    @property  # для удобного получения названия категории
    def category(self):
        return Category.objects.get(pk=self.category_id.id).name

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = "Список продуктов"
        ordering = ('-name',)

    def __str__(self):
        return self.name

    def check_actual(self): # если по продукту нет предложений, или приём заказов по ним отключен, то is_active = False и наоборот
        is_active_change = True
        if not self.product_info.all().filter(is_active=True, shop_id__is_active=True).first():
            is_active_change = False
        if self.is_active != is_active_change:
            self.is_active = is_active_change
            self.save()

class ProductInfo(models.Model):
    model = models.CharField(max_length=80, verbose_name='Модель', blank=True) #None в нашем случае будет равен пустой строке, так как это charfield https://django.fun/ru/docs/django/4.1/ref/models/fields/#null
    external_id = models.PositiveIntegerField(verbose_name='Внешний ИД')
    product_id = models.ForeignKey(Product, verbose_name='Продукт', related_name='product_info', on_delete=models.CASCADE)
    shop_id = models.ForeignKey(Shop, verbose_name='Магазин', related_name='product_info', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Рекомендуемая розничная цена')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) #пока не имеет большого смысла, так как пока предложения магазинов обновляются полным пересозданием
    is_active = models.BooleanField(_('active'), default=True) #для того, чтобы не удалять записи product_info, так как при их удалении удаляться и order_item'ы (не будут отображаться информация по позиции в архивных заказах)

    @property #для вызова из сериализатора
    def product(self):
        return Product.objects.get(id=self.product_id.id).name

    @property  # для вызова из сериализатора
    def shop(self):
        return Shop.objects.get(id=self.shop_id.id).name

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Информационный список о продуктах"
        constraints = [
           models.UniqueConstraint(fields=['product_id', 'shop_id', 'external_id', 'is_active'], name='unique_product_info'), #допускается, что у одного магазина могут быть разные предложения (партии, разная свежесть т.д) на один и тот же товар, но тогда у них должны отличаться external_id
        ]

    def __str__(self):
        return f'{self.shop} {self.price}'

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

    @property  # для удобного вызова имени параметра из сериализатора
    def parameter(self):
        return Parameter.objects.get(pk=self.parameter_id.id).name

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"
        constraints = [
            models.UniqueConstraint(fields=['product_info_id', 'parameter_id'], name='unique_product_parameter'),
        ]

class Order(models.Model):
    user_id = models.ForeignKey(User, verbose_name='Пользователь', #для одного пользователя должен быть только один order со статусом ('basket', 'Статус корзины')
                             related_name='orders', blank=True, null=True, #чтобы в будущем корзина могла собираться для незарегистрированного пользователя на сайте через куки
                             on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(verbose_name='Статус', choices=STATE_CHOICES, max_length=15)
    contact_id = models.ForeignKey(Contact, verbose_name='Контакт',
                                blank=True, null=True, related_name='orders',
                                on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказ"
        ordering = ('-created_at',)

    def __str__(self):
        return str(self.pk)

    @property
    def total_quantity(self):
        return self.ordered_items.aggregate(total=Sum("quantity"))["total"] or 0

    @property
    def cost_of_delivery(self): # чем больше разных магазинов в заказе, тем дороже доставка
        return len(self.ordered_items.values("product_info_id__shop_id__id").annotate(
            Count("product_info_id__shop_id__id")
            ).order_by()
        )*COST_OF_ONE_DELIVERY

    @property
    def total_price(self):
        items_price = self.ordered_items.aggregate(total=Sum(F("product_info_id__price")*F("quantity")))["total"] or 0
        return items_price + self.cost_of_delivery

class OrderItem(models.Model):
    order_id = models.ForeignKey(Order, verbose_name='Заказ', related_name='ordered_items', blank=True,
                              on_delete=models.CASCADE)

    product_info_id = models.ForeignKey(ProductInfo, verbose_name='Информация о продукте', related_name='ordered_items',
                                     blank=True,
                                     on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name='Количество', default=1)

    def quantity_add(self, amount=1): #функция для добавления количества товара в корзину
        self.quantity+=amount
        return self.save()

    class Meta:
        verbose_name = 'Заказанная позиция'
        verbose_name_plural = "Список заказанных позиций"
        constraints = [
            models.UniqueConstraint(fields=['order_id', 'product_info_id'], name='unique_order_item'),
        ]

