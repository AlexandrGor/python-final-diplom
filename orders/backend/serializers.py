from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, ProductInfo, ProductParameter, Product, Category, Shop, Order, OrderItem, Contact
from django.conf import settings
import jwt
import json
from django.utils.translation import gettext_lazy as _


class RegistrationSerializer(serializers.ModelSerializer):
    """ Сериализация регистрации пользователя и создания нового. """
    # Убедитесь, что пароль содержит не менее 8 символов, не более 128,
    # и так же что он не может быть прочитан клиентской стороной
    password = serializers.CharField( #можно сделать через валидацию джанго -> from django.contrib.auth import password_validation
        max_length=128,
        min_length=8,
        write_only=True
    )
    is_active = serializers.ReadOnlyField()
    is_staff = serializers.ReadOnlyField() #при регистрации поле будет false
    email_confirmed = serializers.ReadOnlyField() #при регистрации поле будет false, а после подтверждения email true
    email = serializers.CharField(max_length=255)
    class Meta:
        model = User
        # Перечислить все поля, которые могут быть включены в запрос
        # или ответ, включая поля, явно указанные выше.
        fields = ['email', 'password', 'first_name', 'middle_name', 'last_name', 'company', 'position', 'type',
                  'email_confirmed', 'is_active', 'is_staff']

    def validate(self, data):
        email = data.get('email')
        user = User.objects.filter(email=email).first()
        if user:
            if user.email_confirmed:
                msg = f'Пользователь с указанным email уже существует.'
                raise serializers.ValidationError(msg)
            else:   #В случае если не подтверждена почта user.email_confirmed=False. Например, при повторной регистрации без подтверждения первой. Или кто-то указал до этого эту почту как не свою.
                user.delete() #Удаляем неподтвержденного пользователя, чтобы пересоздать с возможно новыми полями
        return data


    def create(self, validated_data):
        # Использовать метод create_user для создания нового пользователя.
        return User.objects.create_user(**validated_data)

class RegistrationConfirmSerializer(serializers.Serializer):
    # email = serializers.EmailField(max_length=255)        #не используется, так как пользователь определяется декодированием jwt-токена
    token = serializers.CharField(max_length=255, write_only=True)

    def validate(self, data):
        # email = data.get('email', None)
        # Вызвать исключение, если не предоставлена почта.
        # if email is None:
        #    raise serializers.ValidationError(
        #        'An email address is required to confirm reset password.'
        #    )
        # email = email.lower()
        token = data.get('token', None)
        # декодировка токена
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except Exception:
            raise serializers.ValidationError(
                'Ошибка аутентификации. Невозможно декодировать токен.'
            )
        if payload['id'][-5:] != 'email':
            raise serializers.ValidationError(
                'Токен верен, но не для подтверждения почты.'
            )
        try:
            user = User.objects.get(pk=payload['id'][:-5])
        except User.DoesNotExist:  # не обращаем внимания на warning в IDE, работает правильно
            raise serializers.ValidationError(
                'Пользователь соответствующий данному токену не найден.'
            )
        if user.email_confirmed:
            raise serializers.ValidationError(
                'Учетная запись пользователя уже подтверждена.'
            )

        # для дополнительной проверки поля email можно добавить:
        # if user.email != email:
        #    raise serializers.ValidationError(
        #        'Email и токен не соответсвуют друг другу.'
        #    )

        # Метод validate должен возвращать словарь проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update из метода save
        return {
            'user': user
        }

    def save(self, **kwargs):  # переопределение метода save
        user = self.validated_data['user'] # в validated_data должны попасть значения с дополнительной проверки def validate()
        user.is_active = True
        user.email_confirmed = True
        user.save()

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )
    # Клиентская сторона не должна иметь возможность отправлять токен вместе с
    # запросом на регистрацию. Сделаем его доступным только на чтение.
    token = serializers.CharField(read_only=True)

    def validate(self, data):
        # В методе validate мы убеждаемся, что текущий экземпляр
        # LoginSerializer значение valid. В случае входа пользователя в систему
        # это означает подтверждение того, что присутствуют адрес электронной
        # почты и то, что эта комбинация соответствует одному из пользователей.
        email = data.get('email', None)
        password = data.get('password', None)

        # Вызвать исключение, если не предоставлена почта.
        if email is None:
            raise serializers.ValidationError(_(
                'An email address is required to log in.'
            ))

        # Вызвать исключение, если не предоставлен пароль.
        if password is None:
            raise serializers.ValidationError(_(
                'A password is required to log in.'
            ))

        # Метод authenticate предоставляется Django и выполняет проверку, что
        # предоставленные почта и пароль соответствуют какому-то пользователю в
        # нашей базе данных. Мы передаем email как username, так как в модели
        # пользователя USERNAME_FIELD = email.
        user = authenticate(username=email, password=password) #стандартная django аутентификация по логину и паролю

        # Если пользователь с данными почтой/паролем не найден, то authenticate
        # вернет None. Возбудить исключение в таком случае.
        if user is None:
            raise serializers.ValidationError(_(
                'A user with this email and password was not found.'
            ))

        # Django предоставляет флаг is_active для модели User. Его цель
        # сообщить, был ли пользователь деактивирован или заблокирован.
        # Проверить стоит, вызвать исключение в случае True.
        if not user.is_active:
            raise serializers.ValidationError(_(
                'This user has been deactivated.'
            ))

        if not user.email_confirmed:
            raise serializers.ValidationError(_(
                'Email not verified. Please confirm your email.'
            ))

        # Метод validate должен возвращать словать проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update.
        return {
            'email': user.email,
            'token': user.token
        }


