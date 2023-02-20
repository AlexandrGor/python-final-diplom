import pytest
from rest_framework.test import APIClient
from backend.models import *
from model_bakery import baker
from django.core import mail

@pytest.fixture #для того, чтобы можно было указывать в качестве входящего аргумента в тестирущих функциях, сокращая тем дублирующийся код, например строчку client = APIClient()
def client():
    return APIClient(HTTP_HOST='localhost') #The HTTP_HOST header is not set by the Django test client by default.

@pytest.fixture
def user():
    return User.objects.create_user(email='test@test.ru', password='testtest', email_confirmed=True, is_active=True)

@pytest.fixture
def products_factory():
    def factory(*args, **kwargs):
        return baker.make(Product, *args, **kwargs)
    return factory

@pytest.mark.django_db #It will ensure the database is set up correctly for the test. Each test will run in its own transaction which will be rolled back at the end of the test.
def test_get_products(client, products_factory):
    #Arrange
    products = products_factory(_quantity=10, is_active=True)
    products.sort(key=lambda x: x.name) #одинаковая сортировка с data response
    #Act
    response = client.get('/api/v1/products/')
    #Assert
    assert response.status_code == 200
    data = response.json()['results'] #paginaton 'PAGE_SIZE': 20
    assert len(data) == len(products)
    data.sort(key=lambda x: x['name']) #одинаковая сортировка с products_factory
    for i, m in enumerate(data):
        assert m['name'] == products[i].name

@pytest.mark.django_db
def test_registration(client):
    # Arrange
    count = User.objects.count()
    # Act
    responce = client.post('/api/v1/user/register/', data={'email': 'test@test.ru', 'password': 'testtest'})
    # Assert
    assert responce.status_code == 201
    assert User.objects.count() == count + 1
    #assert len(mail.outbox) == 1 #не работает, =0, так как celery отправляет письмо из отдельного котнейнера

@pytest.mark.django_db
def test_registration_confirm(client):
    # Arrange
    user = User.objects.create_user(email='test@test.ru', password='testtest')
    # Act
    responce = client.post('/api/v1/user/register/confirm/', data={'token': user.token_email_confirm})
    # Assert
    assert responce.status_code == 200
    user = User.objects.get(email=user.email)
    assert user.email_confirmed == True
    assert user.is_active == True


@pytest.mark.django_db
def test_login(client, user):
    # Arrange
    # Act
    responce = client.post('/api/v1/user/login/', data={'email': 'test@test.ru', 'password': 'testtest'})
    # Assert
    assert responce.status_code == 200
    token = responce.json()['token']
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    assert payload['id'] == user.id

@pytest.mark.django_db
def test_get_user(client, user):
    # Arrange
    client.credentials(HTTP_AUTHORIZATION='Token ' + user.token)
    # Act
    responce = client.get('/api/v1/user/details/')
    # Assert
    assert responce.status_code == 200
    assert responce.json()['email'] == user.email