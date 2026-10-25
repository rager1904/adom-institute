# ADOM Institute — Django Audit Report

**Date:** 2026-10-22
**Repository:** `D:\adom-institute-main\adom-institute-main`
**Interpreter:** `.venv-dev\Scripts\python.exe` (Python 3.10, Django 4.2)
**Scope:** correctness of flows, broken features, missing functionality, and security of the web UI and DRF API.

---

## 1. Method

| Activity | Result |
| --- | --- |
| `manage.py check` | **0 issues** (before and after changes) |
| Full test suite (baseline) | **224 tests — 4 failures, 1 error** (all pre-existing, see §6) |
| Project mapping | 12 apps: `academics`, `accounts`, `adom`, `adom_institute`, `analytics`, `attendance`, `communication`, `fees`, `library`, `students`, `teachers`, `timetable` |
| Static analysis | AST scan of every view/CBV/ViewSet for permissions & queryset scoping; template `{% url %}` reversal check; orphan-template detection; JS AJAX endpoint check |
| Empirical probes | Live HTTP probes against a throwaway test DB for permission bypasses, cross-tenant reads, upload validation and media delivery |
| Verification after fixes | 20/20 permission/upload probes, 12/12 report-protection probes, 125/125 targeted tests |

---

## 2. Executive summary

Three **Critical** and several **High** issues were found and fixed:

1. **Any signed-in student could create, edit and delete staff, catalogue and analytics data through the REST API** (teachers, subjects, departments, rooms, time slots, schedules, analytics reports).
2. **The API bypassed file-upload validation** — a `.exe` payload was accepted and written to disk as an assignment attachment and as a student submission.
3. **`POST /api/v1/library/digital-resources/` returned HTTP 500 for every request** because the serializer declared a field that was missing from `Meta.fields`. The endpoint was completely unusable.
4. **Generated analytics reports were served from the public `/media/reports/` URL** with a raw `file_path.url`, exposing sensitive institutional data and bypassing tenant scoping.

All four are fixed and verified. Remaining findings are documented in §7.

---

## 3. Critical findings (fixed)

### C1 — Students could mutate staff / catalogue / schedule / analytics data via the API
**Where:** `teachers/views.py` (`TeacherViewSet`, `SubjectViewSet`, `DepartmentViewSet`), `timetable/views.py` (`RoomViewSet`, `TimeSlotViewSet`, `ClassScheduleViewSet`), `analytics/views.py` (all ViewSets).

These ViewSets had either no `permission_classes` (falling back to the DRF default `IsAuthenticated`) or only `IsAuthenticated`. A student token could therefore:

* `POST` / `DELETE` `/api/v1/teachers/teachers/`
* `POST` / `DELETE` `/api/v1/teachers/subjects/` and `/departments/`
* `POST` / `PATCH` `/api/v1/timetable/rooms/`, `/timeslots/`, `/schedules/`
* `POST` / `DELETE` `/api/v1/analytics/reports/`

**Before (probe):** all of the above returned `201`/`204` for a student account.

**Fix:** writes are now restricted to institution administrators (`IsPlatformOrInstitutionAdmin`). Reads remain available to signed-in users, matching the existing library/`academics` pattern.

**After (probe):** all of the above return `403` for students; administrator writes still return `201`.

### C2 — API upload validation bypass (arbitrary file types)
**Where:** `academics/serializers.py`, `library/serializers.py`.

`AssignmentSerializer.attachment`, `StudentAssignmentSerializer.submission_file` and `DigitalResourceSerializer.file` were declared as plain `serializers.FileField(...)`. Declaring a field on a `ModelSerializer` **replaces** the model field, so the model's `document_upload_validators` / `resource_upload_validators` were silently dropped.

**Before (probe):**

```
POST /api/v1/academics/student-assignments/  submission_file=payload.exe -> 201
   SAVED -> media/assignment_submissions/payload.exe (66 bytes), on disk: True
POST /api/v1/academics/assignments/          attachment=payload3.exe     -> 201
   SAVED -> media/assignments/payload3.exe
```