class UserSerializer(serializers.ModelSerializer):
    """ Ощуществляет сериализацию и десериализацию объектов User. """
    password = serializers.CharField(  #можно сделать через валидацию джанго -> from django.contrib.auth import password_validation
        max_length=128,
        min_length=8,
        write_only=True
    )
    is_active = serializers.ReadOnlyField() #без возможности изменения
    is_staff = serializers.ReadOnlyField() #без возможности изменения
    email = serializers.ReadOnlyField() #возможность изменения необходимо реализовать через отдельный эндпоинт, так как для изменения email требуется подтверждение по почте
    class Meta:
        model = User
        fields = ('email', 'password', 'is_active', 'is_staff',
                  'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')

    def update(self, instance, validated_data):
        """ Выполняет обновление User. """

        # В отличие от других полей, пароли не следует обрабатывать с помощью
        # setattr. Django предоставляет функцию, которая обрабатывает пароли
        # хешированием и 'солением'. Это означает, что нам нужно удалить поле
        # пароля из словаря 'validated_data' перед его использованием далее.
        password = validated_data.pop('password', None)

        for key, value in validated_data.items():
            # Для ключей, оставшихся в validated_data мы устанавливаем значения
            # в текущий экземпляр User по одному.
            setattr(instance, key, value)

        if password is not None:
            # 'set_password()' решает все вопросы, связанные с безопасностью
            # при обновлении пароля, потому нам не нужно беспокоиться об этом.
            instance.set_password(password)

        # После того, как все было обновлено, мы должны сохранить наш экземпляр
        # User. Стоит отметить, что set_password() не сохраняет модель.
        instance.save()

        return instance

class UserPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    token = serializers.CharField(read_only=True)
    def validate(self, data):
        email = data.get('email', None)
        # Вызвать исключение, если не предоставлена почта.
        if email is None:
            raise serializers.ValidationError(
                'An email address is required to reset password.'
            )
        # Метод authenticate предоставляется Django и выполняет проверку, что
        # предоставленные почта и пароль соответствуют какому-то пользователю в
        # нашей базе данных. Мы передаем email как username, так как в модели
        # пользователя USERNAME_FIELD = email.
        email = email.lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist: #не обращаем внимания на warning в IDE, работает правильно
            msg = 'Пользователь соответствующий данному email не найден.'
            raise serializers.ValidationError(msg)

            # Django предоставляет флаг is_active для модели User. Его цель
            # сообщить, был ли пользователь деактивирован или заблокирован.
            # Проверить стоит, вызвать исключение в случае True.
        if not user.is_active:
            msg = 'Учетная запись пользователя была деактивирована.'
            raise serializers.ValidationError(msg)
        # Метод validate должен возвращать словать проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update.
        return {
            'email': user.email,
            'token': user.token_password_reset
        }

