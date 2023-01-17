from django.urls import path, include
from .views import LoginAPIView, RegistrationAPIView, RegistrationConfirmAPIView, UserRetrieveUpdateAPIView, UserPasswordResetAPIView,\
    UserPasswordResetConfirmAPIView, PartnerUpdateAPIView, OrderItemAPIView, PartnerOrdersViewSet, PartnerStateAPIView
from rest_framework.routers import DefaultRouter
from .views import ProductInfoViewSet, ProductViewSet, ProductListViewSet, CategoriesViewSet, ShopsViewSet, OrdersViewSet, ContactAPIView

router = DefaultRouter()
router.register('all_offers', ProductInfoViewSet) #вывод всей базы-прайса всех магазинов без привязки к одному продукту
router.register('products', ProductViewSet)
router.register('categories', CategoriesViewSet)
router.register('shops', ShopsViewSet)
router.register('orders', OrdersViewSet)

urlpatterns = [
    path('user/register/', RegistrationAPIView.as_view()),
    path('user/register/confirm/', RegistrationConfirmAPIView.as_view()),
    path('user/login/', LoginAPIView.as_view()),
    path('user/details/', UserRetrieveUpdateAPIView.as_view()),
    path('user/contact/', ContactAPIView.as_view()),
    path('user/password/reset/', UserPasswordResetAPIView.as_view()),
    path('user/password/reset/confirm/', UserPasswordResetConfirmAPIView.as_view()),
    path('products/', ProductListViewSet.as_view({'get': 'list'})),
    path('products/<int:pk>/', ProductViewSet.as_view({'get': 'list'})),
    path('partner/update/', PartnerUpdateAPIView.as_view()),
    path('partner/orders/', PartnerOrdersViewSet.as_view({'get': 'list'})),
    path('partner/state/', PartnerStateAPIView.as_view()),
    path('basket/', OrderItemAPIView.as_view()),
] + router.urls
