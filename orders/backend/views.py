from backend.models import *

from rest_framework import status, mixins
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import JsonResponse
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegistrationSerializer, UserSerializer, UserPasswordResetSerializer, \
    UserPasswordResetConfirmSerializer, ProductListSerializer, ProductInfoSerializer,\
    ProductInfoAllOffersSerializer, CategoriesSerializer, ShopsSerializer, OrderItemSerializer, OrderItemPUTSerializer,\
    ContactSerializer, OrderLiteSerializer, OrderSerializer, RegistrationConfirmSerializer, PartnerOrdersSerializer,\
    PartnerStateSerializer, PartnerUpdateSerializer

from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import PasswordResetForm, PasswordChangeForm, CustomUserCreationForm
from django.conf import settings
import jwt
import requests

from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from django_filters import rest_framework as filters
from rest_framework.filters import OrderingFilter
from .filters import ProductInfoListFilter, ProductInfoFilter, ProductFilter, PartnerOrdersFilter

from .ordering import ProductOrdering
from django.db.models import Prefetch
import json
import yaml

from .tasks import do_import, get_task, send_email #Celery tasks
from drf_spectacular.utils import extend_schema, inline_serializer

# Create your views here.
def index(request):
    #context = {"name":"Django", "version":django.VERSION}
    return render(request, 'index.html')

def AccountsRegistration(request):
    """
    Страница регистрации.
    """
    if request.method == 'GET':
        form = CustomUserCreationForm()
    elif request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()

            user = User.objects.get(email=form.cleaned_data['email'])
            msg = f'Токен для подтверждения регистрации по API:'
            msg += f'\n\n{user.token_email_confirm}\n\n'
            msg += f"Либо перейдите по ссылке:\n{request.scheme}://{request.META['HTTP_HOST']}/accounts/registration/confirm/?token={user.token_email_confirm}"
            try:
                send_mail(f'{user.email}', msg, settings.EMAIL_HOST_USER, [user.email])
            except BadHeaderError:
                return JsonResponse({'error': 'Ошибка в теме письма.'},
                                    status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS)

            return redirect('registration_done')
    else:
        return HttpResponse('Неверный запрос.')
    return render(request, "registration/registration.html", {'form': form})

def AccountsRegistrationConfirm(request):
    """
    Страница подтверждения регистрации.
    """
    token = request.GET.get('token', None)
    if token is None:
        return HttpResponse('В запросе для подтверждения почты нет параметра /?token=...')
    else:
        # декодировка токена
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except Exception:
            return HttpResponse('Ошибка аутентификации. Невозможно декодировать токен.')
        if payload['id'][-5:] != 'email':
            return HttpResponse('Токен верен, но не для подтверждения почты.')
        try:
            user = User.objects.get(pk=payload['id'][:-5])
        except User.DoesNotExist:  # не обращаем внимания на warning в IDE, работает правильно
            return HttpResponse('Пользователь соответствующий данному токену не найден.')
        if user.email_confirmed:
            return HttpResponse('Учетная запись пользователя уже подтверждена.')

        user.is_active = True
        user.email_confirmed = True
        user.save()

        return redirect('registration_complete')

def AccountsRegistrationDone(request):
    """
    Страница с сообщением отправки письма на почту для подтверждения регистрации.
    """
    return render(request, "registration/registration_done.html")

def AccountsRegistrationComplete(request):
    """
    Страница с сообщением об успешной регистрации (с подтверджденным по почте аккаунтом).
    """
    return render(request, "registration/registration_complete.html")

def AccountsPasswordReset(request):
    """
    Страница восстановления пароля.
    """
    # если метод GET, вернем форму
    if request.method == 'GET':
        form = PasswordResetForm()
    elif request.method == 'POST':
        # если метод POST, проверим форму и отправим письмо
        form = PasswordResetForm(request.POST)
        if form.is_valid(): #емайл введен верно, существует, а также is_active пользователя True
            user_email = form.cleaned_data['email']
            user_email = BaseUserManager.normalize_email(user_email)
            user = User.objects.get(email=user_email)
            token = user.token_password_reset
            msg = f'Токен для восстановления пароля {user_email} по API:'
            msg += f'\n\n{token}\n\n'
            msg += f"Либо перейдите по ссылке:\n{request.scheme}://{request.META['HTTP_HOST']}/accounts/password/reset/change/?token={token}"
            try:
                send_mail(f'{user_email}', msg, settings.EMAIL_HOST_USER, [user_email])
            except BadHeaderError:
                return HttpResponse('Ошибка в теме письма.')
            return redirect('password_reset_done')
    else:
        return HttpResponse('Неверный запрос.')
    return render(request, "registration/password_reset_form.html", {'form': form})