**Fix:** the declared fields now carry `document_upload_validators` / `resource_upload_validators` (safe-filename check, extension allow-list, size limit).

**After (probe):** both `.exe` uploads return `400`; a valid `.pdf` still returns `201`.

### C3 — `POST /api/v1/library/digital-resources/` was a hard 500
**Where:** `library/serializers.py` — `DigitalResourceSerializer` declared `file` but omitted it from `Meta.fields`.

Every create/update raised:

```
AssertionError: The field 'file' was declared on serializer DigitalResourceSerializer,
but has not been included in the 'fields' option.
```

`GET` on an empty list coincidentally returned `200`, which masked the bug until a record existed or a create was attempted.

**Fix:** `'file'` added to `Meta.fields` (it is `write_only`, so it is still never returned) and given the resource validators.

**After (probe):** `.pdf` upload returns `201`; list returns `200`.

### C4 — Generated reports exposed on the public media route
**Where:** `analytics/serializers.py` (`ReportSerializer.get_file_url` → `obj.file_path.url`), `templates/analytics/report_detail_modern.html`, `deploy/oci/nginx/adom.conf`, `adom/protected_media.py`.

Report files live under `MEDIA_ROOT/reports/` and were served directly by `/media/`. The nginx config only blocked `assignments/`, `assignment_submissions/` and `library/digital/`. The report web views were also **not** institution-scoped.

**Fix:**
* Added an authenticated, inline-only viewer `analytics/reports/<pk>/file/` (`analytics.views.report_file`) using `protected_file_response`.
* `ReportSerializer.file_url` now returns that viewer URL.
* `ReportListView` / `ReportDetailView` / `ReportUpdateView` / `ReportDeleteView` are institution-scoped.
* `reports/` and `knowledge/` added to `_PROTECTED_ROOT_DIRS` and to the nginx `return 404` block.

**After (probe):** owner admin `200` inline/no-store; other institution admin `403`; student `403`; anonymous `302` to login; raw `/media/reports/…` refused.

---

## 4. High findings (fixed)

| ID | Finding | Fix |
| --- | --- | --- |
| H1 | `TeacherViewSet.statistics` counted teachers globally, leaking cross-tenant totals | Now derives counts from the caller-scoped `get_queryset()` |
| H2 | Analytics API ViewSets returned every institution's performance and school-analytics rows | Added `scope_to_institution()` filtering by `academic_year__institution_id` and by the report author's memberships |
| H3 | `ReportListView`/`DetailView`/`UpdateView`/`DeleteView` exposed every tenant's reports | Institution-scoped `get_queryset()` |
| H4 | `templates/analytics/report_list.html` referenced non-existent `report.file` / `report.status`, producing a dead download link | Now uses `report.is_successful`, `report.file_path` and the authenticated viewer URL |

---

## 5. Files changed

| File | Change |
| --- | --- |
| `library/serializers.py` | Added `file` to `Meta.fields`; attached `resource_upload_validators` |
| `academics/serializers.py` | Attached `document_upload_validators` to `attachment` and `submission_file` |
| `teachers/views.py` | Write permissions on all three ViewSets; scoped `statistics` |
| `timetable/views.py` | Admin-only writes on `RoomViewSet`, `TimeSlotViewSet`, `ClassScheduleViewSet` |
| `analytics/views.py` | Admin-only writes + institution scoping on all API ViewSets; scoped report web views; new `report_file` viewer |
| `analytics/serializers.py` | `file_url` now points at the authenticated viewer |
| `analytics/urls.py` | New `reports/<pk>/file/` route |
| `adom/protected_media.py` | `reports/` and `knowledge/` added to protected root dirs |
| `deploy/oci/nginx/adom.conf` | `return 404` for `/media/reports/` and `/media/knowledge/` |
| `templates/analytics/report_detail_modern.html` | Authenticated viewer link |
| `templates/analytics/report_list.html` | Corrected report fields + viewer link |

---

## 6. Pre-existing test failures (not caused by this audit)