class UserPasswordResetConfirmSerializer(serializers.Serializer):
    #email = serializers.EmailField(max_length=255)        #не используется, так как пользователь определяется декодированием jwt-токена
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )
    token = serializers.CharField(max_length=255, write_only=True)
    def validate(self, data):
        #email = data.get('email', None)
        # Вызвать исключение, если не предоставлена почта.
        #if email is None:
        #    raise serializers.ValidationError(
        #        'An email address is required to confirm reset password.'
        #    )
        #email = email.lower()

        new_password = data.get('password', None)
        # Вызвать исключение, если не предоставлен пароль.
        if new_password is None:
            raise serializers.ValidationError(
                'A password is required.'
            )

        token = data.get('token', None)
        # декодировка токена
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except Exception:
            raise serializers.ValidationError(
                'Ошибка аутентификации. Невозможно декодировать токен.'
            )
        if payload['id'][-5:] != 'reset':
            raise serializers.ValidationError(
                'Токен верен, но не для восстановления пароля.'
            )
        try:
            user = User.objects.get(pk=payload['id'][:-5])
        except User.DoesNotExist:  # не обращаем внимания на warning в IDE, работает правильно
            raise serializers.ValidationError(
                'Пользователь соответствующий данному токену не найден.'
            )
        if not user.is_active:
            raise serializers.ValidationError(
                'Учетная запись пользователя деактивирована.'
            )

        #для дополнительной проверки поля email можно добавить:
        #if user.email != email:
        #    raise serializers.ValidationError(
        #        'Email и токен не соответсвуют друг другу.'
        #    )

        # Метод validate должен возвращать словать проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update из метода save
        return {
            'user': user,
            'new_password': new_password
        }
    def save(self, **kwargs): #переопределение метода save
        user = self.validated_data['user']
        new_password = self.validated_data['new_password'] #в validated_data должны попасть значения с нашей дополнительной проверки def validate()
        user.set_password(new_password)
        user.save()

class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.ReadOnlyField() #parameter.name
    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value')

class ProductInfoAllOffersSerializer(serializers.ModelSerializer): #вывод всей базы-прайса всех магазинов без привязки к одному продукту
    offer_id = serializers.IntegerField(source='id', read_only=True) #переименовал поле id, чтобы было понятно из названия к чему он относится
    product = serializers.ReadOnlyField()
    shop = serializers.ReadOnlyField()
    product_parameters = ProductParameterSerializer(read_only=True, many=True)
    category_id = serializers.PrimaryKeyRelatedField(read_only=True, source='product_id.category_id')
    category = serializers.CharField(read_only=True, source='product_id.category')
    class Meta:
        model = ProductInfo
        fields = ('offer_id', 'shop', 'shop_id', 'product', 'product_id', 'category', 'category_id', 'model',
                  'product_parameters', 'price', 'price_rrc', 'quantity', 'external_id', 'created_at' , 'updated_at')

class ProductInfoSerializer(serializers.ModelSerializer):
    #product = serializers.ReadOnlyField()
    offer_id = serializers.IntegerField(source='id', read_only=True) #переименовал поле id, чтобы было понятно из названия к чему он относится
    shop = serializers.ReadOnlyField()
    product_parameters = ProductParameterSerializer(read_only=True, many=True)
    class Meta:
        model = ProductInfo
        fields = ('offer_id', 'shop', 'shop_id', 'model', 'price', 'price_rrc', 'product_parameters',
                  'quantity', 'external_id', 'created_at', 'updated_at')

class ProductInfoLiteSerializer(serializers.ModelSerializer):
    product = serializers.ReadOnlyField()
    offer_id = serializers.IntegerField(source='id') #переименовал поле id, чтобы было понятно из названия к чему он относится
    shop = serializers.ReadOnlyField()
    class Meta:
        model = ProductInfo
        fields = ('offer_id', 'product', 'product_id', 'shop', 'shop_id', 'model', 'price')

class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.ReadOnlyField()
    offers = serializers.ListSerializer(child=serializers.CharField(), source='actual_product_info')
    class Meta:
        model = Product
        fields = ('id', 'name', 'category', 'category_id', 'offers')

class CategoriesSerializer(serializers.ModelSerializer):
    shops = serializers.ListSerializer(child=serializers.CharField(), read_only=True)
    shop_ids = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='shops')
    products = serializers.ListSerializer(child=serializers.CharField(), read_only=True)
    product_ids = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='products')
    parent_category = serializers.CharField(read_only=True, source='parent_id.name', default=None)
    parent_category_id = serializers.PrimaryKeyRelatedField(read_only=True, source='parent_id')
    child_categories = serializers.ListSerializer(child=serializers.CharField(), source='childs', read_only=True)
    child_category_ids = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='childs')
    class Meta:
        model = Category
        fields = ('id', 'name', 'shops', 'shop_ids', 'products', 'product_ids', 'parent_category', 'parent_category_id',
                  'child_categories', 'child_category_ids')

