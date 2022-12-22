from django.urls import path
from .views import LoginAPIView, RegistrationAPIView, UserRetrieveUpdateAPIView, UserPasswordResetAPIView,\
    UserPasswordResetConfirmAPIView, PartnerUpdateAPIView
urlpatterns = [
    path('user/register/', RegistrationAPIView.as_view()), #класс -> .as_view()
    path('user/login/', LoginAPIView.as_view()),
    path('user/details/', UserRetrieveUpdateAPIView.as_view()),
    path('user/password_reset/', UserPasswordResetAPIView.as_view()),
    path('user/password_reset/confirm/', UserPasswordResetConfirmAPIView.as_view()),
    path('partner/update/', PartnerUpdateAPIView.as_view()),


]