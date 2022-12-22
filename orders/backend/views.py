from backend.models import *

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import JsonResponse
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegistrationSerializer, UserSerializer, UserPasswordReset, UserPasswordResetConfirm

from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from .forms import FormPasswordReset, FormPasswordChange
from django.conf import settings

import jwt

import yaml
import requests
# Create your views here.
def index(request):
    #context = {"name":"Django", "version":django.VERSION}
    return render(request, 'index.html')

def AccountsPasswordReset(request):
    # если метод GET, вернем форму
    if request.method == 'GET':
        form = FormPasswordReset()
    elif request.method == 'POST':
        # если метод POST, проверим форму и отправим письмо
        form = FormPasswordReset(request.POST)
        if form.is_valid(): #емайл введен верно, существует, а также is_active пользователя True
            user_email = form.cleaned_data['email']
            user_email = BaseUserManager.normalize_email(user_email)
            user = User.objects.get(email=user_email)
            token = user.token_password_reset
            msg = f'Токен для восстановления пароля {user_email} по API:'
            msg += f'\n\n{token}\n\n'
            msg += f"Либо перейдите по ссылке:\n{request.scheme}://{request.META['HTTP_HOST']}/accounts/password_reset/change/?token={token}"
            try:
                send_mail(f'{user_email}', msg, settings.DEFAULT_FROM_EMAIL, [user_email])
            except BadHeaderError:
                return HttpResponse('Ошибка в теме письма.')
            return redirect('password_reset_done')
    else:
        return HttpResponse('Неверный запрос.')
    return render(request, "registration/password_reset_form.html", {'form': form})

def AccountsPasswordResetDone(request):
    return render(request, 'registration/password_reset_done.html')

def AccountsPasswordResetChange(request):
    token = request.GET.get('token', None)
    if token is None:
        return HttpResponse('В запросе для изменения пароля нет параметра /?token=...')
    else:
        #декодировка токена
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except Exception:
            return HttpResponse('Ошибка аутентификации. Невозможно декодировать токен')
        if payload['id'][-5:] != 'reset':
            return HttpResponse('Токен верен, но не для восстановления пароля')
        try:
            user = User.objects.get(pk=payload['id'][:-5])
            #...здесь также можно добавить проверку времени жизни токена...#
        except User.DoesNotExist: #не обращаем внимания на warning в IDE, работает правильно
            return HttpResponse('Пользователь соответствующий данному токену не найден.')
        if not user.is_active:
            return HttpResponse('Данный пользователь деактивирован.')

        # если метод GET, вернем форму
        if request.method == 'GET':
            form = FormPasswordChange()
        elif request.method == 'POST':
            # если метод POST, проверим форму, и изменим пароль
            form = FormPasswordChange(request.POST)
            if form.is_valid():
                password = form.cleaned_data['password']
                user.set_password(password)
                user.save()
                return redirect('password_reset_complete')
        else:
            return HttpResponse('Неверный запрос.')
        return render(request, "registration/password_reset_change.html", {'form': form})

def AccountsPasswordResetComplete(request):
    return render(request, 'registration/password_reset_complete.html')
class RegistrationAPIView(APIView):
    """
    Разрешить всем пользователям (аутентифицированным и нет) доступ к данному эндпоинту.
    """
    permission_classes = (AllowAny,)
    serializer_class = RegistrationSerializer
    def post(self, request):
        data = request.data
        # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        data = request.data
        # Не вызываем метод save() сериализатора, как
        # делали это для регистрации. Дело в том, что в данном случае нам
        # нечего сохранять. Вместо этого, метод validate() делает все нужное.
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

class UserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def retrieve(self, request, *args, **kwargs):
        # Здесь нечего валидировать или сохранять. Мы просто хотим, чтобы
        # сериализатор обрабатывал преобразования объекта User во что-то, что
        # можно привести к json и вернуть клиенту.
        serializer = self.serializer_class(request.user)

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        serializer_data = request.data

        # Паттерн сериализации, валидирования и сохранения
        serializer = self.serializer_class(
            request.user, data=serializer_data, partial=True #request.user этот экземпляр класса определяеся благодаря permission_classes = (IsAuthenticated,)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

class UserPasswordResetAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = UserPasswordReset
    def post(self, request):
        data = request.data
        # Не вызываем метод save() сериализатора, как
        # делали это для регистрации. Дело в том, что в данном случае нам
        # нечего сохранять. Вместо этого, метод validate() делает все нужное.
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        user_email=serializer.data["email"]
        token=serializer.data["token"]
        msg = f'Токен для восстановления пароля {user_email} по API:'
        msg += f'\n\n{token}\n\n'
        msg += f"Либо перейдите по ссылке:\n{request.scheme}://{request.META['HTTP_HOST']}/accounts/password_reset/change/?token={token}"
        try:
            send_mail(f'{user_email}', msg, settings.DEFAULT_FROM_EMAIL, [user_email])
        except BadHeaderError:
            return JsonResponse({'error': 'Ошибка в теме письма.'}, status=451)


        return JsonResponse({'status': 'Письмо для восстановления пароля успешно отправлено на указанную почту.'}, status=status.HTTP_200_OK)


class UserPasswordResetConfirmAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = UserPasswordResetConfirm
    def post(self, request):
        data = request.data
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse({'status': 'Пароль успешно обновлён.'}, status=status.HTTP_200_OK)



class PartnerUpdateAPIView(APIView):
    """
    Класс для обновления прайса от поставщика
    """
    permission_classes = (IsAuthenticated,)
    def post(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                response = requests.get(url)
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    # Whoops it wasn't a 200
                    return JsonResponse({'Status': False, 'Error': str(e)})
                data = yaml.safe_load(response.text)
                try:
                    #созданём магазин пользователя, если не было
                    shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user) #shop необходимое unique значение, иначе KeyError. shop <-> user отношение 1к1, тем самым пользователь может создать или изменить только один свой магазин.
                    #созданём категории магазина, если таких не было
                    for category in data['categories']: #categories необходимое значение, иначе KeyError.
                        category_object, _ = Category.objects.get_or_create(
                            name=category['name'], #name необходимое unique значение, иначе KeyError
                            defaults={'id': category.get('id')} #так как name сам по себе уникален, в передаче id нет большого смысла. Если такой категории не существует, defaults создаст её с указанным id (если id в этом случае не указано, то category.get('id') вернет None)
                        )
                        category_object.save() #You can’t associate it until it’s been saved
                        category_object.shops.add(shop) #Adding a second time is OK, it will not duplicate the relation
                    ProductInfo.objects.filter(shop_id=shop.id).delete() #Отчистка всей базы-прайса магазина перед пересозданием
                    for item in data['goods']: #goods необходимое значение, иначе KeyError. Нет смысла указывать только категории магазина, если в них нет продуктов.
                        #созданём продукты, если таких не было
                        product, _ = Product.objects.get_or_create(name=item['name'], category_id=Category(id=item['category'])) #name и category необходимые значение, иначе KeyError.     category_id= требует не id а instance https://code.djangoproject.com/ticket/13915
                        #созданём базу-прайс магазина
                        product_info = ProductInfo.objects.create(product_id=product, #требуется не id, а instance https://code.djangoproject.com/ticket/13915
                                                                  external_id=item['id'], #blank=False необходимое значение, иначе KeyError
                                                                  model=item.get('model'),#blank=True  default=None
                                                                  price=item['price'],#blank=False необходимое значение, иначе KeyError
                                                                  price_rrc=item['price_rrc'], #blank=False необходимое значение, иначе KeyError
                                                                  quantity=item['quantity'], #blank=False необходимое значение, иначе KeyError
                                                                  shop_id=shop)
                        if item.get('parameters'): #делаем возможность не указывать параметры продукта
                            for name, value in item['parameters'].items():
                                parameter_object, _ = Parameter.objects.get_or_create(name=name) #созданём тип параметра, если в базе такого нет
                                ProductParameter.objects.create(product_info_id=product_info,
                                                                parameter_id=parameter_object,
                                                                value=value) #value необходимое значение, иначе KeyError
                    return JsonResponse({'Status': True})
                except (KeyError, Exception) as e:
                    return JsonResponse({'Status': False, 'Error': str(e)})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})
