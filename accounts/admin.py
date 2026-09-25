from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    Institution, InstitutionMembership, User, UserProfile, Permission, Role,
    UserRole, AuditLog
)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'institution_type', 'country', 'province', 'district', 'is_active')
    list_filter = ('institution_type', 'country', 'province', 'is_active')
    search_fields = ('name', 'code', 'email', 'phone_number', 'district')
    list_editable = ('is_active',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InstitutionMembership)
class InstitutionMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'role', 'is_active', 'assigned_by', 'created_at')
    list_filter = ('role', 'is_active', 'institution', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'institution__name', 'institution__code')
    raw_id_fields = ('institution', 'user', 'assigned_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'is_active', 'is_verified', 'created_at')
    list_filter = ('user_type', 'is_active', 'is_verified', 'two_factor_enabled', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'profile_picture')}),
        (_('Account Type'), {'fields': ('user_type',)}),
        (_('Security'), {'fields': ('two_factor_enabled', 'two_factor_secret')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'email_verified_at', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'email_verified_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'emergency_contact_name', 'emergency_contact_phone', 'language_preference', 'timezone')
    list_filter = ('language_preference', 'timezone', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'emergency_contact_name')
    raw_id_fields = ('user',)
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Emergency Contact'), {'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship')}),
        (_('Preferences'), {'fields': ('language_preference', 'timezone', 'notification_preferences')}),
        (_('Additional Info'), {'fields': ('bio', 'skills', 'certifications')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'description')
    search_fields = ('name', 'codename', 'description')
    ordering = ('name',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    
    fieldsets = (
        (None, {'fields': ('name', 'description', 'is_active')}),
        (_('Permissions'), {'fields': ('permissions',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_by', 'assigned_at', 'is_active')
    list_filter = ('role', 'is_active', 'assigned_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'role__name')
    raw_id_fields = ('user', 'role', 'assigned_by')
    
    fieldsets = (
        (None, {'fields': ('user', 'role', 'is_active')}),
        (_('Assignment'), {'fields': ('assigned_by', 'assigned_at')}),
    )
    
    readonly_fields = ('assigned_at',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'ip_address', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'model_name', 'object_id')
    raw_id_fields = ('user',)
    
    fieldsets = (
        (None, {'fields': ('user', 'action', 'model_name', 'object_id')}),
        (_('Details'), {'fields': ('details',)}),
        (_('Request Info'), {'fields': ('ip_address', 'user_agent')}),
        (_('Timestamp'), {'fields': ('timestamp',)}),
    )
    
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
