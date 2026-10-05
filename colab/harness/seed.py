#!/usr/bin/env python3
"""
Seed ADOM Institute with a realistic, multi-tenant dataset for load testing.

Design notes
------------
* Everything is ``bulk_create``-ed. The default Django test fixtures and
  ``--loaddata`` path is unusable at this volume (it does per-object INSERTs),
  and per-object ``save()`` would also skip the batching.
* Passwords are hashed **once**. PBKDF2 at Django's default iteration count
  takes ~100ms per hash; hashing 4000 users individually adds ~7 minutes of
  pure hashing to the run and tells us nothing about the app. Every seeded
  account therefore shares one precomputed hash for a known password.
* ``Receipt.save()`` assigns receipt numbers through a ``select_for_update``
  row lock. Bulk-creating thousands of receipts that way would serialise on a
  single row, so receipt numbers are generated up-front.
* Check constraints and ``unique_together`` are respected, otherwise the
  inserts fail and the dataset is quietly wrong. See the notes next to each
  phase.

Writes a manifest of API tokens, credentials and sample ids to JSON so the load
driver does not have to guess, and so the notebook can log in to the tunnel.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime, time as dtime, timedelta, timezone as dt_timezone
from pathlib import Path
from decimal import Decimal

SEED = 20260228
PASSWORD = "LoadTest!2345"
BATCH = 2000

FIRST_NAMES = [
    "Amahle", "Bongani", "Chanda", "Dalitso", "Enock", "Fatima", "Gift", "Hakim",
    "Irene", "Jonas", "Kabwe", "Lusaka", "Mabel", "Naledi", "Osei", "Patience",
    "Queen", "Rashid", "Sipho", "Thandiwe", "Ubuntu", "Vera", "Wellington", "Xolani",
    "Yvonne", "Zambezi", "Alex", "Bianca", "Chinedu", "Doreen",
]
LAST_NAMES = [
    "Banda", "Chulu", "Daka", "Hamavwa", "Kabaso", "Lungu", "Mumba", "Ngoma",
    "Phiri", "Sialalike", "Tembo", "Ulenga", "Wina", "Zulu", "Chirwa", "Kasonde",
    "Mulenga", "Nyirenda", "Bwalya", "Chipeta", "Daka", "Fumba", "Kakungu", "Mbewe",
    "Nsomba", "Sinkala",
]
STREETS = [
    "Independence Ave", "Cairo Road", "Nkrumah Road", "Great East Road",
    "Lusaka Road", "Moffat Street", "Church Road", "Kwame Nkrumah Ave",
]
CITIES = ["Lusaka", "Kitwe", "Ndola", "Kabwe", "Livingstone", "Chingola", "Solwezi"]
PROVINCES = ["Lusaka", "Copperbelt", "Central", "Southern", "Western", "North-Western"]

SUBJECT_NAMES = [
    ("Mathematics", "MATH"), ("English Language", "ENG"), ("Biology", "BIO"),
    ("Chemistry", "CHEM"), ("Physics", "PHYS"), ("History", "HIST"),
    ("Geography", "GEO"), ("Computer Science", "CS"), ("Agricultural Science", "AGSCI"),
    ("Business Studies", "BUS"), ("Art & Design", "ART"), ("Music", "MUS"),
    ("Physical Education", "PE"), ("Technical Drawing", "TECH"), ("Civics", "CIV"),
    ("Religious Education", "RE"), ("Home Economics", "HOME"), ("Library Skills", "LIB"),
    ("Computer Studies", "CST"), ("Financial Accounting", "ACC"),
]

DEPARTMENT_NAMES = [
    "Sciences", "Mathematics", "Humanities", "Languages", "Commercials",
    "Technical", "Arts & Sports", "Administration", "ICT", "Guidance & Counselling",
    "Agriculture", "Library", "Examinations", "Admissions", "Accounts", "ICT Support",
]

FEE_CATEGORY_NAMES = [
    ("Tuition", "Core teaching fee"),
    ("Boarding", "Accommodation and meals"),
    ("Registration", "One-off enrolment charge"),
    ("Laboratory", "Science practicals"),
    ("Transport", "School bus service"),
    ("Library Levy", "Books and resources"),
]

BOOK_TITLES = [
    "Advanced Mathematics for Secondary Schools", "Oxford Modern English",
    "Biology for the Zambian Curriculum", "Principles of Physics",
    "Introduction to Chemistry", "World History: Modern Era",
    "Physical Geography in Practice", "Computer Science Fundamentals",
    "Financial Accounting Basics", "Civics and Citizenship Education",
    "Agricultural Science for Schools", "Business Studies Handbook",
    "Technical Drawing Standards", "Home Economics Companion",
    "Physical Education and Sport", "Concise Guide to Statistics",
    "Environmental Studies", "Creative Arts Techniques",
    "Religious Education Studies", "Library and Information Science",
]

# Grading bands, aligned with academics.Grade (name, min, max, points).
GRADE_BANDS = [
    ("A1", 80, 100, Decimal("5.00")), ("B2", 70, 79, Decimal("4.00")),
    ("B3", 60, 69, Decimal("3.00")), ("C4", 50, 59, Decimal("2.00")),
    ("C5", 40, 49, Decimal("1.00")), ("D6", 30, 39, Decimal("0.50")),
    ("E7", 0, 29, Decimal("0.00")),
]


# --------------------------------------------------------------------------- #
# Django bootstrap
# --------------------------------------------------------------------------- #

def bootstrap(repo_root: Path) -> None:
    """Put the project on sys.path and call django.setup()."""
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adom.settings")
    import django

    django.setup()


def default_repo_root() -> Path:
    # colab/harness/seed.py -> colab/harness -> colab -> <repo>
    return Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

@contextmanager
def phase(label: str):
    started = time.perf_counter()
    print(f"  [ .. ] {label} ...", flush=True)
    yield
    print(f"  [ ok ] {label} ({time.perf_counter() - started:.1f}s)", flush=True)


def insert(model, objects, batch=BATCH, label=None):
    """bulk_create with batching, returning the objects (PKs populated on PG)."""
    if not objects:
        return objects
    created = model.objects.bulk_create(objects, batch_size=batch)
    if label:
        print(f"         {label}: {len(created)} rows", flush=True)
    return created


def recent_weekdays(count: int, end: date | None = None) -> list[date]:
    """The `count` most recent weekdays, oldest first."""
    end = end or date.today()
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def future_weekdays(count: int, start_offset: int = 30) -> list[date]:
    """`count` weekdays starting `start_offset` days in the future.

    Used for the write-scenario pools so the benchmark can insert attendance
    rows without ever colliding with the (student, date) unique constraint.
    """
    days: list[date] = []
    cursor = date.today() + timedelta(days=start_offset)
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def weighted_pick(rng: random.Random, values, weights):
    return rng.choices(values, weights=weights, k=1)[0]


# --------------------------------------------------------------------------- #
# Seed phases
# --------------------------------------------------------------------------- #

def seed_tenancy(rng, scale):
    from students.models import AcademicYear, Class
    from teachers.models import Subject
    from accounts.models import Institution

    institutions = insert(
        Institution,
        [
            Institution(
                name=f"ADOM Institute Campus {i + 1}",
                code=f"ADOM-{i + 1:02d}",
                institution_type=Institution.InstitutionType.SECONDARY_SCHOOL
                if i % 2 == 0
                else Institution.InstitutionType.COLLEGE,
                country="Zambia",
                province=PROVINCES[i % len(PROVINCES)],
                district=f"District {i + 1}",
                address=f"{rng.randint(1, 400)} {rng.choice(STREETS)}, {CITIES[i % len(CITIES)]}",
                phone_number=f"+2609{rng.randint(1000000, 9999999)}",
                email=f"office{rng.randint(100, 999)}@adom-loadtest.local",
                is_active=True,
            )
            for i in range(scale.institutions)
        ],
        label="Institution",
    )

    this_year = date.today().year
    years, classes = [], []
    for inst in institutions:
        for y in range(scale.academic_years):
            start = date(this_year - 1 + y, 1, 1)
            end = date(this_year + y, 12, 31)
            # The most recent year is the active one.
            is_active = y == scale.academic_years - 1
            years.append(
                AcademicYear(
                    institution=inst,
                    name=f"{this_year - 1 + y}/{str(this_year + y)[2:]} @ {inst.code}",
                    start_date=start,
                    end_date=end,
                    is_active=is_active,
                )
            )
    insert(AcademicYear, years, label="AcademicYear")

    for year in AcademicYear.objects.order_by("id"):
        for c in range(scale.classes_per_year):
            level = 8 + (c // 4)
            letter = chr(ord("A") + c % 4)
            classes.append(
                Class(
                    # Class.name is unique GLOBALLY, not per year.
                    name=f"G{level}{letter}-{year.id:03d}",
                    display_name=f"Grade {level}{letter}",
                    academic_year=year,
                    capacity=60,
                    section=letter,
                    is_active=True,
                )
            )
    insert(Class, classes, label="Class")

    insert(
        Subject,
        [
            Subject(name=name, code=f"{code}{i:02d}", description=f"{name} syllabus", is_active=True)
            for i, (name, code) in enumerate(SUBJECT_NAMES[: scale.subjects])
        ],
        label="Subject",
    )
    available = min(scale.subjects, len(SUBJECT_NAMES))
    if available != scale.subjects:
        print(
            f"         note: only {len(SUBJECT_NAMES)} subjects are defined;"
            f" seeding {available} instead of {scale.subjects}",
            flush=True,
        )
    return institutions


def seed_people(rng, scale, institutions):
    """Users, memberships, and the role profiles (Student/Parent/Teacher)."""
    from django.contrib.auth.hashers import make_password
    from rest_framework.authtoken.models import Token
    from accounts.models import InstitutionMembership, User
    from students.models import Class, Parent, Student
    from teachers.models import Teacher

    # One hash reused everywhere -- see module docstring.
    shared_hash = make_password(PASSWORD)
    now = datetime.now(dt_timezone.utc)

    def mk_user(i, user_type, first, last, **extra):
        return User(
            email=f"{user_type}.{i}@loadtest.adom.local",
            password=shared_hash,
            first_name=first,
            last_name=last,
            user_type=user_type,
            is_active=True,
            is_verified=True,
            is_staff=user_type in ("super_admin", "administrator"),
            is_superuser=user_type == "super_admin",
            date_joined=now - timedelta(days=rng.randint(30, 1500)),
            phone_number=f"+2609{rng.randint(1000000, 9999999)}",
            address=f"{rng.randint(1, 400)} {rng.choice(STREETS)}",
            **extra,
        )

    print("         hashing one shared password (not 4000)", flush=True)

    staff_users, admin_users, accountant_users = [], [], []
    staff_users.append(mk_user(0, "super_admin", "Platform", "Administrator"))
    for i in range(1, scale.staff):
        admin_users.append(mk_user(i, "administrator", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)))
    for i in range(scale.accountants):
        accountant_users.append(
            mk_user(i, "accountant", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
        )
    insert(User, staff_users + admin_users + accountant_users, label="User (staff)")

    teacher_users = [
        mk_user(i, "teacher", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
        for i in range(scale.teachers)
    ]
    insert(User, teacher_users, label="User (teachers)")

    student_users = [
        mk_user(i, "student", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
        for i in range(scale.students)
    ]
    insert(User, student_users, label="User (students)")

    parent_users = [
        mk_user(i, "parent", rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
        for i in range(scale.parents)
    ]
    insert(User, parent_users, label="User (parents)")

    # ---- InstitutionMembership (the tenant boundary) ------------------------
    memberships = []

    def add_membership(user, institution, role):
        memberships.append(
            InstitutionMembership(
                user=user, institution=institution, role=role, is_active=True, assigned_by=None
            )
        )

    # One membership per user: their home campus. InstitutionMembership has
    # unique_together(institution, user), so a user cannot be added twice to
    # the same campus.
    all_users = list(User.objects.order_by("id"))
    for idx, user in enumerate(all_users):
        institution = institutions[idx % len(institutions)]
        role = {
            "super_admin": InstitutionMembership.MembershipRole.OWNER,
            "administrator": InstitutionMembership.MembershipRole.ADMINISTRATOR,
            "accountant": InstitutionMembership.MembershipRole.ACCOUNTANT,
            "teacher": InstitutionMembership.MembershipRole.TEACHER,
            "student": InstitutionMembership.MembershipRole.STUDENT,
            "parent": InstitutionMembership.MembershipRole.PARENT,
        }[user.user_type]
        add_membership(user, institution, role)
    insert(InstitutionMembership, memberships, label="InstitutionMembership")

    # ---- Teacher profiles ---------------------------------------------------
    teachers = [
        Teacher(
            user=user,
            employee_id=f"EMP{1000 + i}",
            employment_type=weighted_pick(
                rng, ["full_time", "part_time", "contract", "visiting"], [70, 15, 10, 5]
            ),
            employment_status=Teacher.EmploymentStatus.ACTIVE
            if i % 10
            else Teacher.EmploymentStatus.ON_LEAVE,
            joining_date=date.today() - timedelta(days=rng.randint(120, 4000)),
            qualification=rng.choice(
                ["BSc", "BA", "BEd", "MEd", "PhD", "HND", "Diploma"]
            ),
            specialization=rng.choice([n for n, _ in SUBJECT_NAMES]),
            experience_years=rng.randint(1, 30),
            phone_number=f"+2609{rng.randint(1000000, 9999999)}",
            emergency_contact=f"+2609{rng.randint(1000000, 9999999)}",
            address=f"{rng.randint(1, 400)} {rng.choice(STREETS)}",
            is_class_teacher=i % 3 == 0,
            is_head_of_department=i % 17 == 0,
        )
        for i, user in enumerate(teacher_users)
    ]
    insert(Teacher, teachers, label="Teacher")

    # ---- Students -----------------------------------------------------------
    # Only classes of an ACTIVE academic year take students, because the
    # teacher-scoped read path joins students -> current_class -> schedules,
    # and schedules only exist for classes we populate.
    active_classes = list(
        Class.objects.filter(academic_year__is_active=True).order_by("id")
    )

    students = []
    for i, user in enumerate(student_users):
        klass = active_classes[i % len(active_classes)]
        # admission_date must be >= date_of_birth (DB check constraint).
        admission = date.today() - timedelta(days=rng.randint(200, 1460))
        dob = admission - timedelta(days=rng.randint(365 * 5, 365 * 22))
        students.append(
            Student(
                user=user,
                student_id=f"STU{100000 + i}",
                admission_number=f"ADM{200000 + i}",
                roll_number=str(i % 999),
                gender=weighted_pick(rng, ["male", "female"], [50, 50]),
                date_of_birth=dob,
                phone_number=f"+2609{rng.randint(1000000, 9999999)}",
                address=f"{rng.randint(1, 400)} {rng.choice(STREETS)}",
                current_class=klass,
                admission_date=admission,
                admission_status=weighted_pick(
                    rng, ["approved", "pending", "rejected"], [92, 6, 2]
                ),
                is_active=True,
            )
        )
    insert(Student, students, label="Student")

    # ---- Parents ------------------------------------------------------------
    # Attach up to two parents per student, cycling through parent users.
    parent_rows = []
    all_students = list(Student.objects.order_by("id"))
    pidx = 0
    for s_i, student in enumerate(all_students):
        for n in range(1 + (1 if s_i % 5 == 0 else 0)):
            if pidx >= len(parent_users):
                break
            parent_rows.append(
                Parent(
                    student=student,
                    user=parent_users[pidx],
                    relationship=["father", "mother", "guardian"][n % 3],
                    occupation=rng.choice(
                        ["Farmer", "Teacher", "Nurse", "Driver", "Shop Owner", "Engineer"]
                    ),
                    phone_number=f"+2609{rng.randint(1000000, 9999999)}",
                    email=parent_users[pidx].email,
                    is_primary_contact=n == 0,
                    is_emergency_contact=n == 0,
                )
            )
            pidx += 1
    insert(Parent, parent_rows, label="Parent")

    # ---- API tokens for the load driver ------------------------------------
    # DRF Token uses a 40-char hex key; generate them directly so we can
    # bulk_create instead of one INSERT per user.
    import binascii

    def pick(users, limit):
        return list(users[:limit])

    token_specs = {
        "super_admin": pick(staff_users, 1),
        "administrator": pick(admin_users, 6),
        "accountant": pick(accountant_users, min(4, len(accountant_users))),
        "teacher": pick(teacher_users, 40),
        "student": pick(student_users, 40),
        "parent": pick(parent_users, 40),
    }
    token_rows, manifest_tokens = [], {}
    for role, users in token_specs.items():
        keys = []
        for user in users:
            key = binascii.hexlify(os.urandom(20)).decode()
            token_rows.append(Token(key=key, user=user))
            keys.append(key)
        manifest_tokens[role] = keys
    insert(Token, token_rows, batch=500, label="API tokens")

    manifest_tokens["_emails"] = {
        # A list, not a single address: the WebSocket probe logs each virtual
        # user in separately, and they need to be distinct accounts so the
        # notification rooms differ.
        role: [u.email for u in users][:60] for role, users in token_specs.items()
    }
    return manifest_tokens, parent_rows, all_students


def seed_teaching_load(rng, scale):
    """Departments, teacher/subject links, rooms, timeslots, timetable."""
    from students.models import Class
    from teachers.models import (
        Department,
        Subject,
        Teacher,
        TeacherDepartment,
        TeacherSubject,
    )
    from timetable.models import ClassSchedule, Room, RoomSchedule, TimeSlot, TeacherSchedule

    teachers = list(Teacher.objects.order_by("id"))
    subjects = list(Subject.objects.order_by("id"))
    departments = [
        Department(name=name, code=f"DEPT{i:02d}", description=f"{name} department", is_active=True)
        for i, name in enumerate(DEPARTMENT_NAMES[: scale.departments])
    ]
    insert(Department, departments, label="Department")
    departments = list(Department.objects.order_by("id"))

    # Link every teacher to a department, and every teacher to 2 subjects.
    insert(
        TeacherDepartment,
        [
            TeacherDepartment(teacher=t, department=departments[i % len(departments)])
            for i, t in enumerate(teachers)
        ],
        label="TeacherDepartment",
    )
    insert(
        TeacherSubject,
        [
            # Each teacher gets TWO DIFFERENT subjects. The old form indexed
            # subjects by the teacher index only, so the inner loop produced
            # two rows with an identical (teacher, subject) pair, which
            # violates the unique constraint on that pair and aborted the
            # whole seed with an IntegrityError. Offsetting by the inner index
            # keeps the pairs distinct.
            TeacherSubject(
                teacher=t,
                subject=subjects[(i + k) % len(subjects)],
                is_primary=k == 0,
            )
            for i, t in enumerate(teachers)
            for k in range(2)
        ],
        label="TeacherSubject",
    )

    rooms = insert(
        Room,
        [
            Room(
                name=f"Room {i + 1:03d}",
                room_type=weighted_pick(
                    rng,
                    ["classroom", "laboratory", "library", "auditorium", "office"],
                    [60, 15, 8, 5, 12],
                ),
                capacity=rng.choice([30, 40, 50, 60]),
                building=f"Block {chr(ord('A') + i % 4)}",
                floor=1 + i % 3,
                is_active=True,
            )
            for i in range(scale.rooms)
        ],
        label="Room",
    )
    insert(
        Room,
        [
            Room(
                name=f"Science Lab {i + 1}",
                room_type="laboratory",
                capacity=30,
                building="Block S",
                floor=1,
                is_active=True,
            )
            for i in range(max(2, scale.subjects // 4))
        ],
        label="Room (labs)",
    )
    rooms = list(Room.objects.order_by("id"))

    # 6 teaching periods x 5 weekdays + 2 break slots.
    slots = []
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        for period in range(1, 9):
            start_hour = 7 + (period - 1)
            is_break = period == 5
            start_min = 0 if not is_break else 30
            slots.append(
                TimeSlot(
                    day=day,
                    start_time=dtime(start_hour, start_min),
                    end_time=dtime(start_hour, 50),
                    period_number=period,
                    is_break=is_break,
                    break_type="Lunch" if is_break else None,
                )
            )
    insert(TimeSlot, slots, label="TimeSlot")
    slots = list(TimeSlot.objects.order_by("id"))
    teaching_slots = [s for s in slots if not s.is_break]

    # Give every active-year class a full weekly timetable. This is what makes
    # the teacher-scoped queries expensive: they join students -> current_class
    # -> schedules -> teacher.
    active_classes = list(Class.objects.filter(academic_year__is_active=True).order_by("id"))
    schedules, room_schedules, teacher_schedules = [], [], []
    room_i = 0
    for c_i, klass in enumerate(active_classes):
        for s_i, slot in enumerate(teaching_slots):
            teacher = teachers[(c_i * 5 + s_i) % len(teachers)]
            subject = subjects[(c_i * 3 + s_i) % len(subjects)]
            room = rooms[room_i % len(rooms)]
            room_i += 1
            # unique_together(class_obj, time_slot)
            schedules.append(
                ClassSchedule(
                    class_obj=klass, subject=subject, teacher=teacher, room=room,
                    time_slot=slot, is_active=True,
                )
            )
            # unique_together(teacher, time_slot) -- only emit when first seen.
            teacher_schedules.append(
                TeacherSchedule(teacher=teacher, time_slot=slot, is_available=True)
            )
            room_schedules.append(
                RoomSchedule(room=room, time_slot=slot, is_available=True)
            )
    insert(ClassSchedule, schedules, label="ClassSchedule")
    # TeacherSchedule/TeacherRoom are unique per (owner, slot) -- dedupe.
    seen, deduped = set(), []
    for row in teacher_schedules:
        key = (row.teacher_id, row.time_slot_id)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    insert(TeacherSchedule, deduped, label="TeacherSchedule")
    seen, deduped = set(), []
    for row in room_schedules:
        key = (row.room_id, row.time_slot_id)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    insert(RoomSchedule, deduped, label="RoomSchedule")

    return active_classes


def seed_academics(rng, scale, active_classes):
    from academics.models import (
        Assignment,
        Exam,
        ExamSubject,
        ExamType,
        Grade,
        StudentExamResult,
    )
    from students.models import Student
    from teachers.models import Subject, Teacher

    insert(
        ExamType,
        [
            ExamType(name="Mid Term", description="Mid-term assessment", weightage=Decimal("30.00")),
            ExamType(name="End of Term", description="End-of-term assessment", weightage=Decimal("70.00")),
            ExamType(name="Mock Exam", description="Pre-board mock", weightage=Decimal("100.00")),
        ],
        label="ExamType",
    )
    exam_types = list(ExamType.objects.order_by("id"))
    grades = insert(
        Grade,
        [
            Grade(name=name, min_marks=lo, max_marks=hi, grade_point=points, description=f"Grade {name}")
            for name, lo, hi, points in GRADE_BANDS
        ],
        label="Grade",
    )
    grades = list(Grade.objects.order_by("id"))
    subjects = list(Subject.objects.order_by("id"))
    teachers = list(Teacher.objects.order_by("id"))
    students = list(Student.objects.order_by("id"))

    insert(
        Assignment,
        [
            Assignment(
                title=f"Assignment {a + 1}: {subjects[(c_i + a) % len(subjects)].name}",
                description="Complete the questions and submit before the due date.",
                subject=subjects[(c_i + a) % len(subjects)],
                class_obj=klass,
                teacher=teachers[(c_i + a) % len(teachers)],
                due_date=datetime.now(dt_timezone.utc) + timedelta(days=rng.randint(3, 30)),
                max_marks=50,
                is_active=True,
            )
            for c_i, klass in enumerate(active_classes)
            for a in range(2)
        ],
        label="Assignment",
    )

    exam_rows, exam_subject_rows = [], []
    for c_i, klass in enumerate(active_classes):
        for e in range(scale.exams):
            start = date.today() - timedelta(days=rng.randint(10, 90))
            exam_rows.append(
                Exam(
                    # Exam has unique_together(name, academic_year, class_obj), so the
                    # per-class sequence number keeps this unique even when more than
                    # len(exam_types) exams are requested per class.
                    name=f"{exam_types[e % len(exam_types)].name} {klass.name} #{e + 1}",
                    exam_type=exam_types[e % len(exam_types)],
                    academic_year=klass.academic_year,
                    class_obj=klass,
                    start_date=start,
                    end_date=start + timedelta(days=rng.randint(3, 14)),
                    total_marks=100,
                    passing_marks=40,
                    is_active=True,
                )
            )
    insert(Exam, exam_rows, label="Exam")
    exams = list(Exam.objects.order_by("id"))

    for exam in exams:
        for s in range(scale.subjects_per_exam):
            subject = subjects[(exam.class_obj_id + s) % len(subjects)]
            exam_subject_rows.append(
                ExamSubject(
                    exam=exam, subject=subject, max_marks=100, passing_marks=40,
                    exam_date=exam.start_date + timedelta(days=s % 5),
                    duration=90,
                )
            )
    insert(ExamSubject, exam_subject_rows, label="ExamSubject")
    exam_subjects = list(ExamSubject.objects.order_by("id"))
    by_exam: dict[int, list[ExamSubject]] = {}
    for es in exam_subjects:
        by_exam.setdefault(es.exam_id, []).append(es)

    # Results: every student x the subjects of their class's exam.
    student_by_class: dict[int, list] = {}
    for student in students:
        if student.current_class_id:
            student_by_class.setdefault(student.current_class_id, []).append(student)

    results = []
    for klass in active_classes:
        class_students = student_by_class.get(klass.id, [])
        if not class_students:
            continue
        for exam in exams:
            if exam.class_obj_id != klass.id:
                continue
            for es in by_exam.get(exam.id, []):
                for student in class_students:
                    pct = rng.uniform(0.25, 1.0)
                    marks = round(es.max_marks * pct, 2)
                    band = next(
                        (g for g in grades if g.min_marks <= marks <= g.max_marks), grades[-1]
                    )
                    results.append(
                        StudentExamResult(
                            student=student,
                            exam_subject=es,
                            marks_obtained=Decimal(str(marks)),
                            grade=band,
                            remarks="" if band.grade_point > 0 else "Fail",
                            created_by=teachers[(student.id + es.id) % len(teachers)],
                        )
                    )
    insert(StudentExamResult, results, label="StudentExamResult")
    return grades, exam_subjects


def seed_attendance(rng, scale):
    from attendance.models import (
        Attendance,
        ClassAttendance,
        LeaveRequest,
        TeacherAttendance,
    )
    from students.models import Class, Student
    from teachers.models import Teacher

    teachers = list(Teacher.objects.order_by("id"))
    students = list(Student.objects.order_by("id"))
    days = recent_weekdays(scale.attendance_days)

    rows = [
        Attendance(
            student=student,
            date=day,
            status=weighted_pick(
                rng,
                ["present", "late", "absent", "excused", "half_day"],
                [86, 5, 5, 2, 2],
            ),
            marked_by=teachers[(student.id + i) % len(teachers)],
        )
        for i, day in enumerate(days)
        for student in students
    ]
    insert(Attendance, rows, label="Attendance")

    # ClassAttendance needs present/absent/late <= total_students.
    classes = list(Class.objects.order_by("id"))
    per_class_counts: dict[int, int] = {}
    for student in students:
        if student.current_class_id:
            per_class_counts[student.current_class_id] = per_class_counts.get(student.current_class_id, 0) + 1

    class_rows = []
    for klass in classes:
        total = per_class_counts.get(klass.id, 0)
        if not total:
            continue
        for day in days:
            present = int(total * rng.uniform(0.75, 0.98))
            late = min(total - present, rng.randint(0, 4))
            absent = total - present - late
            class_rows.append(
                ClassAttendance(
                    class_obj=klass, date=day, total_students=total,
                    present_count=present, absent_count=absent, late_count=late,
                    marked_by=teachers[klass.id % len(teachers)],
                )
            )
    insert(ClassAttendance, class_rows, label="ClassAttendance")

    t_days = recent_weekdays(scale.teacher_attendance_days)
    insert(
        TeacherAttendance,
        [
            TeacherAttendance(
                teacher=teacher,
                date=day,
                status=weighted_pick(
                    rng, ["present", "late", "absent", "on_leave"], [85, 5, 4, 6]
                ),
                check_in_time=dtime(7, 30),
                check_out_time=dtime(15, 30),
            )
            for day in t_days
            for teacher in teachers
        ],
        label="TeacherAttendance",
    )

    # LeaveRequest: the DB check constraint demands exactly one owner.
    leave_rows = []
    for i in range(min(200, scale.students)):
        student = students[i]
        start = date.today() - timedelta(days=rng.randint(1, 60))
        leave_rows.append(
            LeaveRequest(
                student=student, teacher=None, leave_type="sick_leave",
                start_date=start, end_date=start + timedelta(days=rng.randint(0, 3)),
                reason="Reported unwell.", status=weighted_pick(
                    rng, ["pending", "approved", "rejected", "cancelled"], [30, 55, 10, 5]
                ),
            )
        )
    for i in range(min(60, len(teachers))):
        start = date.today() - timedelta(days=rng.randint(1, 60))
        leave_rows.append(
            LeaveRequest(
                student=None, teacher=teachers[i], leave_type="annual_leave",
                start_date=start, end_date=start + timedelta(days=rng.randint(0, 5)),
                reason="Annual leave.", status="approved",
            )
        )
    insert(LeaveRequest, leave_rows, label="LeaveRequest")


def seed_fees(rng, scale, active_classes):
    from fees.models import (
        FeeCategory,
        FeeDiscount,
        FeeStructure,
        FeeStructureDetail,
        Payment,
        Receipt,
        StudentFee,
        StudentFeeDiscount,
    )
    from students.models import Student
    from accounts.models import User

    categories = insert(
        FeeCategory,
        [
            FeeCategory(name=name, description=desc, is_active=True)
            for name, desc in FEE_CATEGORY_NAMES
        ],
        label="FeeCategory",
    )
    categories = list(FeeCategory.objects.order_by("id"))

    insert(
        FeeDiscount,
        [
            FeeDiscount(name="Scholarship 25%", discount_type="percentage", discount_value=Decimal("25.00")),
            FeeDiscount(name="Staff Relative", discount_type="percentage", discount_value=Decimal("50.00")),
            FeeDiscount(name="S Bursary", discount_type="fixed_amount", discount_value=Decimal("500.00")),
        ],
        label="FeeDiscount",
    )
    discounts = list(FeeDiscount.objects.order_by("id"))

    structures = []
    for klass in active_classes:
        for ftype in ["monthly", "termly", "annual"]:
            structures.append(
                FeeStructure(
                    name=f"{klass.name} {ftype.title()} Fees",
                    academic_year=klass.academic_year,
                    class_obj=klass,
                    fee_type=ftype,
                    is_active=True,
                )
            )
    insert(FeeStructure, structures, label="FeeStructure")
    structures = list(FeeStructure.objects.order_by("id"))

    detail_rows = []
    for structure in structures:
        for cat in categories[:3]:
            detail_rows.append(
                FeeStructureDetail(
                    fee_structure=structure, fee_category=cat,
                    amount=Decimal(rng.randint(15000, 90000)) / Decimal(100),
                    is_optional=cat.name == "Transport",
                    due_date=date.today() + timedelta(days=rng.randint(10, 90)),
                )
            )
    insert(FeeStructureDetail, detail_rows, label="FeeStructureDetail")
    details = list(FeeStructureDetail.objects.order_by("id"))
    details_by_class: dict[int, list[FeeStructureDetail]] = {}
    for d in details:
        details_by_class.setdefault(d.fee_structure.class_obj_id, []).append(d)

    students = list(Student.objects.order_by("id"))
    accounts = list(User.objects.filter(user_type="accountant").order_by("id")) or list(
        User.objects.filter(user_type__in=["administrator", "super_admin"]).order_by("id")[:1]
    )

    fee_rows = []
    for student in students:
        if not student.current_class_id:
            continue
        for detail in details_by_class.get(student.current_class_id, [])[:3]:
            amount = detail.amount
            roll = rng.random()
            if roll < 0.62:
                paid, status = amount, "paid"
            elif roll < 0.80:
                paid, status = (amount / 2).quantize(Decimal("0.01")), "partial"
            elif roll < 0.93:
                paid, status = Decimal("0.00"), "pending"
            else:
                paid, status = Decimal("0.00"), "overdue"
            fee_rows.append(
                StudentFee(
                    student=student, fee_structure_detail=detail, amount=amount,
                    paid_amount=paid,
                    due_date=detail.due_date or date.today() + timedelta(days=30),
                    payment_status=status,
                )
            )
    insert(StudentFee, fee_rows, label="StudentFee")

    # Payments only for rows that actually moved, amount > 0 (DB check).
    paid_fees = [f for f in StudentFee.objects.filter(paid_amount__gt=0).order_by("id")]
    payment_rows = []
    for i, fee in enumerate(paid_fees):
        payment_rows.append(
            Payment(
                student=fee.student, student_fee=fee,
                amount=fee.paid_amount,
                payment_method=weighted_pick(
                    rng, ["cash", "bank_transfer", "online", "cheque", "card"], [30, 25, 25, 10, 10]
                ),
                payment_status=weighted_pick(rng, ["completed", "pending", "failed"], [88, 8, 4]),
                transaction_id=f"TXN{rng.getrandbits(48):012x}",
                reference_number=f"REF{i:08d}",
                received_by=accounts[i % len(accounts)] if accounts else None,
            )
        )
    insert(Payment, payment_rows, label="Payment")

    # Receipt.save() would serialise on ReceiptSequence; write numbers directly.
    completed = list(
        Payment.objects.filter(payment_status="completed")
        .select_related("student__user", "student__current_class")
        .order_by("id")
    )
    receipt_rows = []
    for i, payment in enumerate(completed):
        student_name = payment.student.user.get_full_name()
        receipt_rows.append(
            Receipt(
                payment=payment,
                receipt_number=f"RCP{date.today().year}{i + 1:06d}",
                student_name=student_name,
                class_name=payment.student.current_class.display_name
                if payment.student.current_class_id
                else "N/A",
                fee_category="Various",
                amount_paid=payment.amount,
                payment_method=payment.get_payment_method_display(),
                school_name="ADOM Institute",
                school_address="Load Test Campus",
                school_phone="+260211000000",
            )
        )
    insert(Receipt, receipt_rows, label="Receipt")
    # Keep the sequence ahead of the numbers we just wrote.
    from fees.models import ReceiptSequence

    ReceiptSequence.objects.update_or_create(
        year=date.today().year, defaults={"last_number": len(receipt_rows) + 1}
    )

    fee_by_student: dict[int, list[StudentFee]] = {}
    for fee in fee_rows:
        fee_by_student.setdefault(fee.student_id, []).append(fee)
    discount_rows = []
    for i, student in enumerate(students):
        fees = fee_by_student.get(student.id)
        if fees and i % 20 == 0:
            fee = fees[0]
            discount_rows.append(
                StudentFeeDiscount(
                    student=student,
                    fee_discount=discounts[i % len(discounts)],
                    student_fee=fee,
                    discount_amount=(fee.amount * Decimal("0.25")).quantize(Decimal("0.01")),
                    reason="Merit award",
                    approved_by=accounts[0] if accounts else None,
                )
            )
    insert(StudentFeeDiscount, discount_rows, label="StudentFeeDiscount")


def seed_communication(rng, scale):
    from accounts.models import User
    from communication.models import (
        Announcement,
        CommunicationLog,
        Message,
        MessageRecipient,
        Notification,
    )
    from students.models import Student

    teachers = list(User.objects.filter(user_type="teacher").order_by("id"))
    students = list(Student.objects.order_by("id"))
    staff = list(User.objects.filter(user_type__in=["super_admin", "administrator"]).order_by("id"))
    if not staff:
        return

    insert(
        Announcement,
        [
            Announcement(
                title=f"Announcement {i + 1}: {rng.choice(['Term Opening', 'Sports Day', 'Parent Meeting', 'Exam Timetable', 'Holiday Notice'])}",
                content="Details are available on the notice board and via SMS.",
                announcement_type=weighted_pick(
                    rng, ["general", "academic", "event", "emergency", "holiday"], [40, 30, 20, 5, 5]
                ),
                target_audience=weighted_pick(
                    rng, ["all", "students", "teachers", "parents", "administrators"], [50, 20, 10, 15, 5]
                ),
                is_published=True,
                published_at=datetime.now(dt_timezone.utc) - timedelta(days=rng.randint(1, 120)),
                published_by=staff[i % len(staff)],
                is_urgent=i % 10 == 0,
                is_featured=i % 5 == 0,
            )
            for i in range(scale.announcements)
        ],
        label="Announcement",
    )

    # Messages: teacher -> student. M2M recipients need a second pass, so build
    # Message rows first, then MessageRecipient rows.
    messages = []
    for t_i, teacher in enumerate(teachers):
        for m in range(scale.messages_per_teacher):
            student = students[(t_i * 7 + m * 13) % len(students)]
            messages.append(
                Message(
                    sender=teacher,
                    subject=f"Progress update on {student.student_id}",
                    content="Please review the latest assessment feedback.",
                    message_type="direct",
                    status=weighted_pick(rng, ["sent", "delivered", "read"], [30, 30, 40]),
                    is_urgent=False,
                )
            )
    insert(Message, messages, label="Message")

    all_students_users = [s.user for s in students]
    recipient_rows = []
    for i, message in enumerate(messages):
        for off in range(1, 4):
            student = all_students_users[(i * 3 + off * 11) % len(all_students_users)]
            recipient_rows.append(
                MessageRecipient(
                    message=message, recipient=student,
                    is_read=message.status == "read", is_deleted=False,
                )
            )
    # unique_together(message, recipient) -- dedupe defensively.
    seen, deduped = set(), []
    for row in recipient_rows:
        key = (row.message_id, row.recipient_id)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    insert(MessageRecipient, deduped, label="MessageRecipient")

    notifications = []
    for i, student in enumerate(students):
        for n in range(scale.notifications_per_student):
            notifications.append(
                Notification(
                    recipient=student.user,
                    notification_type=["message", "announcement", "attendance", "exam", "fee"][
                        n % 5
                    ],
                    title=f"Notification {n + 1}",
                    message="You have a new update. Tap to view.",
                    status=weighted_pick(
                        rng, ["pending", "sent", "delivered", "read", "failed"], [10, 20, 20, 45, 5]
                    ),
                    sent_at=datetime.now(dt_timezone.utc) - timedelta(hours=rng.randint(1, 720)),
                    read_at=datetime.now(dt_timezone.utc) - timedelta(hours=rng.randint(1, 700))
                    if n % 2
                    else None,
                    is_urgent=n == 0,
                )
            )
            if len(notifications) >= 60000:
                break
        if len(notifications) >= 60000:
            break
    insert(Notification, notifications, label="Notification")

    logs = []
    for i in range(min(20000, len(notifications))):
        notification = notifications[i]
        logs.append(
            CommunicationLog(
                recipient=notification.recipient,
                communication_type=weighted_pick(rng, ["email", "sms", "push", "in_app"], [20, 30, 20, 30]),
                status=notification.status,
                subject=notification.title,
                content=notification.message,
                sent_at=notification.sent_at,
                related_notification=notification,
            )
        )
    insert(CommunicationLog, logs, label="CommunicationLog")


def seed_library(rng, scale):
    from accounts.models import User
    from library.models import Book, BookBorrowing, BookCategory, DigitalResource, LibrarySettings

    # Use physical books as single source of truth - do not generate synthetic books
    category_names = ['Early Childhood (3-4 years)', 'Early Childhood (4-5 years)', 'Primary - Grade 1', 'Primary - Grade 4', 'Secondary - Form 1', 'Secondary - Form 2']
    for name in category_names:
        BookCategory.objects.get_or_create(name=name, defaults={'description': f'Books for {name}', 'color': '#007bff'})

    books = list(Book.objects.filter(is_active=True).order_by('id'))
    if not books:
        categories = list(BookCategory.objects.order_by('id'))
        for cat in categories:
            pass  # no placeholders - require physical books
        books = list(Book.objects.filter(is_active=True).order_by('id'))

    borrowers = list(User.objects.filter(user_type__in=['student', 'teacher']).order_by('id'))
    borrowings = []
    now = datetime.now(dt_timezone.utc) + timedelta(minutes=5)
    if books and borrowers:
        for i in range(min(4000, scale.students // 2)):
            if i % 3:
                returned = now + timedelta(minutes=rng.randint(1, 240))
                due_date = now + timedelta(days=14)
            else:
                returned = None
                due_date = now + timedelta(days=rng.randint(1, 30))
            borrowings.append(BookBorrowing(book=books[i % len(books)], borrower=borrowers[i % len(borrowers)], due_date=due_date, return_date=returned, late_fee=Decimal('0.00') if not returned or i % 4 else Decimal('5.00'), notes='', is_active=True))
    insert(BookBorrowing, borrowings, label='BookBorrowing')

    uploaders = list(User.objects.filter(user_type__in=['teacher', 'administrator']).order_by('id'))
    insert(DigitalResource, [DigitalResource(title=f'Digital resource {i+1}', description='Shared learning material.', resource_type=['ebook','pdf','video','audio','presentation','worksheet'][i%6], file=f'library/digital/sample-{i}.bin', file_size=rng.randint(10000,5000000), author=f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}', subject='General', grade_level=f'Grade {8+i%5}', access_level=['students','teachers','public','restricted'][i%4], is_downloadable=i%3!=0, uploaded_by=uploaders[i%len(uploaders)] if uploaders else None) for i in range(300)], label='DigitalResource')
    LibrarySettings.objects.get_or_create(pk=1)


def seed_analytics(rng, scale):
    from accounts.models import AuditLog, User
    from analytics.models import (
        AnalyticsEvent,
        ClassPerformance,
        Report,
        SchoolAnalytics,
        StudentPerformance,
        TeacherPerformance,
    )
    from students.models import AcademicYear, Class, Student
    from teachers.models import Teacher

    students = list(Student.objects.select_related("current_class", "current_class__academic_year").order_by("id"))
    teachers = list(Teacher.objects.order_by("id"))
    classes = list(Class.objects.filter(academic_year__is_active=True).order_by("id"))
    years = list(AcademicYear.objects.order_by("id"))
    users = list(User.objects.order_by("id"))
    super_admin = next((u for u in users if u.user_type == "super_admin"), users[0])

    # The analytics models carry CHECK constraints comparing a "part" against
    # its "whole": obtained_marks <= total_marks, present_days <= total_days,
    # submitted_assignments <= total_assignments, paid_fees <= total_fees,
    # lowest_percentage <= highest_percentage,
    # total_fees_collected <= total_fees_expected, and
    # assignments_graded <= assignments_created.
    #
    # Drawing both sides independently makes the pair inconsistent often enough
    # to abort the seed, so each part is drawn as a bounded fraction of its
    # whole instead. Without this the analytics phase raised IntegrityError on
    # whichever row happened to draw the unlucky pair.
    def part(rng, whole, lo_frac=0.0, hi_frac=1.0):
        """An integer in [lo_frac*whole, hi_frac*whole]."""
        lo = int(whole * lo_frac)
        hi = int(whole * hi_frac)
        return rng.randint(lo, max(lo, min(hi, whole)))

    def money(rng, whole):
        """A Decimal in [0, whole], rounded like the other seeded money."""
        return Decimal(str(round(rng.uniform(0, float(whole)), 2)))

    student_rows = []
    for s in students:
        if not s.current_class_id:
            continue
        present = part(rng, 20, 0.7, 1.0)
        student_rows.append(
            StudentPerformance(
                student=s, academic_year=s.current_class.academic_year, class_obj=s.current_class,
                total_subjects=5, total_marks=Decimal("500.00"),
                obtained_marks=money(rng, Decimal("500.00")),
                percentage=Decimal(str(round(rng.uniform(30, 96), 2))),
                grade=weighted_pick(rng, ["A1", "B2", "B3", "C4", "C5", "D6"], [12, 24, 30, 18, 11, 5]),
                total_days=20, present_days=present, absent_days=20 - present,
                attendance_percentage=Decimal(str(round(rng.uniform(70, 100), 2))),
                total_assignments=10, submitted_assignments=part(rng, 10, 0.5, 1.0),
                assignment_completion_rate=Decimal(str(round(rng.uniform(50, 100), 2))),
                total_fees=Decimal("3000.00"), paid_fees=money(rng, Decimal("3000.00")),
                fee_payment_rate=Decimal(str(round(rng.uniform(0, 100), 2))),
                rank_in_class=rng.randint(1, 60), class_average=Decimal(str(round(rng.uniform(35, 75), 2))),
            )
        )
    insert(StudentPerformance, student_rows, label="StudentPerformance")

    class_rows = []
    for c in classes:
        highest = Decimal(str(round(rng.uniform(75, 100), 2)))
        # lowest <= highest is a CHECK constraint.
        lowest = Decimal(str(round(rng.uniform(10, 45), 2)))
        if lowest > highest:
            lowest, highest = highest, lowest
        class_rows.append(
            ClassPerformance(
                class_obj=c, academic_year=c.academic_year,
                total_students=sum(1 for s in students if s.current_class_id == c.id),
                average_percentage=Decimal(str(round(rng.uniform(40, 80), 2))),
                highest_percentage=highest,
                lowest_percentage=lowest,
                grade_a_count=rng.randint(0, 15), grade_b_count=rng.randint(0, 20),
                grade_c_count=rng.randint(0, 15), grade_d_count=rng.randint(0, 10),
                grade_f_count=rng.randint(0, 5),
                average_attendance=Decimal(str(round(rng.uniform(75, 98), 2))),
                total_attendance_days=20,
                total_fees_expected=Decimal("150000.00"),
                total_fees_collected=money(rng, Decimal("150000.00")),
                fee_collection_rate=Decimal(str(round(rng.uniform(30, 100), 2))),
            )
        )
    insert(ClassPerformance, class_rows, label="ClassPerformance")

    teacher_rows = []
    for t in teachers:
        if not years:
            break
        created = part(rng, 20, 0.1, 1.0)
        teaching_days = 20
        teacher_rows.append(
            TeacherPerformance(
                teacher=t, academic_year=years[0],
                total_classes=rng.randint(1, 6), total_students=rng.randint(20, 300),
                total_subjects=rng.randint(1, 3), total_teaching_days=teaching_days,
                present_days=part(rng, teaching_days, 0.75, 1.0),
                attendance_percentage=Decimal(str(round(rng.uniform(75, 100), 2))),
                assignments_created=created,
                # graded <= created is a CHECK constraint.
                assignments_graded=part(rng, created, 0.0, 1.0),
                grading_completion_rate=Decimal(str(round(rng.uniform(50, 100), 2))),
                average_student_performance=Decimal(str(round(rng.uniform(40, 80), 2))),
                student_satisfaction_score=Decimal(str(round(rng.uniform(3, 5), 2))),
                messages_sent=scale.messages_per_teacher, announcements_published=rng.randint(0, 5),
            )
        )
    insert(TeacherPerformance, teacher_rows, label="TeacherPerformance")

    insert(
        SchoolAnalytics,
        [
            SchoolAnalytics(
                academic_year=y,
                total_students=sum(1 for s in students if s.current_class and s.current_class.academic_year_id == y.id),
                new_admissions=rng.randint(10, 200), transfers_in=rng.randint(0, 30),
                transfers_out=rng.randint(0, 30), dropouts=rng.randint(0, 10),
                total_teachers=len(teachers), total_administrators=5, total_support_staff=8,
                total_classes=len(classes), total_subjects=scale.subjects,
                average_class_size=Decimal(str(scale.students_per_class)),
                overall_pass_percentage=Decimal(str(round(rng.uniform(60, 95), 2))),
                average_attendance_rate=Decimal(str(round(rng.uniform(80, 97), 2))),
                total_fees_expected=Decimal("9000000.00"),
                total_fees_collected=Decimal(str(round(rng.uniform(3000000, 9000000), 2))),
                fee_collection_rate=Decimal(str(round(rng.uniform(35, 100), 2))),
                outstanding_fees=Decimal(str(round(rng.uniform(0, 6000000), 2))),
                total_rooms=scale.rooms, room_utilization_rate=Decimal(str(round(rng.uniform(40, 95), 2))),
                active_users=len(users), system_uptime=Decimal("99.50"),
            )
            for y in years
        ],
        label="SchoolAnalytics",
    )

    insert(
        Report,
        [
            Report(
                name=f"Report {i + 1}: {n}",
                report_type=rt, description="Generated by the load-test harness.",
                parameters={"class_id": classes[i % len(classes)].id if classes else 1},
                filters={}, report_format=fmt,
                generated_by=super_admin, generation_time=Decimal(str(round(rng.uniform(0.2, 30), 2))),
                is_successful=True,
            )
            for i, (n, rt, fmt) in enumerate(
                [
                    ("Student Performance", "student_performance", "pdf"),
                    ("Class Performance", "class_performance", "excel"),
                    ("Teacher Performance", "teacher_performance", "pdf"),
                    ("Attendance Summary", "attendance", "csv"),
                    ("Fee Collection", "fee_collection", "pdf"),
                    ("Academic Progress", "academic_progress", "json"),
                    ("Financial Overview", "financial", "excel"),
                ]
            )
        ],
        label="Report",
    )

    event_types = [
        "login", "logout", "page_view", "feature_use", "data_access",
        "report_generated", "payment_made", "assignment_submitted",
        "attendance_marked", "message_sent",
    ]
    insert(
        AnalyticsEvent,
        [
            AnalyticsEvent(
                user=users[i % len(users)], event_type=event_types[i % len(event_types)],
                event_data={"path": f"/api/v1/feature/{i % 40}", "duration_ms": rng.randint(1, 900)},
                ip_address=f"10.0.{i % 255}.{(i // 255) % 255}",
                user_agent="adom-loadtest/1.0", session_id=f"sess-{i % 2000:05d}",
            )
            for i in range(min(40000, scale.students * 8))
        ],
        label="AnalyticsEvent",
    )

    insert(
        AuditLog,
        [
            AuditLog(
                user=users[i % len(users)], action=["create", "update", "login", "logout"][i % 4],
                model_name=["Student", "Teacher", "Payment", "Attendance"][i % 4],
                object_id=str(rng.randint(1, 100000)),
                details={"ip": f"10.0.0.{i % 255}"},
                ip_address=f"10.0.{i % 255}.{(i // 255) % 255}",
                user_agent="adom-loadtest/1.0",
            )
            for i in range(min(10000, scale.students * 2))
        ],
        label="AuditLog",
    )


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #

def build_manifest(tokens, rng, scale):
    from students.models import Class, Student
    from timetable.models import TimeSlot

    students = list(Student.objects.order_by("id").values("id", "student_id", "current_class_id"))
    classes = list(Class.objects.filter(academic_year__is_active=True).order_by("id").values("id", "name"))
    slots = list(
        TimeSlot.objects.filter(is_break=False).order_by("id").values("id", "day", "start_time")
    )

    # Per-class roster. The bulk attendance endpoint validates that every
    # student in the payload can be accessed, and returns them one at a time, so
    # the driver needs real same-class groups rather than a flat id list.
    roster: dict[int, list[int]] = {}
    for s in students:
        if s["current_class_id"]:
            roster.setdefault(s["current_class_id"], []).append(s["id"])

    # A large pool of (student, date) pairs for write scenarios. Dates are in
    # the future so they can never collide with the seeded attendance rows.
    write_dates = [d.isoformat() for d in future_weekdays(180)]
    write_pairs = [
        {"student_id": s["id"], "date": write_dates[i % len(write_dates)]}
        for i, s in enumerate(students)
    ]
    rng.shuffle(write_pairs)

    return {
        "generated_at": datetime.now(dt_timezone.utc).isoformat(),
        "password": PASSWORD,
        "tokens": tokens,
        "scale": scale.summary(),
        "samples": {
            "student_ids": [s["id"] for s in students[:500]],
            "student_id_strings": [s["student_id"] for s in students[:50]],
            "class_ids": [c["id"] for c in classes],
            "class_names": [c["name"] for c in classes],
            "class_rosters": {str(c["id"]): roster.get(c["id"], []) for c in classes},
            "time_slot_ids": [s["id"] for s in slots],
            "students_per_class": scale.students_per_class,
            "attendance_dates": [d.isoformat() for d in recent_weekdays(scale.attendance_days)],
        },
        "write_pairs": write_pairs[:8000],
        "counts": table_counts(),
    }


def table_counts() -> dict[str, int]:
    """Row counts for the interesting app tables, keyed by model name."""
    from django.apps import apps

    interesting = {
        "institution", "institutionmembership", "user", "userprofile",
        "academicyear", "class", "student", "parent", "teacher", "subject",
        "department", "teachersubject", "teacherdepartment", "room", "timeslot",
        "classschedule", "attendance", "classattendance", "teacherattendance",
        "leaverequest", "examtype", "exam", "examsubject", "grade",
        "studentexamresult", "assignment", "feecategory", "feestructure",
        "feestructuredetail", "studentfee", "payment", "receipt",
        "message", "messagerecipient", "announcement", "notification",
        "communicationlog", "book", "bookcategory", "bookborrowing",
        "digitalresource", "studentperformance", "classperformance",
        "teacherperformance", "schoolanalytics", "report", "analyticevent",
        "auditlog", "authtoken",
    }
    counts: dict[str, int] = {}
    for model in apps.get_models():
        if model._meta.model_name not in interesting:
            continue
        try:
            counts[model._meta.model_name] = model.objects.count()
        except Exception:  # table may not exist if migrations are behind
            continue
    return counts


# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("ADOM_REPO", ""),
        help="Path to the ADOM Institute checkout (default: parent of colab/).",
    )
    parser.add_argument(
        "--manifest",
        default=os.environ.get("ADOM_MANIFEST", ""),
        help="Where to write the load-driver manifest JSON.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Flush existing app data first (keeps content types and permissions).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve() if args.repo else default_repo_root()
    if not (repo_root / "manage.py").exists():
        print(f"ERROR: no manage.py in {repo_root}. Pass --repo /path/to/checkout.", file=sys.stderr)
        return 2

    manifest_path = (
        Path(args.manifest).resolve()
        if args.manifest
        else repo_root / ".colab_loadtest" / "manifest.json"
    )

    bootstrap(repo_root)
    sys.path.insert(0, str(repo_root / "colab"))

    from harness.scale import resolve_scale

    scale = resolve_scale()
    rng = random.Random(SEED)

    print("=" * 70)
    print("ADOM Institute :: load-test seeder")
    print("=" * 70)
    print(scale.describe())
    print()

    from django.conf import settings
    from django.core.management import call_command

    engine = settings.DATABASES["default"]["ENGINE"].split(".")[-1]
    print(f"database: {engine} @ {settings.DATABASES['default'].get('HOST', 'n/a')}")
    if engine == "sqlite3":
        print(
            "WARNING: seeding against SQLite. The load numbers will not be "
            "representative -- use PostgreSQL (DB_ENGINE=postgresql).",
            file=sys.stderr,
        )
    print()

    if args.reset:
        with phase("flushing existing data"):
            call_command("flush", "--noinput", verbosity=0)

    total_started = time.perf_counter()
    with phase("tenancy (institutions, years, classes, subjects)"):
        institutions = seed_tenancy(rng, scale)
    with phase("people (users, memberships, students, parents, teachers)"):
        tokens, _parents, _students = seed_people(rng, scale, institutions)
    with phase("teaching load (departments, rooms, slots, timetable)"):
        active_classes = seed_teaching_load(rng, scale)
    with phase("academics (exams, results, assignments)"):
        seed_academics(rng, scale, active_classes)
    with phase("attendance"):
        seed_attendance(rng, scale)
    with phase("fees"):
        seed_fees(rng, scale, active_classes)
    with phase("communication"):
        seed_communication(rng, scale)
    with phase("library"):
        seed_library(rng, scale)
    with phase("analytics"):
        seed_analytics(rng, scale)
    with phase("manifest"):
        manifest = build_manifest(tokens, rng, scale)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Postgres statistics are what the planner uses. Without an explicit
    # ANALYZE after a bulk load, Postgres guesses, and EXPLAIN output is
    # misleading.
    if engine == "postgresql":
        with phase("ANALYZE (planner statistics)"):
            from django.db import connection

            with connection.cursor() as cur:
                cur.execute("ANALYZE")
            connection.close()

    counts = manifest["counts"]
    print()
    print("=" * 70)
    print(f"seeded in {time.perf_counter() - total_started:.1f}s")
    print("=" * 70)
    for name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        if count:
            print(f"  {name:<28} {count:>9,}")
    print(f"  {'TOTAL':<28} {sum(counts.values()):>9,}")
    print()
    print(f"manifest: {manifest_path}")
    print()
    print("Log in with any of:")
    for role, emails in (tokens.get("_emails") or {}).items():
        if emails:
            print(f"  {role:<14} {emails[0]}  /  {PASSWORD}   (+{len(emails) - 1} more)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Print a real traceback to stderr and exit 1. Without this, an
        # exception escaping main() produces a traceback on stderr *and* a
        # nonzero exit, which the notebook reported as a bare
        # "seeding failed - see the output above" while the cause scrolled
        # past in a cell the user was not watching. Keeping the traceback
        # here means the notebook cell can echo it deliberately.
        import traceback

        traceback.print_exc()
        print(
            "\nseeding aborted. The traceback above is the cause; the most "
            "common failures are a database that is not accepting connections "
            "(the seeding cell starts Postgres and waits for it), or a missing "
            "migration (the previous cell runs makemigrations --check).",
            file=sys.stderr,
        )
        raise SystemExit(1)