class ShopsSerializer(serializers.ModelSerializer):
    categories = serializers.ListSerializer(child=serializers.CharField(), read_only=True, source='shop_categories')
    category_ids = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='shop_categories')
    class Meta:
        model = Shop
        fields = ('id', 'name', 'url', 'user_id', 'is_active', 'categories', 'category_ids')

class OrderItemSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    product_info = ProductInfoLiteSerializer(read_only=True, source='product_info_id')
    product_info_id = serializers.IntegerField(write_only=True, min_value=0)
    class Meta:
        model = OrderItem
        fields = ('id', 'quantity', 'product_info', 'product_info_id') #order_item.quantity default=1 поэтому допускается не указывать в post-запросе

    def validate(self, data): #проверка существования product_info_id, shop.is_active, product_info_id.is_active, а также что его quantity достаточно
        product_info_id = data.get('product_info_id', None)
        quantity = data.get('quantity', 1)

        if product_info_id is None:
            raise serializers.ValidationError(
                'Вы не указали значение поля product_info_id.'
            )
        try:
            product_info = ProductInfo.objects.select_related('shop_id').get(id=product_info_id, is_active=True)
        except ProductInfo.DoesNotExist:
            msg = f'Предложения (product_info) с id = {product_info_id} нет.'
            raise serializers.ValidationError(msg)
        if not product_info.shop_id.is_active:
            msg = f'Поставщик предложения (product_info) с id = {product_info_id} приостановил приём заказов.'
            raise serializers.ValidationError(msg)
        #определение сколько данного товара у данного пользователя уже лежит в корзине
        basket_item_quantity=0
        order_item = OrderItem.objects.select_related('order_id__user_id', 'product_info_id').filter(
                                                                                        order_id__user_id__id=self.context['request'].user.id,
                                                                                        order_id__status='basket',
                                                                                        product_info_id__id=product_info.id
                                                                                        ).first() #или query или none
        if order_item:
            basket_item_quantity=order_item.quantity
        if basket_item_quantity+quantity > product_info.quantity: #кол-во в корзине + кол-во в заявке на добавление > кол-ва "в магазине"
            msg = f'В корзине не может быть большего количества, чем есть у поставщика. {basket_item_quantity} + {quantity} > {product_info.quantity} (product_info с id = {product_info_id}).'
            raise serializers.ValidationError(msg)
        # Метод validate должен возвращать словарь проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update.
        return {
            'product_info_id': product_info_id,
            'quantity': quantity
        }

    def create(self, validated_data):
        order, _ = Order.objects.get_or_create(user_id=self.context['request'].user, status='basket')  #для одного пользователя должен быть только один order со статусом ('basket', 'Статус корзины')
        product_info = ProductInfo(id=validated_data['product_info_id'])
        order_item = OrderItem.objects.filter(order_id=order.id, product_info_id=product_info.id).first() #returns the first result in a filter query, or None.
        if order_item: #Если товар уже в корзине, то добавляем quantity
            order_item.quantity_add(validated_data['quantity'])
        else:
            OrderItem.objects.create(order_id=order, quantity=validated_data['quantity'], product_info_id=product_info)
            order_item = OrderItem.objects.filter(order_id=order.id, product_info_id=product_info.id).first() #повторный запрос. решение проблемы, когда при первом создании [при order_item = OrderItem.objects.create(...] в ответе post-запроса позиции в "product_info": отображались как None
        return order_item

    # def to_representation(self, instance): #нерабочее решение проблемы. результат не изменился. при первом создании [при order_item = OrderItem.objects.create(...] в ответе post-запроса позиции в "product_info": отображались как none
    #     # get representation from ModelSerializer
    #     ret = super(OrderItemSerializer, self).to_representation(instance)
    #     # if product_info is None, overwrite
    #     if not ret["product_info"].get("product", None):
    #         ret["product_info"] = json.loads(json.dumps(ProductInfoLiteSerializer(instance.product_info_id, read_only=True).data))
    #     return ret

