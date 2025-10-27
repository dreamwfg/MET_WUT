from django.contrib import admin
from users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'first_name', 'last_name', 'username', 'email',
        'phone', 'passport_id', 'is_bachelor', 'is_active', 'is_staff'
    )
    search_fields = ('first_name', 'last_name', 'username', 'email', 'phone', 'passport_id')
    ordering = ('-id',)
    list_filter = ('is_staff', 'is_superuser', 'is_bachelor', 'is_active')