def AccountsPasswordResetDone(request):
    """
    Страница после отправки письма для изменения пароля на почту.
    """
    return render(request, 'registration/password_reset_done.html')

def AccountsPasswordResetChange(request):
    """
    Страница для подтверждения восстановления пароля по jwt-токену, а также для ввода нового пароля.
    """
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
        except User.DoesNotExist: #не обращаем внимания на warning в IDE, работает правильно
            return HttpResponse('Пользователь соответствующий данному токену не найден.')
        if not user.is_active:
            return HttpResponse('Данный пользователь деактивирован.')

        # если метод GET, вернем форму
        if request.method == 'GET':
            form = PasswordChangeForm()
        elif request.method == 'POST':
            # если метод POST, проверим форму, и изменим пароль
            form = PasswordChangeForm(request.POST)
            if form.is_valid():
                password = form.cleaned_data['password']
                user.set_password(password)
                user.save()
                return redirect('password_reset_complete')
        else:
            return HttpResponse('Неверный запрос.')
        return render(request, "registration/password_reset_change.html", {'form': form})

def AccountsPasswordResetComplete(request):
    """
    Страница с сообщением об успешном изменении пароля.
    """
    return render(request, 'registration/password_reset_complete.html')

class RegistrationAPIView(APIView):
    """
    Регистрация нового пользователя.
    """
    permission_classes = (AllowAny,) #Разрешить всем пользователям (аутентифицированным и нет) доступ к данному эндпоинту.
    serializer_class = RegistrationSerializer
    def post(self, request):
        """
        POST запрос ...api/v1/user/register/
        Письмо для подтверждения регистрации будет отправлено на указанный email.
        """
        data = request.data
        # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save() #user.email_confirmed = False

        user = User.objects.filter(email=data.get('email')).first()
        msg = f'Токен для подтверждения регистрации по API:'
        msg += f'\n\n{user.token_email_confirm}\n\n'
        task = send_email.delay(msg=msg, to=[user.email], header='Регистрация Netology homework')
        return JsonResponse({'status': f'Письмо для подтверждения будет отправлено на указанную почту. '
                                       f'Id задачи отправки письма: {task.id} '
                                       f'Для проверки задачи можете перейдите по ссылке: '
                                       f'{request.scheme}://{request.META["HTTP_HOST"]}/api/v1/task/{task.id}/ ',
                             'user': serializer.data}, status=status.HTTP_201_CREATED)

class RegistrationConfirmAPIView(APIView):
    """
    Подтверждение регистрации по jwt-токену, который был отправлен на почту.
    """
    permission_classes = (AllowAny,)
    serializer_class = RegistrationConfirmSerializer

    def post(self, request):
        """
        POST запрос ...api/v1/user/register/confirm/
        1. Декодировка указанного поля token.
        2. Определение id пользователя.
        3. Установление user.email_confirmed=True
        """
        data = request.data
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse({'status': 'Почта успешно подтверждена.'}, status=status.HTTP_200_OK)

class LoginAPIView(APIView):
    """
    Логин по email и password.
    """
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        """
        POST запрос ...api/v1/user/login/
        Получение jwt-токена по паре значений email и password для последующих авторизаций.
        """
        data = request.data
        # Не вызываем метод save() сериализатора, как
        # делали это для регистрации. Дело в том, что в данном случае нам
        # нечего сохранять. Вместо этого, метод validate() делает все нужное.
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

class UserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    """
    Класс для просмотра и изменения своего пользователя.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        GET запрос ...api/v1/user/details/
        Просмотр своего пользователя через авторизацию по токену.
        """
        # Здесь нечего валидировать или сохранять. Мы просто хотим, чтобы
        # сериализатор обрабатывал преобразования объекта User во что-то, что
        # можно привести к json и вернуть клиенту.
        serializer = self.serializer_class(request.user)

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        PATCH запрос ...api/v1/user/details/
        Изменение параметров пользователя. Авторизация по токену.
        """
        serializer_data = request.data

        # Паттерн сериализации, валидирования и сохранения
        serializer = self.serializer_class(
            request.user, data=serializer_data, partial=True #partial Частичные обновления
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

class UserPasswordResetAPIView(APIView):
    """
    Класс для восстановления пароля.
    """
    permission_classes = (AllowAny,)
    serializer_class = UserPasswordResetSerializer
    def post(self, request):
        """
        POST запрос ...api/v1/user/password/reset/
        Отправка письма с jwt-токеном на почту для подтверждения.
        """
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
        msg += f"Либо перейдите по ссылке:\n{request.scheme}://{request.META['HTTP_HOST']}/accounts/password/reset/change/?token={token}"
        task = send_email.delay(msg=msg, to=[user_email], header='Восстановление пароля Netology homework')
        return JsonResponse({'status': f'Письмо для восстановления пароля будет отправлено на указанную почту. '
                                       f'Id задачи отправки письма: {task.id} '
                                       f'Для проверки задачи можете перейдите по ссылке: '
                                       f'{request.scheme}://{request.META["HTTP_HOST"]}/api/v1/task/{task.id}/ ',
                             }, status=status.HTTP_200_OK)


class UserPasswordResetConfirmAPIView(APIView):
    """
    Класс для подтверждения восстановления пароля и указания нового.
    """
    permission_classes = (AllowAny,)
    serializer_class = UserPasswordResetConfirmSerializer
    def post(self, request):
        """
        POST запрос ...api/v1/user/password/reset/confirm/
        1. Указанному jwt-токен проходит декодирование.
        2. Определяется id пользователя.
        3. Пользователю с данным id устанавливается указанный password.
        """
        data = request.data
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse({'status': 'Пароль успешно обновлён.'}, status=status.HTTP_200_OK)



class PartnerUpdateAPIView(APIView):
    """
    Класс для:
    1. Обновления прайса от поставщика, получения id celery-задачи ...api/v1/partner/update/ POST.
    2. Получения статуса обновления прайса по id celery-задачи ...api/v1/partner/update/<task_id>/ GET.
    3. Удаления всего прайса ...api/v1/partner/update/ DELETE.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PartnerUpdateSerializer
    def post(self, request, *args, **kwargs):
        """
        POST запрос ...api/v1/partner/update/
        Обновление прайса от поставщика, получение id celery-задачи. Авторизация по токену.
        """
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = requests.get(serializer.data['url'] )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Whoops it wasn't a 200
            return JsonResponse({'Status': False, 'Error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        task = do_import.delay(response.text, request.user.email)
        return JsonResponse({'Status': f'Id задачи обновления прайса: {task.id} '
                                       f'Для проверки задачи сделайте аутентифицированный get запрос: '
                                       f'{request.scheme}://{request.META["HTTP_HOST"]}/api/v1/partner/update/{task.id}/ ',
                             }, status=status.HTTP_200_OK)

    def get(self, request, task_id, *args, **kwargs):
        """
        GET запрос ...api/v1/partner/update/<task_id>/
        Получение статуса обновления прайса по id celery-задачи. Авторизация по токену.
        """
        task_id = self.kwargs.get('task_id', None)
        if not task_id:
            return JsonResponse({'Status': False, 'Errors': f'Не указан id задачи ...api/v1/partner/update/<task_id>/'},
                                status=status.HTTP_400_BAD_REQUEST)
        task = get_task(task_id)
        if isinstance(task.result, tuple):
            if task.result[0] == request.user.email:
                return JsonResponse({'Status': task.status,
                                     'Result': task.result[1]}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'Status': False,
                                     'Error': 'Эта задача не от вашего имени.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return JsonResponse({'Status': task.status,
                                 'Result': task.result}, status=status.HTTP_200_OK)


    def delete(self, request, *args, **kwargs):
        """
        DELETE запрос ...api/v1/partner/update/
        Удаления всего прайса. Авторизация по токену.
        """
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)
        shop = Shop.objects.prefetch_related("product_info__product_id").filter(user_id__id=request.user.id).first()
        if not shop:
            return JsonResponse({'Status': 'Ваш магазин не найден.'}, status=status.HTTP_200_OK)
        old_offers = ProductInfo.objects.select_related('product_id').filter(shop_id=shop.id, is_active=True)

        if old_offers.first():
            result = old_offers.update(is_active=False)  # Отчистка всей базы-прайса магазина перед пересозданием
            for old_offer in old_offers:
                old_offer.product_id.check_actual()  # Если по продукту нет больше предложений, то product_obj.is_active = False
            return JsonResponse({'Status': f'Все предложения по товарам вашего магазина {shop.name} сняты. '
                                       f'(Количество снятых товаров: {result})'}, status=status.HTTP_200_OK)
        return JsonResponse({'Status': f'Ваш прайс уже пуст.'}, status=status.HTTP_200_OK)


class ProductInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Класс для:
    1. Вывода всей базы-прайса всех магазинов без привязки к одному продукту.
    Фильтрация (по параметрам: 'name', 'model', 'external_id', 'product_id', 'shop_id', 'shop', 'created_[after,before]',
    'updated_[after,before]', 'price_[min,max]', 'category', 'category_id').
    Т.е. в отличие от класса ProductViewSet можно выставить поиск, например, только для определённого магазина.
    Поставщик может видеть свои предложения (?shop_id=1)(?shop=связной),
    и контролировать остаток quantity по ним (?ordering=quantity).
    2. Просмотра предложения по его id ...api/v1/all_offers/<pk>/ GET
    """
    permission_classes = (AllowAny,)
    queryset = ProductInfo.objects.filter(is_active=True, shop_id__is_active=True)
    pagination_class = PageNumberPagination
    serializer_class = ProductInfoAllOffersSerializer
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductInfoListFilter
    ordering_fields = ['price', 'created_at', 'quantity', 'updated_at', 'external_id']
    ordering = ['-created_at']
    def list(self, request, *args, **kwargs):  #переопределение метода list для удаления повторяющихся продуктов при поиске
        """
        GET запрос ...api/v1/all_offers/
        Вывод предложений по всем товарам.
        """
        queryset = self.filter_queryset(self.get_queryset()).distinct() # .distinct() удаление повторяющихся продуктов при поиске
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.serializer_class(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.serializer_class(queryset, many=True)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

class ProductListViewSet(mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    Класс для:
    1. Просмотра всех товаров .../api/v1/products/ GET.
    Фильтрация (по параметрам: 'name', 'category', 'category_id', 'price_[min,max]', 'created_[after,before]',
    'updated_[after,before]', 'model', 'shop_id', 'shop').
    """
    permission_classes = (AllowAny,)
    queryset = Product.objects.filter(is_active=True).prefetch_related(
                                            Prefetch(
                                                "product_info",
                                                queryset=ProductInfo.objects.filter(is_active=True, shop_id__is_active=True),
                                                to_attr="actual_product_info",
                                            ),
                                        )
    pagination_class = PageNumberPagination
    serializer_class = ProductListSerializer
    filter_backends = [filters.DjangoFilterBackend, ProductOrdering] #custom ordering
    filterset_class = ProductFilter
    ordering_fields = ['name', 'category_id', 'price', 'created_at'], #price и created_at для сортировки по связанному ProductInfo
    ordering = ['-name']

    def list(self, request, *args, **kwargs):  #переопределение метода list для удаления повторяющихся продуктов при поиске
        """
        GET запрос .../api/v1/products/
        Просмотр всех товаров.
        """
        queryset = self.filter_queryset(self.get_queryset()).distinct() # .distinct() удаление повторяющихся продуктов при поиске
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.serializer_class(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.serializer_class(queryset, many=True)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)


