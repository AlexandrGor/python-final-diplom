from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User

# Register your models here.
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ('email', 'first_name', 'last_name', 'company', 'is_staff', 'is_active', 'type', )
    list_filter = ('email', 'first_name', 'last_name', 'company', 'is_staff', 'is_active', 'type', )
    fieldsets = (
        (None, {'fields': ('email', 'password', 'first_name', 'last_name', 'middle_name',
                           'company', 'position', 'type')}),
        ('Permissions', {'fields': ('is_staff', 'is_active')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active',
                       'first_name', 'last_name', 'middle_name', 'company', 'position', 'type')}
        ),
    )
    search_fields = ('email','first_name', 'last_name', 'company',)
    ordering = ('email','first_name', 'last_name', 'company',)

admin.site.register(User, CustomUserAdmin)