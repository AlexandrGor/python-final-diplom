#Cоздание собственного бекенда для поддержки JWT.
import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import User
from drf_spectacular.extensions import OpenApiAuthenticationExtension

class JWTAuthentication(authentication.BaseAuthentication):
    authentication_header_prefix = 'Token'

    class CustomTokenScheme(OpenApiAuthenticationExtension):
        target_class = "backend.customauth.JWTAuthentication"
        name = "CustomJWTAuth"

        def get_security_definition(self, auto_schema): #для drf-spectacular
            return {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Token-based authentication with required prefix 'Token'",
            }


    def authenticate(self, request):
        """
        Метод authenticate вызывается каждый раз, независимо от того, требует
        ли того эндпоинт аутентификации. 'authenticate' имеет два возможных
        возвращаемых значения:
            1) None - мы возвращаем None если не хотим аутентифицироваться.
            Обычно это означает, что мы значем, что аутентификация не удастся.
            Примером этого является, например, случай, когда токен не включен в
            заголовок.
            2) (user, token) - мы возвращаем комбинацию пользователь/токен
            тогда, когда аутентификация пройдена успешно. Если ни один из
            случаев не соблюден, это означает, что произошла ошибка, и мы
            ничего не возвращаем. В таком случае мы просто вызовем исключение
            AuthenticationFailed и позволим DRF сделать все остальное.
        """
        request.user = None
        #print('........................Кастомная JWT аутентификация для rest api........................')
        # 'auth_header' должен быть массивом с двумя элементами:
        # 1) именем заголовка аутентификации (Token в нашем случае)
        # 2) сам JWT, по которому мы должны пройти аутентифкацию
        auth_header = authentication.get_authorization_header(request).split()
        auth_header_prefix = self.authentication_header_prefix.lower()
        if not auth_header:
            return None

        if len(auth_header) == 1:
            # Некорректный заголовок токена, в заголовке передан один элемент
            return None

        elif len(auth_header) > 2:
            # Некорректный заголовок токена, какие-то лишние пробельные символы
            return None

        prefix = auth_header[0].decode('utf-8')
        token = auth_header[1].decode('utf-8')
        if prefix.lower() != auth_header_prefix:
            # Префикс заголовка не тот, который мы ожидали - отказ.
            return None

        # К настоящему моменту есть "шанс", что аутентификация пройдет успешно.
        # Мы делегируем фактическую аутентификацию учетных данных методу ниже.
        return self._authenticate_credentials(request, token)

    def _authenticate_credentials(self, request, token):
        """
        Попытка аутентификации с предоставленными данными. Если успешно -
        вернуть пользователя и токен, иначе - сгенерировать исключение.
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except Exception:
            #print('Ошибка аутентификации. Либо истёк срок токена, либо невозможно его декодировать.')
            msg = 'Ошибка аутентификации. Либо истёк срок токена, либо невозможно его декодировать.'
            raise exceptions.AuthenticationFailed(msg)

        if not str(payload['id']).isdigit():
            #print('Данный токен не для аутентификации.')
            msg = 'Данный токен не для аутентификации.'
            raise exceptions.AuthenticationFailed(msg)
        try:
            user = User.objects.get(pk=payload['id'])

        except User.DoesNotExist: #не обращаем внимания на warning в IDE, работает правильно
            #print('Пользователь соответствующий данному токену не найден.')
            msg = 'Пользователь соответствующий данному токену не найден.'
            raise exceptions.AuthenticationFailed(msg)

        if not user.is_active:
            #print('Данный пользователь деактивирован.')
            msg = 'Данный пользователь деактивирован.'
            raise exceptions.AuthenticationFailed(msg)

        if not user.email_confirmed:
            #print('Почта не подтверждена.')
            msg = 'Почта не подтверждена.'
            raise exceptions.AuthenticationFailed(msg)

        #print('...........................................OK............................................')
        return (user, token)