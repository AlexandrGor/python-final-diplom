from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
from django.conf import settings
import jwt



class RegistrationSerializer(serializers.ModelSerializer):
    """ Сериализация регистрации пользователя и создания нового. """

    # Убедитесь, что пароль содержит не менее 8 символов, не более 128,
    # и так же что он не может быть прочитан клиентской стороной
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )
    is_active = serializers.BooleanField(default=True)
    #is_staff = serializers.BooleanField(default=False)

    class Meta:
        model = User
        # Перечислить все поля, которые могут быть включены в запрос
        # или ответ, включая поля, явно указанные выше.
        fields = ['email', 'password', 'first_name', 'middle_name', 'last_name', 'company', 'position',
                  'type', 'is_active'] #пока без 'is_staff'

    def create(self, validated_data):
        # Использовать метод create_user для создания нового пользователя.
        return User.objects.create_user(**validated_data)



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )
    # Клиентская сторона не должна иметь возможность отправлять токен вместе с
    # запросом на регистрацию. Сделаем его доступным только на чтение.
    token = serializers.CharField(max_length=255, read_only=True)

    def validate(self, data):
        # В методе validate мы убеждаемся, что текущий экземпляр
        # LoginSerializer значение valid. В случае входа пользователя в систему
        # это означает подтверждение того, что присутствуют адрес электронной
        # почты и то, что эта комбинация соответствует одному из пользователей.
        email = data.get('email', None)
        password = data.get('password', None)

        # Вызвать исключение, если не предоставлена почта.
        if email is None:
            raise serializers.ValidationError(
                'An email address is required to log in.'
            )

        # Вызвать исключение, если не предоставлен пароль.
        if password is None:
            raise serializers.ValidationError(
                'A password is required to log in.'
            )

        # Метод authenticate предоставляется Django и выполняет проверку, что
        # предоставленные почта и пароль соответствуют какому-то пользователю в
        # нашей базе данных. Мы передаем email как username, так как в модели
        # пользователя USERNAME_FIELD = email.
        user = authenticate(username=email, password=password) #стандартная django аутентификация по логину и паролю

        # Если пользователь с данными почтой/паролем не найден, то authenticate
        # вернет None. Возбудить исключение в таком случае.
        if user is None:
            raise serializers.ValidationError(
                'A user with this email and password was not found.'
            )

        # Django предоставляет флаг is_active для модели User. Его цель
        # сообщить, был ли пользователь деактивирован или заблокирован.
        # Проверить стоит, вызвать исключение в случае True.
        if not user.is_active:
            raise serializers.ValidationError(
                'This user has been deactivated.'
            )

        # Метод validate должен возвращать словать проверенных данных. Это
        # данные, которые передются в т.ч. в методы create и update.
        return {
            'email': user.email,
            'token': user.token
        }


class UserSerializer(serializers.ModelSerializer):
    """ Ощуществляет сериализацию и десериализацию объектов User. """

    # Пароль должен содержать от 8 до 128 символов. Это стандартное правило. Мы
    # могли бы переопределить это по-своему, но это создаст лишнюю работу для
    # нас, не добавляя реальных преимуществ, потому оставим все как есть.
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True
    )

    class Meta:
        model = User
        fields = ('email', 'password', 'token', 'is_active',
                  'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')

        # Параметр read_only_fields является альтернативой явному указанию поля
        # с помощью read_only = True, как мы это делали для пароля выше.
        # Причина, по которой мы хотим использовать здесь 'read_only_fields'
        # состоит в том, что нам не нужно ничего указывать о поле. В поле
        # пароля требуются свойства min_length и max_length,
        # но это не относится к полю токена.
        read_only_fields = ('token',)

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

class UserPasswordReset(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    token = serializers.CharField(max_length=255, read_only=True)
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

class UserPasswordResetConfirm(serializers.Serializer):
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
            # ...здесь также можно добавить проверку времени жизни токена...#
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