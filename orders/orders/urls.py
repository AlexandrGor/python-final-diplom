"""orders URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from backend.views import index, AccountsPasswordReset, AccountsPasswordResetDone, AccountsPasswordResetChange,\
    AccountsPasswordResetComplete, AccountsRegistration, AccountsRegistrationDone, AccountsRegistrationConfirm,\
    AccountsRegistrationComplete
from django.contrib.auth import views as django_auth_views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from allauth.socialaccount.providers.vk import views as vk_views

urlapischeme = [
    # YOUR PATTERNS
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

urlpatterns = [ #the patterns are tested in order. Feel free to exploit the ordering to insert special cases
    path('', index, name='index'),
    path('api/v1/', include('backend.urls')),
    path('admin/', admin.site.urls), #admin:index
    path('accounts/registration/', AccountsRegistration, name='registration'), #надо бы всё это в отдельное приложение
    path('accounts/registration/done/', AccountsRegistrationDone, name='registration_done'),
    path('accounts/registration/confirm/', AccountsRegistrationConfirm, name='registration_confirm'),
    path('accounts/registration/complete/', AccountsRegistrationComplete, name='registration_complete'),
    path('accounts/login/', django_auth_views.LoginView.as_view(), name='login'),  # стандартная аутентификация джанго для фронтенда через сессии, пока без выдачи токена JWT #к тому же пока не реализован refresh-токен
    path('accounts/logout/', django_auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password/reset/', AccountsPasswordReset, name='password_reset'),
    path('accounts/password/reset/done/', AccountsPasswordResetDone, name='password_reset_done'),
    path('accounts/password/reset/change/', AccountsPasswordResetChange, name='password_reset_change'),
    path('accounts/password/reset/complete/', AccountsPasswordResetComplete, name='password_reset_complete'),
    path('accounts/vk/login/', vk_views.oauth2_login, name='vk_login'),
    path('accounts/vk/login/callback/', vk_views.oauth2_callback, name='vk_callback'),
    path('accounts/', include('allauth.urls')),
] + urlapischeme


