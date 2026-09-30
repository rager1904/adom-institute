"""
Scenario catalogue for the ADOM Institute load driver.

A scenario is one request shape. The driver picks from these by weight, so a
run exercises a realistic mix rather than hammering a single URL.

Roles map onto tokens minted by ``seed.py``: ``super_admin``, ``administrator``,
``accountant``, ``teacher``, ``student``, ``parent``. ``None`` means anonymous.

Two things are deliberate here:

* ``teacher_scope`` scenarios. Every scoped queryset in this codebase resolves a
  teacher's visible students through
  ``filter(current_class__schedules__teacher__user=user).distinct()``
  (accounts/permissions.py:225, attendance/views.py:88). That is a four-table
  join with a DISTINCT over the whole attendance table. It is the most
  expensive read in the platform and the first thing that will not scale, so it
  gets its own scenarios instead of being averaged into the mix.
* Write scenarios. Reads are cheap; attendance marking and fee payment are the
  operations a school actually hammers during term. Writes mutate the seeded
  data, which is fine and intended.
* The router root is not a list endpoint. ``adom/urls.py`` mounts each app's
  ``DefaultRouter`` at ``/api/v1/<app>/``, so ``/api/v1/students/`` resolves to
  ``APIRootView``: it answers 200 with the *route list* and never touches a
  table. The rows live one level deeper, at the basename the router registered
  (``/api/v1/students/students/``). Pointing a scenario at the router root
  looks like a healthy 200 while measuring nothing, and because
  ``APIRootView`` only defines ``get``, a POST aimed at one returns 405 --
  so the write scenarios silently never run. ``loadgen.py`` asserts every
  path here resolves to a real route before it measures anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    name: str
    method: str
    path: str
    role: str | None = None
    weight: int = 1
    category: str = "read"
    note: str = ""
    #: Body template. ``{...}`` placeholders are filled from the request context.
    body: str | None = None

    def label(self) -> str:
        who = self.role or "anon"
        return f"{self.name} [{who}]"

    @property
    def key(self) -> str:
        """Identity used for per-scenario results and for the learned page count."""
        return f"{self.name}|{self.role}"

    @property
    def uses_page(self) -> bool:
        """Whether the path interpolates a ``{page}`` token."""
        return "{page}" in self.path


# --------------------------------------------------------------------------- #
# Read scenarios: the list endpoints a dashboard hits constantly
# --------------------------------------------------------------------------- #

READ_SCENARIOS: list[Scenario] = [
    Scenario(
        "students_list", "GET", "/api/v1/students/students/?page={page}", "super_admin", 6,
        note="Default paginated list. Platform admin bypasses tenant scoping.",
    ),
    Scenario(
        "students_filtered", "GET",
        "/api/v1/students/students/?admission_status=approved&ordering=-id&page={page}",
        "administrator", 4,
        note="Filtered + ordered list; exercises the (admission_status, is_active) index.",
    ),
    Scenario(
        "students_search", "GET",
        "/api/v1/students/students/?search={search}&page={page}", "super_admin", 3,
        note="SearchFilter -> icontains across the table. Expect a seq scan at scale.",
    ),
    Scenario(
        "students_detail", "GET", "/api/v1/students/students/{student_id}/", "super_admin", 4,
    ),
    Scenario(
        "attendance_list", "GET", "/api/v1/attendance/attendance/?page={page}", "super_admin", 5,
    ),
    Scenario(
        "attendance_filtered", "GET",
        "/api/v1/attendance/attendance/?status=absent&date={date}&page={page}", "super_admin", 3,
    ),
    Scenario(
        "attendance_summary", "GET",
        "/api/v1/attendance/attendance/summary/?date_from={date_from}&date_to={date}",
        "super_admin", 2,
        note="Conditional aggregate over every attendance row. The heaviest read.",
    ),
    Scenario(
        "student_fees_overdue", "GET",
        "/api/v1/fees/student-fees/?payment_status=overdue&page={page}",
        "accountant", 3,
    ),
    Scenario(
        "student_fees_all", "GET", "/api/v1/fees/student-fees/?page={page}", "administrator", 3,
    ),
    Scenario(
        "payments_list", "GET", "/api/v1/fees/payments/?page={page}", "accountant", 2,
    ),
    Scenario(
        "exam_results", "GET", "/api/v1/academics/student-exam-results/?page={page}",
        "administrator", 2,
    ),
    Scenario(
        "timetable_schedules", "GET", "/api/v1/timetable/schedules/?page={page}",
        "administrator", 2,
    ),
    Scenario(
        "teachers_list", "GET", "/api/v1/teachers/teachers/?page={page}", "administrator", 2,
    ),
    Scenario(
        "parents_list", "GET", "/api/v1/students/parents/?page={page}", "administrator", 1,
    ),
    Scenario(
        "classes_list", "GET", "/api/v1/students/classes/", "administrator", 1,
    ),
    Scenario(
        "users_list", "GET", "/api/v1/accounts/users/?page={page}", "super_admin", 2,
    ),
    Scenario(
        "library_books", "GET", "/api/v1/library/books/?page={page}", "student", 1,
    ),
    Scenario(
        "library_borrowings", "GET", "/api/v1/library/borrowings/?page={page}", "student", 1,
    ),
    Scenario(
        "analytics_reports", "GET", "/api/v1/analytics/reports/?page={page}", "super_admin", 1,
    ),
    Scenario(
        "analytics_school", "GET", "/api/v1/analytics/school-analytics/", "super_admin", 1,
    ),
    Scenario(
        "notifications", "GET", "/api/v1/communication/notifications/?page={page}",
        "student", 2,
    ),
    Scenario(
        "messages", "GET", "/api/v1/communication/messages/?page={page}", "teacher", 2,
    ),
]

# --------------------------------------------------------------------------- #
# Scoped reads: the expensive tenant/role-scoped queries
# --------------------------------------------------------------------------- #

SCOPED_SCENARIOS: list[Scenario] = [
    Scenario(
        "scoped_students_teacher", "GET", "/api/v1/students/students/?page={page}", "teacher", 6,
        category="scoped",
        note="students JOIN classes JOIN schedules JOIN teachers + DISTINCT.",
    ),
    Scenario(
        "scoped_attendance_teacher", "GET", "/api/v1/attendance/attendance/?page={page}", "teacher", 6,
        category="scoped",
        note="Same join shape over the largest table in the schema.",
    ),
    Scenario(
        "scoped_attendance_summary_teacher", "GET",
        "/api/v1/attendance/attendance/summary/?date_from={date_from}&date_to={date}", "teacher", 3,
        category="scoped",
        note="Aggregate on top of the scoped join. Usually the worst endpoint here.",
    ),
    Scenario(
        "scoped_students_parent", "GET", "/api/v1/students/students/", "parent", 3,
        category="scoped",
        note="students JOIN parents, filtered to the logged-in guardian's children.",
    ),
    Scenario(
        "scoped_notifications_student", "GET", "/api/v1/communication/notifications/",
        "student", 2, category="scoped",
    ),
]

# --------------------------------------------------------------------------- #
# Write scenarios
# --------------------------------------------------------------------------- #

WRITE_SCENARIOS: list[Scenario] = [
    Scenario(
        "attendance_create", "POST", "/api/v1/attendance/attendance/", "teacher", 5,
        category="write",
        note=(
            "One attendance row, using a pre-seeded unique (student, date) pair so "
            "the benchmark measures inserts rather than constraint violations."
        ),
        body='{"student": {student_pk}, "date": "{write_date}", "status": "present", "remarks": "lt"}',
    ),
    Scenario(
        "attendance_bulk_create", "POST", "/api/v1/attendance/attendance/bulk_create/", "teacher", 2,
        category="write",
        note=(
            "25 students in one call. The view does Student.objects.get() per row "
            "(attendance/views.py:120) -- a textbook N+1, one query per record."
        ),
        body='{"class_obj": {class_id}, "date": "{write_date}", "attendances": {attendance_block}}',
    ),
]

# --------------------------------------------------------------------------- #
# Page renders (template + context processors + dashboard aggregates)
# --------------------------------------------------------------------------- #

PAGE_SCENARIOS: list[Scenario] = [
    Scenario("page_home", "GET", "/", None, 3, category="page",
             note="Public landing page; counts institutions/students/teachers on every hit."),
    Scenario("page_login", "GET", "/accounts/login/", None, 2, category="page"),
    Scenario("page_swagger", "GET", "/swagger/", None, 1, category="page",
             note="drf-yasg schema render. Heavy on CPU (introspection), not I/O."),
]

ALL_SCENARIOS: list[Scenario] = (
    READ_SCENARIOS + SCOPED_SCENARIOS + WRITE_SCENARIOS + PAGE_SCENARIOS
)

SCENARIOS_BY_NAME: dict[str, Scenario] = {s.name: s for s in ALL_SCENARIOS}


def get_scenarios(
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    categories: list[str] | None = None,
) -> list[Scenario]:
    """Filter the catalogue. Empty/None filters mean 'everything'."""
    selected = list(ALL_SCENARIOS)
    if categories:
        selected = [s for s in selected if s.category in categories]
    if include:
        wanted = set(include)
        selected = [s for s in selected if s.name in wanted]
    if exclude:
        unwanted = set(exclude)
        selected = [s for s in selected if s.name not in unwanted]
    return selected


def describe_catalogue() -> str:
    lines = []
    by_cat: dict[str, list[Scenario]] = {}
    for s in ALL_SCENARIOS:
        by_cat.setdefault(s.category, []).append(s)
    for cat in sorted(by_cat):
        lines.append(f"{cat.upper()} ({len(by_cat[cat])})")
        for s in by_cat[cat]:
            lines.append(
                f"  {s.name:<32} {s.method:<5} {s.role or 'anon':<14} w={s.weight}"
            )
            if s.note:
                lines.append(f"      {s.note}")
        lines.append("")
    return "\n".join(lines)
