from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Role, User, UserRole


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('role_id', 'name', 'status', 'description')
    list_filter = ('status',)
    search_fields = ('name',)


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    fields = ('role', 'status', 'assigned_at_utc')
    readonly_fields = ('assigned_at_utc',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'institution', 'status', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('status', 'is_staff', 'institution')
    inlines = [UserRoleInline]

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'second_last_name', 'email', 'institution')}),
        ('Status & Permissions', {'fields': ('status', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'created_at_utc')}),
    )
    readonly_fields = ('created_at_utc', 'last_login')