class ProductViewSet(mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    Класс для:
    1. Просмотра всех предложений по определенному товару .../api/v1/products/<pk>/ GET.
    Фильтрация (по параметрам: 'created_[after,before]', 'updated_[after,before]', 'price_[min,max]',
    'external_id', 'shop_id', 'shop').
    """
    permission_classes = (AllowAny,)
    queryset = ProductInfo.objects.filter(is_active=True, shop_id__is_active=True)
    serializer_class = ProductInfoSerializer
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductInfoFilter
    ordering_fields = ['price', 'created_at'],
    ordering = ['-created_at']
    def list(self, request, *args, **kwargs):
        """
        GET запрос .../api/v1/products/<pk>/
        Просмотр предложений по конкретному товару.
        """
        pk=self.kwargs.get('pk')
        try:
            product = Product.objects.select_related("category_id").get(id=pk)
        except Product.DoesNotExist:
            return JsonResponse({'Status': False, 'Errors': f'Продукта с id = {pk} нет.'},
                                status=status.HTTP_400_BAD_REQUEST)
        if not product.is_active:
            return JsonResponse({'Status': False, 'Errors': f'По продукту с id = {pk} нет предложений.'},
                                status=status.HTTP_200_OK)
        queryset = self.filter_queryset(self.get_queryset().filter(product_id=pk)).distinct() # .distinct() удаление повторяющихся продуктов при поиске
        serializer = self.serializer_class(queryset, many=True)
        return JsonResponse({'id': product.id,
                             'name': product.name,
                             'category': product.category_id.name,
                             'category_id': product.category_id.id,
                             'product_info:': serializer.data
                             }, status=status.HTTP_200_OK)


class CategoriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Класс для:
    1. Просмотра всех категорий. .../api/v1/categories/ GET.
    2. Просмотра определенной категории. .../api/v1/categories/<pk>/ GET.
    """
    permission_classes = (AllowAny,)
    queryset = Category.objects.filter(is_active=True) #отображаем только is_active категории
    pagination_class = PageNumberPagination
    serializer_class = CategoriesSerializer
    ordering = ['-name']

class ShopsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Класс для:
    1. Просмотра всех магазинов. .../api/v1/shops/ GET.
    2. Просмотра определенного магазина. .../api/v1/shops/<pk>/ GET.
    """
    permission_classes = (AllowAny,)
    queryset = Shop.objects.filter(is_active=True) #отображаем только is_active магазины
    pagination_class = PageNumberPagination
    serializer_class = ShopsSerializer
    ordering = ['-name']

class OrderItemAPIView(APIView):
    """
    Класс для:
    1. Добавления товара в корзину .../api/v1/basket/  POST.
    2. Просмотра козины .../api/v1/basket/  GET.
    3. Редактирования количества товара в корзине .../api/v1/basket/  PUT.
    4. Удаления товара из корзины .../api/v1/basket/  DELETE.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderItemSerializer

    def post(self, request):
        """
        POST запрос .../api/v1/basket/
        Добавление товара в корзину. Авторизация по токену.
        {
            "items":[{ "product_info_id":  1,
                       "quantity": 1         }]
        }
        """
        items = request.data.get('items', None)
        if items:
            # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
            serializer = self.serializer_class(data=items, context = {'request':request}, many=True) #передача request для определения id пользователя
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            return JsonResponse({'Status': False, 'Errors': 'Не указано поле items'}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({'items': serializer.data}, status=status.HTTP_201_CREATED)

    def get(self, request):
        """
        GET запрос .../api/v1/basket/
        Просмотр корзины. Авторизация по токену.
        """
        queryset = OrderItem.objects.select_related('order_id__user_id', 'product_info_id').filter(
            order_id__user_id__id=request.user.id,
            order_id__status='basket')
        if queryset:
            serializer = self.serializer_class(queryset, many=True)
            return JsonResponse({'total_quantity': queryset[0].order_id.total_quantity,
                                 'cost_of_delivery': queryset[0].order_id.cost_of_delivery,
                                 'total_price': queryset[0].order_id.total_price,
                                 'items': serializer.data}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'Status': 'Ваша корзина в данный момент пуста.'}, status=status.HTTP_200_OK)

    def delete(self, request):
        """
        DELETE запрос .../api/v1/basket/
        Удаление товара из корзины. Авторизация по токену.
        items = '92,93,94'
        """
        items = request.data.get('items', None)# items = '92,93,94'
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указано поле items.'}, status=status.HTTP_400_BAD_REQUEST)
        items = items.split(",")
        queryset = OrderItem.objects.select_related('order_id__user_id').filter(
            order_id__user_id__id=request.user.id,
            order_id__status='basket')
        result = queryset.filter(id__in=items).delete()
        return JsonResponse({'Status': f'Успешно удалено позиций из корзины: {result[0]}'}, status=status.HTTP_200_OK)

    def put(self, request):
        """
        PUT запрос .../api/v1/basket/
        Редактирование количества товара в корзине. Авторизация по токену.
        {
            "items": [{"id": 39, "quantity": 2}]
        }
        """
        items = request.data.get('items', None)
        if items:
            # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
            serializer = OrderItemPUTSerializer(data=items, context={'request': request},
                                               many=True)  # передача request для определения id пользователя
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            return JsonResponse({'Status': False, 'Errors': 'Не указано поле items'})
        return JsonResponse({'items': serializer.data}, status=status.HTTP_200_OK)

class ContactAPIView(APIView):
    """
    Класс для:
    1. Создания контакта для аутентифицированного пользователя. .../api/v1/user/contact/ POST.
    2. Просмотра всех контактов аутентифицированного пользователя. .../api/v1/user/contact/ GET.
    3. Редактирования контакта пользователя с указанием id в body. .../api/v1/user/contact/ PATCH.
    4. Удаления контактов пользователя с указанием в items = 2,3,4 в body. .../api/v1/user/contact/ DELETE.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ContactSerializer

    def post(self, request):
        """
        POST запрос .../api/v1/user/contact/
        Создание контакта для аутентифицированного пользователя. Авторизация по токену.
        """
        # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
        serializer = self.serializer_class(data=request.data, context={'request': request}) # передача request для определения id пользователя
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):
        """
        GET запрос .../api/v1/user/contact/
        Создание контакта для пользователя. Авторизация по токену.
        """
        queryset = Contact.objects.filter(user_id__id=request.user.id, is_active=True)
        if queryset:
            serializer = self.serializer_class(queryset, many=True)
            return JsonResponse({'contacts': serializer.data}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'Status': 'У вас пока нет контактов.'}, status=status.HTTP_200_OK)

    def patch(self, request): #метод PUT не реализован. PUT создает ресурс, если он не существует. так как пользователь бы задавал id и для создания контакта, а id определяет БД (оно может быть занято). Либо в будущем можно добавить в БД ещё одно поле "красивых"(а не общих) id
        """
        PATCH запрос .../api/v1/user/contact/
        Редактирование контакта пользователя с указанием id в body. Авторизация по токену.
        """
        contact_id = request.data.get('id', None)
        if not contact_id:
            return JsonResponse({'Status': False, 'Errors': 'Не указано поле id.'}, status=status.HTTP_400_BAD_REQUEST)
        contact = Contact.objects.filter(user_id__id=request.user.id, id=contact_id, is_active=True).first()
        if not contact:
            return JsonResponse({'Status': False, 'Errors': f'Вашего контакта с id = {contact_id} не существует.'}, status=status.HTTP_400_BAD_REQUEST)
        # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
        serializer = self.serializer_class(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        """
        DELETE запрос .../api/v1/user/contact/
        Удаление контактов пользователя с указанием в items в body. Авторизация по токену.
        items = '2,3,4'
        """
        items = request.data.get('items', None) #items = '92,93,94'
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указано поле items.'})
        items = items.split(",")
        queryset = Contact.objects.filter(user_id__id=request.user.id, is_active=True)
        result = queryset.filter(id__in=items).update(is_active=False)
        return JsonResponse({'Status': f'Успешно удалено контактов: {result}'}, status=status.HTTP_200_OK)

class OrdersViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    """
    Класс для:
    1. Размещения заказа из корзины (смена статуса объекта Order с basket на new,
    корректировки quantity предложений на величины соответствующих позиций в заказе,
    отправки писем на email'ы покупателя и администратора). .../api/v1/orders/  POST.
    2. Просмотра определенного заказа по id .../api/v1/orders/<pk>/  GET.
    3. Просмотра всех сформированных заказов пользователя .../api/v1/orders/  GET.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer
    queryset = Order.objects.select_related('user_id', 'contact_id')

    def create(self, request, *args, **kwargs):
        """
        POST запрос .../api/v1/orders/
        Размещение заказа из корзины (смена статуса объекта Order с basket на new,
        корректировка quantity предложений на величины соответствующих позиций в заказе,
        отправка писем на email'ы покупателя и администратора).
        Авторизация по токену.
        """
        # Паттерн создания сериализатора, валидации и сохранения. Часто встречается.
        serializer = self.serializer_class(data=request.data, context = {'request':request}) #передача request для определения id пользователя
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Отправка письма покупателю
        user_email = request.user.email
        msg = f'Номер вашего заказа: {serializer.data["id"]}'
        msg += f'\nНаш оператор свяжется с вами в ближайшее время для уточнения делатей заказа\n'
        msg += f'Статуc заказов вы можете посмотреть в разделе "Заказы"\n'
        #msg += pprint.pformat({'order': serializer.data}, indent=4)
        msg += yaml.dump(json.loads(json.dumps({'order': serializer.data})), allow_unicode=True)  #сначала в json, из-за OrderedDict
        task1 = send_email.delay(msg=msg, to=[user_email], header='Спасибо за заказ Netology homework')
        # Отправка накладной администратору
        msg = f'Новый заказ {serializer.data["id"]}'
        msg += f'\nПокупатель {user_email} {request.user.full_name}\n'
        # msg += pprint.pformat({'order': serializer.data}, indent=4)
        msg += yaml.dump(json.loads(json.dumps({'order': serializer.data})), allow_unicode=True)  #сначала в json, из-за OrderedDict
        header = f'Новый заказ {serializer.data["id"]}'
        task2 = send_email.delay(msg=msg, to=settings.RECIPIENTS_EMAIL, header=header)
        return JsonResponse({'Status': f'Спасибо за заказ. На Вашу почту будет отправлено письмо. '                                       
                                       f'Наш оператор свяжется с вами в ближайшее время для уточнения делатей заказа. '
                                       f'Id задачи отправки письма покупателю: {task1.id} '
                                       f'Для проверки задачи можете перейдите по ссылке: '
                                       f'{request.scheme}://{request.META["HTTP_HOST"]}/api/v1/task/{task1.id}/ '
                                       f'Id задачи отправки письма менеджеру: {task2.id} '
                                       f'Для проверки задачи можете перейдите по ссылке: '
                                       f'{request.scheme}://{request.META["HTTP_HOST"]}/api/v1/task/{task2.id}/ ',
                             'order': serializer.data}, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """
        GET запрос .../api/v1/orders/
        Просмотр всех сформированных заказов пользователя. Авторизация по токену.
        """
        queryset = self.queryset.filter(user_id__id=request.user.id, status__in=['new',
                                                                                 'confirmed',
                                                                                 'assembled',
                                                                                 'sent',
                                                                                 'delivered',
                                                                                 'canceled',]) #без корзины
        if queryset:
            serializer = OrderLiteSerializer(queryset, many=True)
            return JsonResponse({'orders': serializer.data}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'Status': 'У вас пока нет заказов.'}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        GET запрос .../api/v1/orders/<pk>/
        Просмотра определенного заказа по id. Авторизация по токену.
        """
        order = self.queryset.filter(id=self.kwargs['pk'], user_id__id=request.user.id, status__in=['new',     #без корзины
                                                                                                    'confirmed',
                                                                                                    'assembled',
                                                                                                    'sent',
                                                                                                    'delivered',
                                                                                                    'canceled', ]).first()
        if order:
            serializer = self.serializer_class(order)
            return JsonResponse(serializer.data, status=status.HTTP_200_OK)
        return JsonResponse({'Status': f'У вас нет заказа c id = {self.kwargs["pk"]}.'}, status=status.HTTP_200_OK)

class PartnerOrdersViewSet(mixins.ListModelMixin,
                           viewsets.GenericViewSet):
    """
    Класс для просмотра поставщиком сформированных заказов с его товарами  .../api/v1/partner/orders/ GET.
    Фильтрация (по параметрам: 'id', 'user_email', 'status', 'created_[after,before]', 'updated_[after,before]',
    'phone', 'city', 'street', 'house', 'product', 'model')
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PartnerOrdersSerializer
    pagination_class = PageNumberPagination
    filterset_class = PartnerOrdersFilter
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['status', 'created_at', 'updated_at', 'id'],
    ordering = ['-updated_at']
    def list(self, request, *args, **kwargs):
        """
        GET запрос .../api/v1/partner/orders/ [ ?status=new ]
        Просмотр поставщиком сформированных заказов с его товарами. Авторизация по токену.
        """
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)
        shop = Shop.objects.filter(user_id__id=request.user.id).first()
        if not shop:
            return JsonResponse({'Status': 'Ваш магазин не найден.'}, status=status.HTTP_200_OK)
        queryset = Order.objects.filter(status__in=['new',
                                                    'confirmed',
                                                    'assembled',
                                                    'sent',
                                                    'delivered',
                                                    'canceled', ]
                                        ).prefetch_related(
                                            Prefetch(
                                                "ordered_items",
                                                queryset=OrderItem.objects.filter(product_info_id__shop_id__id=shop.id),
                                                to_attr="our_ordered_items",
                                            ), "ordered_items__product_info_id__product_id"
                                        ).select_related('user_id', 'contact_id')
        if not queryset:
            return JsonResponse({'Status': 'Пока заказов нет.'}, status=status.HTTP_200_OK)
        page = self.paginate_queryset(self.filter_queryset(queryset))
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK) #в ордерах отображаются товары только этого поставщика queryset.our_ordered_items


class PartnerStateAPIView(APIView):
    """
    Класс для:
    1. Включения и отключения приема заказов магазина поставщика .../api/v1/partner/state/ POST.
    2. Просмотра статуса отключения приема заказов магазина поставщика .../api/v1/partner/state/ GET.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PartnerStateSerializer
    def post(self, request, *args, **kwargs):
        """
        POST запрос .../api/v1/partner/state/
        Включение и отключение приема заказов магазина поставщика. Авторизация по токену.
        state = on [или off]
        """
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)
        shop = Shop.objects.prefetch_related("product_info__product_id").filter(user_id__id=request.user.id).first()
        if not shop:
            return JsonResponse({'Status': 'Ваш магазин не найден.'}, status=status.HTTP_200_OK)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.data['state'] == 'on':
            is_active_change = True
            msg = f'Приём заказов вашего магазина {shop.name} включен.'
        else:
            is_active_change = False
            msg = f'Приём заказов вашего магазина {shop.name} отключен.'
        if shop.is_active != is_active_change:
            shop.is_active = is_active_change
            shop.save()
            #обновление состояния is_active продуктов, связанных с этим магазином
            for offer in shop.product_info.all():
                offer.product_id.check_actual()
        return JsonResponse({'Status': msg}, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        """
        GET запрос .../api/v1/partner/state/
        Просмотр статуса отключения приема заказов магазина поставщика. Авторизация по токену.
        """
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)
        shop = Shop.objects.filter(user_id__id=request.user.id).first()
        if not shop:
            return JsonResponse({'Status': 'Ваш магазин не найден.'}, status=status.HTTP_200_OK)

        if shop.is_active:
            return JsonResponse({'Status': f'Приём заказов вашего магазина {shop.name} включен.'}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'Status': f'Приём заказов вашего магазина {shop.name} отключен.'}, status=status.HTTP_200_OK)

@extend_schema(responses=None)
class GetCeleryTaskAPIView(APIView):
    """
    Класс для:
    1. Получения статуса celery-задачи по id для неавторизованных пользователей ...api/v1/task/<task_id>/ GET.
    Например, для проверки статуса отправки письма подтверждения при регистрации, или при восстановлении пароля
    """
    permission_classes = (AllowAny,)
    def get(self, request, task_id, *args, **kwargs):
        """
        Класс для:
        GET запрос ...api/v1/task/<task_id>/
        Получения статуса celery-задачи по id.
        """
        task_id = self.kwargs.get('task_id', None)
        if not task_id:
            return JsonResponse({'Status': False, 'Errors': f'Не указан id задачи ...api/v1/partner/update/<task_id>/'},
                                status=status.HTTP_400_BAD_REQUEST)
        task = get_task(task_id)
        if isinstance(task.result, tuple):
            if task.result[0] == 'allow any':
                return JsonResponse({'Status': task.status,
                                     'Result': task.result[1]}, status=status.HTTP_200_OK)
            else:
                # на случай если введен id задачи обновления прайса магазина, только магазин имеет доступ к результату
                return JsonResponse({'Status': False,
                                     'Error': 'Результат недоступен для неавторизованных пользователей.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return JsonResponse({'Status': task.status,
                                 'Result': task.result}, status=status.HTTP_200_OK)