Baseline and post-fix runs are identical: **224 tests, 4 failures, 1 error**.

| Test | Cause |
| --- | --- |
| `accounts.test_page_routes.ADOMInstitutePageRouteTests.test_public_home_page_exists` | `Missing staticfiles manifest entry for 'images/home.png'` — `CompressedManifestStaticFilesStorage` is active while `collectstatic` has not run in dev. |
| `accounts.tests.UserRegistrationFormTests` (4 tests: student identifiers, signup membership role, teacher membership, institution register redirect) | Stale expectations around institution-approval gating and the post-registration redirect. |

`manage.py check` reports no issues.

---

## 7. Remaining findings / recommendations (not changed)

These need product decisions or larger changes and were deliberately left untouched.

### 7.1 Sensitive media still publicly served
`leave_documents/`, `message_attachments/`, `announcement_attachments/` and `receipts/` are still reachable under `/media/`. Templates link to them with raw `.url`, so blocking them without first adding authenticated viewers would break the UI. Recommended: add inline viewers (as done for reports) and then extend `_PROTECTED_ROOT_DIRS` + nginx.

### 7.2 Object storage bypasses all local media protection
When `USE_S3=True`, Django renders full object-storage URLs and nginx/Django protections are never consulted. Bucket policy (private + signed URLs) must carry the same guarantees.

### 7.3 Global catalogue models
`Subject`, `Department`, `Room` and `TimeSlot` have no `institution` foreign key and globally unique `name`/`code`. Two institutions cannot use the same subject code, and every institution can read every other institution's catalogue. If multi-tenancy of the catalogue is intended, add `institution` FKs and scope the querysets.

### 7.4 Orphaned template with a broken URL
`templates/academics/student_assignment_list.html` references `{% url 'academics:student_assignment_submit' %}`, which does not exist. The template is **not rendered** (the live view uses `student_assignment_list_modern.html`), so this is currently dead code; it will break if the template is ever re-wired. Either delete the template or add the submit route.

### 7.5 Static files in development
The home page 500 in dev is caused by the manifest storage. Either run `collectstatic`, or set `WHITENOISE_MANIFEST_STRICT = False` (or use `StaticFilesStorage`) while `DEBUG=True`.

### 7.6 DRF defaults
`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` is safe-by-default for authentication but not for authorization. Prefer a deny-by-default object/permission policy and explicit `permission_classes` on every ViewSet; C1 arose because several ViewSets relied on the default.

---

## 8. Verification evidence

```
manage.py check                       -> System check identified no issues (0 silenced)
Permission/upload probes              -> 20/20 passed
Report protection probes              -> 12/12 passed
Targeted tests (125 tests)            -> OK
Full suite                            -> 224 tests, 4 failures, 1 error (unchanged baseline)
```

Key probe results:

* Student writes to `teachers/*`, `timetable/*`, `analytics/reports/` → **403**
* Admin writes to the same endpoints → **201**
* `.exe` upload to `student-assignments` / `assignments` → **400**
* `.pdf` upload to `student-assignments` / `digital-resources` → **201**
* `POST /api/v1/library/digital-resources/` → **201** (previously **500**)
* Report file: owner **200** inline/no-store, other tenant **403**, student **403**, anonymous **302**

---

## 9. Library module audit (second pass)

**Scope:** `library` app only - models, views, forms, serializers, templates, DRF API.
**Tests added:** `library/test_audit_fixes.py` (46 tests).
**Result:** `manage.py check` -> 0 issues; `manage.py test library` -> **141 tests, OK**; full project suite -> **274 tests, 4 failures** (the same pre-existing `accounts.tests.UserRegistrationFormTests` failures documented in section 6).


### 9.1 Critical / High findings (fixed)

