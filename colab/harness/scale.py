"""
Auto-sizing of the synthetic dataset to the Colab runtime that is running it.

A Colab standard runtime is ~2 vCPU / 12.7 GB RAM. The high-mem tiers are only
available on paid runtimes (Pro/Pro+). Sizing matters for two opposite reasons:

  * Too small and the numbers are meaningless -- query planners happily
    sequential-scan a 200-row table, so nothing bad ever shows up.
  * Too large and the *generator* starves the runtime, or Postgres evicts shared
    buffers, and you end up measuring the loader instead of the application.

So we pick a tier from total RAM / CPU count, and let any individual knob be
overridden with an ``ADOM_SEED_*`` environment variable. Overrides win.

The derived row counts (attendance, fees, exam results) are the expensive part:
they are multiplicative in ``students``, so ``ADOM_SEED_STUDENTS`` is the knob
that dominates seeding time and database size.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field


def _total_ram_gb() -> float:
    """Total RAM in GiB, or 4.0 if we cannot read /proc/meminfo."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    return 4.0


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@dataclass
class Scale:
    """Row-count targets for the seeder."""

    tier: str
    ram_gb: float
    cpu: int

    institutions: int
    academic_years: int
    classes_per_year: int
    subjects: int
    departments: int
    rooms: int

    students: int
    teachers: int
    staff: int
    parent_ratio: float
    accountant_ratio: float

    attendance_days: int
    teacher_attendance_days: int
    exams: int
    subjects_per_exam: int
    announcements: int
    notifications_per_student: int
    messages_per_teacher: int

    # Populated by describe(); not user-facing knobs.
    derived: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- helpers

    @property
    def parents(self) -> int:
        return int(self.students * self.parent_ratio)

    @property
    def accountants(self) -> int:
        # One or two per institution, floored so finance endpoints are exercised.
        return max(2, int(self.students * self.accountant_ratio))

    @property
    def students_per_class(self) -> int:
        total_classes = max(1, self.classes_per_year * self.academic_years * self.institutions)
        return max(1, self.students // total_classes)

    def describe(self) -> str:
        d = asdict(self)
        d.pop("derived", None)
        lines = [
            f"tier              {self.tier}",
            f"runtime           {self.cpu} vCPU / {self.ram_gb:.1f} GB RAM",
            "",
            "tenancy",
            f"  institutions    {self.institutions}",
            f"  academic years  {self.academic_years} per institution "
            f"({self.academic_years * self.institutions} total)",
            f"  classes         {self.classes_per_year} per year "
            f"({self.classes_per_year * self.academic_years * self.institutions} total)",
            f"  ~per class      {self.students_per_class} students",
            "",
            "people",
            f"  students        {self.students}",
            f"  teachers        {self.teachers}",
            f"  parents         {self.parents}",
            f"  accountants     {self.accountants}",
            f"  staff/admin     {self.staff}",
            "",
            "academic",
            f"  subjects        {self.subjects}",
            f"  departments     {self.departments}",
            f"  exams           {self.exams} x {self.subjects_per_exam} subjects",
            "",
            "generated rows (approx)",
            f"  attendance      {self.derived.get('attendance_rows', 0)}",
            f"  exam results    {self.derived.get('exam_result_rows', 0)}",
            f"  student fees    {self.derived.get('student_fee_rows', 0)}",
            f"  payments        {self.derived.get('payment_rows', 0)}",
            f"  notifications   {self.derived.get('notification_rows', 0)}",
            f"  messages        {self.derived.get('message_rows', 0)}",
        ]
        return "\n".join(lines)

    def summary(self) -> dict:
        return {
            "tier": self.tier,
            "ram_gb": round(self.ram_gb, 1),
            "cpu": self.cpu,
            **{k: v for k, v in asdict(self).items() if k not in {"derived", "ram_gb", "cpu", "tier"}},
            "derived": dict(self.derived),
        }


# Tier definitions. Keyed smallest-first; the first tier whose requirements are
# met wins. `ram_gb` is a floor, not a target -- Colab reports the host's RAM,
# which can be higher than the billed allocation.
TIERS: list[dict] = [
    {
        "name": "standard",
        "min_ram_gb": 0.0,
        "min_cpu": 0,
        "institutions": 2,
        "academic_years": 2,
        "classes_per_year": 10,
        "subjects": 20,
        "departments": 6,
        "rooms": 15,
        "students": 2000,
        "teachers": 120,
        "staff": 8,
        "parent_ratio": 0.55,
        "accountant_ratio": 0.0,
        "attendance_days": 20,
        "teacher_attendance_days": 20,
        "exams": 1,
        "subjects_per_exam": 5,
        "announcements": 15,
        "notifications_per_student": 3,
        "messages_per_teacher": 8,
    },
    {
        "name": "highmem",
        "min_ram_gb": 20.0,
        "min_cpu": 4,
        "institutions": 3,
        "academic_years": 2,
        "classes_per_year": 25,
        "subjects": 35,
        "departments": 10,
        "rooms": 30,
        "students": 6000,
        "teachers": 300,
        "staff": 14,
        "parent_ratio": 0.55,
        "accountant_ratio": 0.0,
        "attendance_days": 30,
        "teacher_attendance_days": 30,
        "exams": 2,
        "subjects_per_exam": 6,
        "announcements": 25,
        "notifications_per_student": 3,
        "messages_per_teacher": 8,
    },
    {
        "name": "ultra",
        "min_ram_gb": 45.0,
        "min_cpu": 8,
        "institutions": 4,
        "academic_years": 2,
        "classes_per_year": 50,
        "subjects": 60,
        "departments": 16,
        "rooms": 60,
        "students": 20000,
        "teachers": 800,
        "staff": 24,
        "parent_ratio": 0.55,
        "accountant_ratio": 0.0,
        "attendance_days": 60,
        "teacher_attendance_days": 60,
        "exams": 2,
        "subjects_per_exam": 8,
        "announcements": 40,
        "notifications_per_student": 3,
        "messages_per_teacher": 8,
    },
]

# Maps an ADOM_SEED_<KEY> env var onto a Scale field name.
_OVERRIDABLE = {
    "ADOM_SEED_INSTITUTIONS": "institutions",
    "ADOM_SEED_ACADEMIC_YEARS": "academic_years",
    "ADOM_SEED_CLASSES_PER_YEAR": "classes_per_year",
    "ADOM_SEED_SUBJECTS": "subjects",
    "ADOM_SEED_DEPARTMENTS": "departments",
    "ADOM_SEED_ROOMS": "rooms",
    "ADOM_SEED_STUDENTS": "students",
    "ADOM_SEED_TEACHERS": "teachers",
    "ADOM_SEED_STAFF": "staff",
    "ADOM_SEED_ATTENDANCE_DAYS": "attendance_days",
    "ADOM_SEED_TEACHER_ATTENDANCE_DAYS": "teacher_attendance_days",
    "ADOM_SEED_EXAMS": "exams",
    "ADOM_SEED_SUBJECTS_PER_EXAM": "subjects_per_exam",
    "ADOM_SEED_ANNOUNCEMENTS": "announcements",
    "ADOM_SEED_NOTIFICATIONS_PER_STUDENT": "notifications_per_student",
    "ADOM_SEED_MESSAGES_PER_TEACHER": "messages_per_teacher",
}


def _tier_for(ram_gb: float, cpu: int) -> dict:
    # Iterate largest-first so the biggest satisfied tier wins.
    for tier in sorted(TIERS, key=lambda t: t["min_ram_gb"], reverse=True):
        if ram_gb >= tier["min_ram_gb"] and cpu >= tier["min_cpu"]:
            return tier
    return TIERS[0]


def resolve_scale() -> Scale:
    """Pick a tier, apply env overrides, and compute derived row counts."""
    ram_gb = _total_ram_gb()
    cpu = os.cpu_count() or 2
    tier = _tier_for(ram_gb, cpu)

    scale = Scale(
        tier=tier["name"],
        ram_gb=ram_gb,
        cpu=cpu,
        **{k: v for k, v in tier.items() if k not in {"name", "min_ram_gb", "min_cpu"}},
    )

    for env_name, field_name in _OVERRIDABLE.items():
        override = _env_int(env_name)
        if override is not None:
            setattr(scale, field_name, override)

    # Guard rails: these must be >= 1 for the seeder to produce a usable dataset.
    scale.institutions = max(1, scale.institutions)
    scale.academic_years = max(1, scale.academic_years)
    scale.classes_per_year = max(1, scale.classes_per_year)
    scale.subjects = max(1, scale.subjects)
    scale.departments = max(1, scale.departments)
    scale.rooms = max(1, scale.rooms)
    scale.students = max(1, scale.students)
    scale.teachers = max(1, scale.teachers)
    scale.staff = max(1, scale.staff)
    scale.exams = max(1, scale.exams)
    scale.subjects_per_exam = max(1, scale.subjects_per_exam)

    # One AcademicYear per (institution, year) -- AcademicYear.name is globally
    # unique, so years cannot be shared between institutions. Classes are then
    # created per academic year, which multiplies by institution count too.
    total_academic_years = scale.institutions * scale.academic_years
    total_classes = scale.academic_years * scale.classes_per_year * scale.institutions
    per_student_fee_slots = 3
    scale.derived = {
        "academic_years_total": total_academic_years,
        "classes_total": total_classes,
        "attendance_rows": scale.students * scale.attendance_days,
        "class_attendance_rows": total_classes * min(scale.attendance_days, 30),
        "teacher_attendance_rows": scale.teachers * scale.teacher_attendance_days,
        "exam_rows": total_classes * scale.exams,
        "exam_subject_rows": total_classes * scale.exams * scale.subjects_per_exam,
        "exam_result_rows": scale.students * scale.subjects_per_exam * scale.exams,
        "student_fee_rows": scale.students * per_student_fee_slots,
        "payment_rows": int(scale.students * per_student_fee_slots * 0.7),
        "receipt_rows": int(scale.students * per_student_fee_slots * 0.5),
        "notification_rows": scale.students * scale.notifications_per_student,
        "message_rows": scale.teachers * scale.messages_per_teacher,
        "user_rows": (
            scale.students + scale.parents + scale.teachers + scale.accountants + scale.staff
        ),
    }
    return scale


if __name__ == "__main__":
    print(resolve_scale().describe())
