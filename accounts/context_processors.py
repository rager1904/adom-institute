def role_ui(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'role_ui': {}}

    user_type = getattr(user, 'user_type', '')
    is_platform_admin = bool(user.is_superuser or user_type == 'super_admin')
    is_admin = bool(is_platform_admin or user_type == 'administrator')
    is_teacher = user_type == 'teacher'
    is_student = user_type == 'student'
    is_parent = user_type == 'parent'
    is_accountant = user_type == 'accountant'

    role_labels = {
        'super_admin': 'Platform administrator',
        'administrator': 'Administrator',
        'teacher': 'Teacher',
        'student': 'Student',
        'parent': 'Parent',
        'accountant': 'Accountant',
    }

    return {
        'role_ui': {
            'user_type': user_type,
            'label': role_labels.get(user_type, 'User'),
            'is_admin': is_admin,
            'is_teacher': is_teacher,
            'is_student': is_student,
            'is_parent': is_parent,
            'is_accountant': is_accountant,
            'can_manage_people': is_admin,
            'can_manage_academics': is_admin or is_teacher,
            'can_manage_attendance': is_admin or is_teacher,
            'can_manage_finance': is_admin or is_accountant,
            'can_manage_library': is_admin,
            'can_manage_timetable': is_admin,
            'student_scope_label': (
                'Students' if is_admin
                else 'My Students' if is_teacher
                else 'My Profile' if is_student
                else 'My Children' if is_parent
                else 'Students'
            ),
            'teacher_scope_label': (
                'Teachers' if is_admin
                else 'My Teaching Profile' if is_teacher
                else 'My Teachers' if is_student or is_parent
                else 'Teachers'
            ),
            'fees_scope_label': (
                'Fee Management' if is_admin or is_accountant
                else 'My Fees' if is_student
                else 'Children Fees' if is_parent
                else 'Fees'
            ),
            'attendance_scope_label': (
                'Attendance Management' if is_admin
                else 'Class Attendance' if is_teacher
                else 'My Attendance' if is_student
                else 'Children Attendance' if is_parent
                else 'Attendance'
            ),
            'academic_scope_label': (
                'Academic Management' if is_admin
                else 'Teaching Workspace' if is_teacher
                else 'My Learning' if is_student
                else 'Children Learning' if is_parent
                else 'Academics'
            ),
            'timetable_scope_label': (
                'Timetable Management' if is_admin
                else 'My Teaching Timetable' if is_teacher
                else 'My Class Timetable' if is_student
                else 'Children Timetable' if is_parent
                else 'Timetable'
            ),
        }
    }