| # | Finding | Fix |
| --- | --- | --- |
| L1 | The staff borrowing form rendered `form.user`, but the field is `borrower` - the borrower picker never appeared and staff could not create a loan. | `templates/library/borrowing_form.html` now renders `form.borrower`. |
| L2 | `POST /api/v1/library/reservations/` always returned **500**: `expiry_date` is `NOT NULL` and the viewset never set it. | `BookReservationViewSet.perform_create` sets `expiry_date` from `settings.reservation_duration_hours`. |
| L3 | `GET /api/v1/library/statistics/user_activity/` returned **500**: the serializer was handed an already-serialized dict but expected a `User` instance. | `LibraryStatisticsViewSet.user_activity` passes the `User` instance. |
| L4 | The bulk import wizard was dead: the page posted to `/library/bulk-import/parse|validate|execute/`, none of which exist (404), and read a CSRF token from a `<form>` that did not exist. | `templates/library/bulk_import.html` is now a real server-rendered form posting to the view. |
| L5 | A single bad CSV row aborted the whole import (and a raw DB error was shown to the user); non-UTF-8 spreadsheets raised `UnicodeDecodeError`; `int()`/`float()` on a blank or non-numeric cell raised `ValueError`. | `bulk_import_books` decodes `utf-8-sig`/`cp1252`/`latin-1`, validates every row, skips and reports bad rows, and saves each row in its own `transaction.atomic()` block. |
| L6 | The catalogue, borrowing and reservation lists ignored their own filter fields, so the filters on screen did nothing. | `BookListView`, `BookBorrowingListView` and `BookReservationListView` now honour `search`, `status`, `availability`, `category` and `date_range`. |
| L7 | `AdminRequiredMixin` accepted `user_type == 'administrator'` only, while `is_admin_user`/`IsPlatformOrInstitutionAdmin` also accept an active institution membership with an admin role. The same person could manage the library through the function views and the API but was refused by the class based views. | `AdminRequiredMixin.test_func` now uses `is_admin_user`, so institution owners are administrators everywhere. |
| L8 | `TagListField.render()` emitted a hidden `False` input, so every book silently saved the literal tag "False". | The custom `render()` was removed. |
| L9 | The library settings page was static markup: `require_approval` and `enable_delivery` could not be read or changed, and the late fee shown in reports came from a different source than `LibrarySettings.late_fee_per_day`. | `library_settings` renders and saves the real `LibrarySettingsForm`; the late fee has a single source. |
| L10 | The return-request form did not expose the loan it referred to, so a staff member had to pick the loan blind, and any user could file a request for somebody else's loan. | `BookReturnRequestForm` has an explicit `borrowing` field with ownership, duplicate and collection checks. |
| L11 | The reservation form showed a "priority" selector and checkboxes that were never submitted. | Replaced with the real `fulfillment_method`, `delivery_address` and `delivery_phone` fields (delivery only offered when `enable_delivery` is on). |
| L12 | The book edit form posted `language`, `tags` and `total_copies`, which are not model fields; the real fields (`availability`, `condition`, `price`, `is_active`) were missing. | The form was rewritten against the model. |
| L13 | Templates used `user.username`, but `accounts.User` has no `username` column, so the reviewer pages rendered blank names. | All library templates use the email address. |
| L14 | Returning a book marked it `available` even when a reservation was waiting for it. | `BookBorrowing.return_book()` restores `reserved` while an open reservation exists. |

### 9.2 Dead or misleading UI removed

The book list and the digital resource list carried bulk-action bars, checkboxes and modals that were never wired to a working endpoint (the borrow/reserve modals posted nowhere and the bulk actions returned 404). They were replaced with a single working "Borrow" link that pre-selects the book (`?book=<id>`).

### 9.3 Remaining findings (not changed)

| Finding | Why it was left |
| --- | --- |
| The library API is mounted twice: `/api/v1/library/...` (`adom/urls.py`) and `/library/api/...` (`library/urls.py`). | Both paths point at the same views with the same permissions; removing one could break unknown clients. Recommended: keep `/api/v1/library/` only. |
| `templates/library/book_detail.html` is orphaned - `BookDetailView` renders `book_detail_modern.html`. | Dead but harmless; recommended: delete it. |
| The library models are global (`Book`, `BookCategory`) with no `institution` column. | A tenant boundary change needs a migration and a data backfill; see section 7.3. |