#class OrderItemsSerializer(serializers.Serializer):
#    items = OrderItemSerializer(many=True)

class OrderItemPUTSerializer(serializers.ModelSerializer): #измененный OrderItemSerializer. для PUT-запроса другая функция validate и id не read_only
    product_info = ProductInfoLiteSerializer(read_only=True, source='product_info_id')
    id = serializers.IntegerField(min_value=0)
    class Meta:
        model = OrderItem
        fields = ('id', 'quantity', 'product_info')
        extra_kwargs = {'quantity': {'required': True}} #так как OrderItem.quantity default=1 => blank=true

    def validate(self, data): #проверка существования order_item'a для корзины данного пользователя, а также что quantity < product_info.quantity
        order_item_id = data.get('id')
        quantity = data.get('quantity')
        order_item = OrderItem.objects.select_related('product_info_id__shop_id').filter(id=order_item_id,
                                              order_id__user_id__id=self.context['request'].user.id,
                                              order_id__status='basket').first()
        if not order_item:
            msg = f'Позиции в корзине с id = {order_item_id} не существует.'
            raise serializers.ValidationError(msg)
        if not order_item.product_info_id.shop_id.is_active:
            msg = f'Поставщик предложения (product_info) с id = {order_item.product_info_id.id} приостановил приём заказов.'
            raise serializers.ValidationError(msg)
        if quantity > order_item.product_info_id.quantity: #кол-во в заявке > кол-ва "в магазине"
            msg = f'В корзине не может быть большего количества, чем есть у поставщика. {quantity} >' \
                  f' {order_item.product_info_id.quantity} (product_info с id = {order_item.product_info_id.id}).'
            raise serializers.ValidationError(msg)
        # Метод validate должен возвращать словарь проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update.
        return {
            'id': order_item_id,
            'quantity': quantity
        }

    def create(self, validated_data):
        order_item = OrderItem.objects.filter(id=validated_data['id']).first()
        order_item.quantity = validated_data['quantity']
        order_item.save()
        return order_item

class ContactSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField() #id в post указывать не нужно, но если указать проверки этого поля не будет, для patch его проверка во view
    class Meta:
        model = Contact
        exclude = ('user_id', 'is_active')
    def validate(self, attrs):
        if attrs.get('phone', '') != '' or (attrs.get('city', '') != '' and attrs.get('street', '') != '' and attrs.get('house', '') != ''):
            return attrs
        else:
            msg = f'Для контакта необходимо указать либо телефон, либо город, улицу и дом.'
            raise serializers.ValidationError(msg)
    def create(self, validated_data):
        return Contact.objects.create(user_id=self.context['request'].user, **validated_data)

class OrderLiteSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField() #id в post указывать не нужно, но если указать проверки этого поля не будет
    contact_info = ContactSerializer(read_only=True, source='contact_id')
    total_quantity = serializers.ReadOnlyField()
    cost_of_delivery = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    contact = serializers.IntegerField(min_value=0, write_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'status', 'total_quantity', 'cost_of_delivery', 'total_price', 'created_at', 'updated_at', 'contact_info', 'contact')


