from rest_framework import permissions
from django.contrib.auth.mixins import UserPassesTestMixin

from .models import InstitutionMembership


ADMIN_ROLES = {
    InstitutionMembership.MembershipRole.OWNER,
    InstitutionMembership.MembershipRole.ADMINISTRATOR,
}

STAFF_WRITE_ROLES = {
    InstitutionMembership.MembershipRole.OWNER,
    InstitutionMembership.MembershipRole.ADMINISTRATOR,
    InstitutionMembership.MembershipRole.TEACHER,
}

FINANCE_WRITE_ROLES = {
    InstitutionMembership.MembershipRole.OWNER,
    InstitutionMembership.MembershipRole.ADMINISTRATOR,
    InstitutionMembership.MembershipRole.ACCOUNTANT,
}


def is_platform_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, 'user_type', None) == 'super_admin')
    )


def user_type(user):
    return getattr(user, 'user_type', None)


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (
            is_platform_admin(user)
            or user_type(user) == 'administrator'
            or has_membership_role(user, ADMIN_ROLES)
        )
    )


def is_accountant_user(user):
    return bool(
        user
        and user.is_authenticated
        and (
            is_admin_user(user)
            or user_type(user) == 'accountant'
            or has_membership_role(user, FINANCE_WRITE_ROLES)
        )
    )


def is_teacher_user(user):
    return bool(user and user.is_authenticated and user_type(user) == 'teacher')


def is_student_user(user):
    return bool(user and user.is_authenticated and user_type(user) == 'student')


def is_parent_user(user):
    return bool(user and user.is_authenticated and user_type(user) == 'parent')


def is_academic_staff_user(user):
    return bool(
        user
        and user.is_authenticated
        and (
            is_admin_user(user)
            or is_teacher_user(user)
            or has_membership_role(user, STAFF_WRITE_ROLES)
        )
    )


class RoleRequiredMixin(UserPassesTestMixin):
    allowed_user_types = ()
    allow_platform_admin = True
    allow_staff_flag = False

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if self.allow_platform_admin and is_platform_admin(user):
            return True
        if self.allow_staff_flag and user.is_staff:
            return True
        return user_type(user) in self.allowed_user_types


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_user_types = ('administrator',)


class FinanceRequiredMixin(RoleRequiredMixin):
    allowed_user_types = ('administrator', 'accountant')


class FinanceSelfServiceRequiredMixin(RoleRequiredMixin):
    allowed_user_types = ('administrator', 'accountant', 'student', 'parent')


class AcademicStaffRequiredMixin(RoleRequiredMixin):
    allowed_user_types = ('administrator', 'teacher')


class AdminOrAcademicStaffRequiredMixin(RoleRequiredMixin):
    allowed_user_types = ('administrator', 'teacher')


def active_memberships(user):
    if not user or not user.is_authenticated:
        return InstitutionMembership.objects.none()
    return InstitutionMembership.objects.filter(
        user=user,
        is_active=True,
        institution__is_active=True,
    )


def user_institution_ids(user):
    if is_platform_admin(user):
        return None
    return list(active_memberships(user).values_list('institution_id', flat=True))


def user_can_access_institution(user, institution_id):
    if is_platform_admin(user):
        return True
    if institution_id is None:
        return False
    return active_memberships(user).filter(institution_id=institution_id).exists()


def has_institution_admin_role(user):
    if is_platform_admin(user):
        return True
    return active_memberships(user).filter(role__in=ADMIN_ROLES).exists()


def has_membership_role_for_institution(user, institution_id, roles):
    if is_platform_admin(user):
        return True
    if institution_id is None:
        return False
    return active_memberships(user).filter(
        institution_id=institution_id,
        role__in=roles,
    ).exists()


def has_membership_role(user, roles):
    if is_platform_admin(user):
        return True
    return active_memberships(user).filter(role__in=roles).exists()


class IsPlatformOrInstitutionAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_institution_admin_role(request.user)


class IsInstitutionTeacherOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_membership_role(request.user, STAFF_WRITE_ROLES)


class IsInstitutionAccountantOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_membership_role(request.user, FINANCE_WRITE_ROLES)


class IsMaterialMaintainer(permissions.BasePermission):
    """Read for any signed-in user; write only for admins and teachers.

    Learning material is read-only for everyone else.
    """

    message = 'Only administrators and teachers can change learning material.'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        if not request.user or not request.user.is_authenticated:
            return False
        return is_admin_user(request.user) or is_teacher_user(request.user)


class IsSubmissionOwnerOrAdmin(permissions.BasePermission):
    """Only the submitting student (or an admin) may change a submission."""

    message = 'You can only change your own submission.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_platform_admin(user) or is_admin_user(user):
            return True
        return getattr(getattr(obj, 'student', None), 'user_id', None) == user.id


class IsSelfServiceOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class InstitutionScopedQuerysetMixin:
    institution_lookup = None
    admin_only_actions = {'create', 'update', 'partial_update', 'destroy'}

    def get_user_institution_ids(self):
        return user_institution_ids(self.request.user)

    def filter_by_institution(self, queryset, lookup=None):
        institution_ids = self.get_user_institution_ids()
        if institution_ids is None:
            return queryset
        if not institution_ids:
            return queryset.none()
        lookup = lookup or self.institution_lookup
        if not lookup:
            return queryset.none()
        return queryset.filter(**{f'{lookup}__in': institution_ids}).distinct()

    def get_permissions(self):
        if getattr(self, 'action', None) in self.admin_only_actions:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()


class UserScopedQuerysetMixin:
    def scoped_students(self, queryset):
        user = self.request.user
        institution_ids = user_institution_ids(user)
        if institution_ids is None:
            return queryset
        if getattr(user, 'user_type', None) == 'student':
            return queryset.filter(user=user)
        if getattr(user, 'user_type', None) == 'parent':
            return queryset.filter(parents__user=user)
        if getattr(user, 'user_type', None) == 'teacher':
            return queryset.filter(current_class__schedules__teacher__user=user).distinct()
        if institution_ids:
            return queryset.filter(current_class__academic_year__institution_id__in=institution_ids).distinct()
        return queryset.none()


class StudentAccessMixin:
    def scope_student_queryset(self, queryset):
        user = self.request.user
        institution_ids = user_institution_ids(user)
        if institution_ids is None:
            return queryset
        if getattr(user, 'user_type', None) == 'student':
            return queryset.filter(user=user)
        if getattr(user, 'user_type', None) == 'parent':
            return queryset.filter(parents__user=user)
        if getattr(user, 'user_type', None) == 'teacher':
            return queryset.filter(current_class__schedules__teacher__user=user).distinct()
        if institution_ids:
            return queryset.filter(current_class__academic_year__institution_id__in=institution_ids).distinct()
        return queryset.none()


class InstitutionAccessMixin:
    institution_lookup = None

    def scope_institution_queryset(self, queryset, lookup=None):
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids is None:
            return queryset
        if not institution_ids:
            return queryset.none()
        lookup = lookup or self.institution_lookup
        if not lookup:
            return queryset.none()
        return queryset.filter(**{f'{lookup}__in': institution_ids}).distinct()
