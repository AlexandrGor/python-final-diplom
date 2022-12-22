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

from backend.views import index, AccountsPasswordReset, AccountsPasswordResetDone, AccountsPasswordResetChange, AccountsPasswordResetComplete
from django.contrib.auth import views as django_auth_views
urlpatterns = [
    path('', index, name='index'),
    path('api/v1/', include('backend.urls')),
    path('admin/', admin.site.urls), #admin:index
    #path('accounts/registration/', Registration, name='registration'), #пока без формы регистрации
    path('accounts/login/', django_auth_views.LoginView.as_view(), name='login'), #стандартная аутентификация джанго для фронтенда через сессии, пока без выдачи токена JWT #к тому же пока не реализован refresh-токен
    path('accounts/logout/', django_auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_reset/', AccountsPasswordReset, name='password_reset'), #надо бы всё это в отдельное приложение
    path('accounts/password_reset/done/', AccountsPasswordResetDone, name='password_reset_done'),
    path('accounts/password_reset/change/', AccountsPasswordResetChange, name='password_reset_change'),
    path('accounts/password_reset/complete/', AccountsPasswordResetComplete, name='password_reset_complete'),

]