class OrderSerializer(serializers.ModelSerializer): #для детального просмотра заказа
    id = serializers.ReadOnlyField()  # id в post указывать не нужно, но если указать проверки этого поля не будет
    contact_info = ContactSerializer(read_only=True, source='contact_id')
    total_quantity = serializers.ReadOnlyField()
    cost_of_delivery = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    contact = serializers.IntegerField(min_value=0, write_only=True)
    status = serializers.CharField(read_only=True)
    ordered_items = OrderItemSerializer(read_only=True, many=True)
    class Meta:
        model = Order
        fields = ('id', 'status', 'total_quantity', 'cost_of_delivery', 'total_price', 'created_at', 'updated_at', 'contact_info', 'contact', 'ordered_items')

    def validate(self, data):
        """
            Проверка:
            1. Cуществования корзины данного пользователя, + то что total_quantity != 0.
            2. Проверка существования контакта.
            3. Предложение по товару не снято.
            4. Магазин принимает заказы.
            5. Количество предложения по каждому товару хватает (оно могло критически изменится, пока корзина собиралась).
        """
        user_id = self.context['request'].user.id
        order = Order.objects.filter(user_id=user_id, status='basket').prefetch_related("ordered_items__product_info_id__shop_id").first()
        if order:
            if order.total_quantity != 0:
                contact = Contact.objects.filter(id=data['contact'], user_id=user_id).first()
                if not contact:
                    msg = f'Ваших контактов c id = {data["contact"]} не найдено.'
                    raise serializers.ValidationError(msg)

                for ordered_item in order.ordered_items.all():
                    if not ordered_item.product_info_id.is_active:
                        msg = f'Предложение по товару снято. (order_item с id = {ordered_item.id}).'
                        raise serializers.ValidationError(msg)
                    if not ordered_item.product_info_id.shop_id.is_active:
                        msg = f'Поставщик предложения по товару (order_item с id = {ordered_item.id}) приостановил приём заказов.'
                        raise serializers.ValidationError(msg)
                    if ordered_item.product_info_id.quantity < ordered_item.quantity:
                        msg = f'В заказе не может быть большего количества товара, чем есть у поставщика. {ordered_item.quantity} >' \
                              f' {ordered_item.product_info_id.quantity} (order_item с id = {ordered_item.id}).'
                        raise serializers.ValidationError(msg)

                # Метод validate должен возвращать словарь проверенных данных. Это
                # данные, которые передются в т.ч. в методы create и update.
                return {
                    'order': order,
                    'contact': contact
                }
        msg = f'Ваша корзина пуста.'
        raise serializers.ValidationError(msg)

    def create(self, validated_data):
        """
            Сначала изменяем количество предложений по каждому товару на величину заказа, а потом уже
            фиксируем заказ (order.status = 'new'), а не наоборот. Так как в этом случае, если что-то пойдёт не так
            (хоть и проверка по всем позициям уже прошла в def validate), заказ не разместиться и покупатель не заплатит
            за несуществующий товар (например).
        """
        for ordered_item in validated_data['order'].ordered_items.all():
            try:
                ordered_item.product_info_id.quantity -= ordered_item.quantity
                ordered_item.product_info_id.save()
            except Exception as e:
                if not ordered_item.product_info_id.is_active:
                    msg = f'Предложение по товару снято. (order_item с id = {ordered_item.id}).'
                    raise serializers.ValidationError(msg)
                if ordered_item.product_info_id.quantity < ordered_item.quantity:
                    msg = f'В заказе не может быть большего количества товара, чем есть у поставщика. {ordered_item.quantity} >' \
                          f' {ordered_item.product_info_id.quantity} (order_item с id = {ordered_item.id}).'
                    raise serializers.ValidationError(msg)
                raise serializers.ValidationError(e)

        order = validated_data['order']
        order.status = 'new'
        order.contact_id = validated_data['contact']
        order.save()
        return order

class PartnerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        exclude = ('user_id', 'is_active', 'id')

    def create(self, validated_data):
        return Contact.objects.create(user_id=self.context['request'].user, **validated_data)

class PartnerProductInfoSerializer(serializers.ModelSerializer):
    product = serializers.ReadOnlyField()
    offer_id = serializers.IntegerField(source='id') #переименовал поле id, чтобы было понятно из названия к чему он относится
    class Meta:
        model = ProductInfo
        fields = ('offer_id', 'external_id', 'product', 'product_id', 'model', 'price')

class PartnerOrderItemSerializer(serializers.ModelSerializer):
    product_info = PartnerProductInfoSerializer(read_only=True, source='product_info_id')
    class Meta:
        model = OrderItem
        fields = ('quantity', 'product_info')

class PartnerOrdersSerializer(serializers.ModelSerializer): #для просмотра поставщиком заказов с его товарами
    user_email = serializers.CharField(read_only=True, source='user_id.email')
    user_name = serializers.CharField(read_only=True, source='user_id.full_name')
    contact_info = PartnerContactSerializer(read_only=True, source='contact_id')
    status = serializers.CharField(read_only=True)
    our_ordered_items = PartnerOrderItemSerializer(read_only=True, many=True)
    class Meta:
        model = Order
        fields = ('id', 'status', 'user_email', 'user_name', 'created_at', 'updated_at', 'contact_info', 'our_ordered_items')


class PartnerStateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(choices=(('on', True), ('off', False)))
    class Meta:
        model = Shop
        fields = ('state',)

class PartnerUpdateSerializer(serializers.Serializer):
    url = serializers.URLField() #default allow_null=False
