# ADOM Institute Frontend Endpoint Completion Plan

Last updated: 2026-06-16

## Purpose

This plan is for the next development session. The backend surface is now broad, but several backend/API features either have no proper frontend, have only basic CRUD pages, or are not connected clearly in the role-specific navigation. The goal is to finish the user-facing product layer so ADOM Institute feels like a complete school platform instead of a backend-heavy Django project.

Primary objective:

- Every important backend feature should have a working, role-aware, mobile-conscious frontend endpoint.
- Every visible page should dynamically fetch scoped data for the logged-in user.
- Students, teachers, parents, accountants, librarians, and administrators should only see workflows relevant to them.

## Current Status

Verified foundation:

- Role-aware base shell exists in `templates/base.html`.
- Core apps have web routes: accounts, students, teachers, academics, attendance, fees, communication, timetable, library, analytics.
- `adom_institute` has API endpoints and the Accounts AI Hub, but not a full dedicated frontend module.
- Full Django test suite passed with 62 tests after the latest student-list fix.

Known recent fix:

- Fixed `/students/students/` template crash caused by `timesince:now`.
- Added `Student.age` model property.
- Updated `templates/students/student_list.html` and `templates/students/student_detail.html`.

## Product Rule For Next Session

Do not start by adding more backend models unless a frontend endpoint is blocked by missing data. The next session should prioritize completing pages, route coverage, and role-specific workflows.

## Priority 0: Broken Or Missing Frontend Endpoints

### 1. ADOM Institute Frontend Module

Current:

- API exists under `/api/v1/adom-institute/`.
- AI Hub exists at `/accounts/ai-hub/`.
- Started dedicated frontend routes under `/adom-institute/`.

Needed pages:

- Done: `/adom-institute/` dashboard
- Done: `/adom-institute/knowledge/` knowledge document list
- Done: `/adom-institute/knowledge/search/` RAG search page
- Done: `/adom-institute/knowledge/upload/` upload knowledge document
- Done: `/adom-institute/knowledge/<id>/` document detail with chunks, checksum, processing status
- Done: `/adom-institute/knowledge/<id>/process/` POST action UI
- Done: `/adom-institute/agents/` agent catalog
- Done: `/adom-institute/tasks/` agent task list
- Done: `/adom-institute/tasks/create/` create task
- Done: `/adom-institute/tasks/<id>/` task detail
- Done: `/adom-institute/conversations/` conversation list
- Done: `/adom-institute/conversations/create/` create conversation
- Done: `/adom-institute/conversations/<id>/` conversation detail
- Done: `/adom-institute/conversations/<id>/messages/create/` add message
- Done: `/adom-institute/usage/` usage ledger page
- Done: `/adom-institute/consent/` AI consent preferences

Implementation approach:

- Add class-based views in `adom_institute/views.py` for template pages.
- Add forms in `adom_institute/forms.py`.
- Add templates under `templates/adom_institute/`.
- Reuse the existing ADOM Institute design shell and dashboard cards.
- Keep model execution open-source-only. Do not integrate GPT.

Acceptance checks:

- Done: ADOM Institute frontend route tests cover dashboard, knowledge library, and knowledge search.
- Done: Teacher/admin can upload a `.txt` knowledge document.
- Done: Teacher/admin can trigger processing.
- Search returns scoped chunks.
- Done: Teacher/admin can create a scoped agent task from the frontend.
- Done: Users can view scoped usage ledger entries and create consent preferences.
- Done: Users can create scoped AI conversations and add messages.
- Student can see only their own conversations/tasks.
- Admin sees institution-level AI usage.
- Unauthorized users cannot create knowledge documents or tasks for another institution.

### 2. LMS/Course Frontend Gap

Current:

- Academics has exams, assignments, submissions, and grade pages.
- There is no course/module/lesson frontend experience.

Needed pages:

- Started: `/academics/courses/` course dashboard mapped to existing `Class` records.
- Started: `/academics/courses/<id>/` course detail with assignments, exams, and learner count.
- Lesson/module list page.
- Lesson detail page.
- Teacher course analytics page.
- Student course progress page.

Implementation approach:

- First version can use existing `Class`, `Subject`, `Assignment`, `Exam`, `DigitalResource`.
- Avoid adding a large new LMS schema immediately.
- Create frontend views that compose existing data into course-like pages.
- Later add real `Course`, `Module`, `Lesson`, `LearningOutcome` models.

Acceptance checks:

- Started: Student sees only courses/classes they belong to.
- Started: Teacher sees only courses/classes they teach.
- Admin sees institution courses.
- Started: Course page shows assignments and exams.
- Done: Course page shows assignments, exams, resources, attendance summary, and progress.

### 3. Scholarship & Opportunities Frontend

Current:

- Agent definition exists.
- No frontend pages exist.

Needed pages:

- Started: `/adom-institute/opportunities/`
- Opportunity list
- Opportunity detail
- Saved opportunities
- Eligibility checklist
- Admin import/source-management page

Implementation approach:

- Start with manually managed opportunities or JSON-backed seed data.
- Later connect crawler/API ingestion.
- Keep student profile matching simple at first: grade level, location, interests, deadline.

Acceptance checks:

- Started: Student sees opportunity matching task history.
- Admin can add opportunity records.
- Student can save an opportunity.
- Deadlines and eligibility are visible.

## Priority 1: Existing Pages That Need Frontend Modernization

### 4. Student Frontend

Routes:

- `/students/`
- `/students/portal/` - done: scoped student/parent portal with progress, attendance, fees, deadlines, messages, and ADOM Institute links.
- `/students/students/`
- `/students/students/<id>/`
- `/students/classes/`
- `/students/parents/`

Needed improvements:

- Replace generic admin table feel with role-specific cards.
- Add student portal view: GPA, attendance, upcoming exams, assignments, fees, AI recommendations. Initial portal is done using existing performance, attendance, exam, assignment, fee, message, and AI task data.
- Done: `/fees/my/`, `/attendance/my/`, and `/academics/my/` are linked from student/parent navigation and dashboard quick actions.
- Parent view should say "My Children" and show child progress, fees, attendance, messages. Initial parent portal label and scoped child visibility are covered by tests.
- Student list should be mobile-friendly with card layout on small screens.

Acceptance checks:

- Student cannot see global student directory.
- Parent sees only linked children. Portal route has regression coverage.
- Teacher sees only students in their classes.
- Admin sees institution-scoped list.

### 5. Teacher Frontend

Routes:

- `/teachers/`
- `/teachers/my/` - done: role-scoped teaching workspace.
- `/teachers/teachers/`
- `/teachers/subjects/`
- `/teachers/departments/`

Needed improvements:

- Teacher dashboard should prioritize classes today, grading queue, attendance pending, course analytics. Initial `/teachers/my/` workspace is done.
- Teacher profile should not say "Add Teacher" or show admin-only operations.
- Subject and department pages should be useful to teachers but admin-only for management actions.

Acceptance checks:

- Teacher sees teaching workflows, not accountant/admin workflows. `/teachers/my/` is linked from sidebar and covered by a scoping test.
- Admin sees management actions.
- Teacher detail page is role-sensitive.

### 6. Academics Frontend

Routes:

- `/academics/`
- `/academics/my/` - done: student/parent scoped academic self-service page.
- `/academics/grading/` - done: teacher grading queue.
- `/academics/exams/`
- `/academics/assignments/`
- `/academics/student-assignments/`

Needed improvements:

- Modern assessment builder page.
- Rubric/marking UI.
- Student assignment submission flow with clear status.
- Done: My Academics page shows assignments, submissions, exams, and results.
- Teacher grading queue page. Done through `/academics/grading/` with inline grade/feedback forms.
- Student results page.

Acceptance checks:

- Student can submit and review own assignments.
- Teacher can grade assigned submissions. Covered by grading queue route and POST test.
- Parent can view child academic progress read-only.
- Admin can audit all institution academic records.

### 7. Fees Frontend

Routes:

- `/fees/`
- `/fees/my/` - done: student/parent scoped fee self-service page.
- `/fees/student-fees/`
- `/fees/payments/`
- `/fees/receipts/` - done: role-scoped receipt archive frontend.
- `/fees/receipts/<id>/` - done: receipt detail frontend linked from payment detail.
- `/fees/bulk-fee-generation/`
- `/fees/bulk-payment/`
- `/fees/reports/`

Needed improvements:

- Accountant dashboard with collections, overdue balances, aging, recent payments.
- Student/parent fee page with outstanding balance and receipts. Receipt self-service is started through the role-scoped receipt archive.
- Done: My Fees page shows balances, fee items, recent payments, and receipts.
- Payment form should clearly show outstanding amount and block overpayment before submit.
- Receipt detail/download page. Detail view is done; PDF/download polish remains.

Acceptance checks:

- Accountant can manage payments.
- Student/parent cannot create payments unless intended.
- Student/parent can view their own balances and receipts only. Route-scoped receipt access is covered by existing queryset permissions.

### 8. Library Frontend

Routes:

- `/library/`
- `/library/books/`
- `/library/resources/` - done: teacher/admin resource workspace.
- `/library/resources/upload/` - done: teacher/admin digital resource upload.
- `/library/digital-resources/`
- `/library/borrowings/`
- `/library/reservations/`
- `/library/barcode-scan/`
- `/library/reports/`
- `/library/settings/`

Needed improvements:

- Done: `/library/discover/` student discovery page for digital resources.
- Teacher upload/resource organization page. Done through `/library/resources/` and `/library/resources/upload/`.
- Librarian dashboard with borrowings, overdue books, reservations.
- Connect digital resources to AI knowledge ingestion where appropriate.

Acceptance checks:

- Done: Student sees downloadable/visible resources only.
- Teacher/admin can upload resources. Covered by upload route test.
- Librarian/admin can manage borrowings and reservations.

### 9. Communication Frontend

Routes:

- `/communication/inbox/` - done: role-scoped received-message inbox with unread/important summary.
- `/communication/messages/`
- `/communication/announcements/`
- `/communication/notifications/`
- `/communication/email-templates/`
- `/communication/sms-templates/`
- `/communication/logs/`
- `/communication/reports/`

Needed improvements:

- Inbox-like message layout. Initial `/communication/inbox/` frontend is done and linked from the dashboard.
- Announcement composer with audience targeting.
- Notification preferences page.
- Delivery status report page.
- Template preview before send.

Acceptance checks:

- Student/parent sees only relevant messages. Inbox route has coverage proving unrelated recipient messages are hidden.
- Teacher can message assigned classes/parents if allowed.
- Admin can audit delivery logs.

### 10. Timetable Frontend

Routes:

- `/timetable/`
- `/timetable/my-schedule/` - done: role-scoped weekly timetable page.
- `/timetable/rooms/`
- `/timetable/timeslots/`
- `/timetable/schedules/`
- `/timetable/calendar/`

Needed improvements:

- Calendar-grade timetable view.
- Role-specific timetable:
  - student: my class schedule - initial page done.
  - teacher: my teaching schedule - covered by shared scoped page.
  - parent: child timetable
  - admin: institution schedule builder
- Conflict visualization.

Acceptance checks:

- Users see only relevant schedules. Student route and forbidden detail access are covered by tests.
- Admin can manage rooms/timeslots/schedules.
- Timetable grid works on mobile.

### 11. Analytics Frontend

Routes:

- `/analytics/`
- `/analytics/my-analytics/` - done: role-scoped self-service analytics page.
- `/analytics/student-performance/`
- `/analytics/class-performance/`
- `/analytics/teacher-performance/`
- `/analytics/reports/`

Needed improvements:

- Admin executive dashboard.
- Teacher course analytics. Initial self-service teacher section is available on `/analytics/my-analytics/`.
- Student progress analytics. Initial self-service student section is done and covered by tests.
- Parent child progress summary.
- Export/report generation UX.

Acceptance checks:

- Students/parents cannot access institution-wide analytics. Student self-service route only exposes the current student's performance.
- Teachers see analytics for assigned classes only.
- Admin sees institution-level dashboards.

## Priority 2: Global Frontend Quality Work

### Design System

Create or consolidate:

- Page header component
- Metric card component
- Empty state component
- Status badge component
- Filter/search toolbar
- Responsive data table pattern
- Action dropdown pattern
- Confirmation modal pattern
- Form layout pattern

Files likely involved:

- `static/css/adom-theme.css`
- `templates/base.html`
- Optional partials under `templates/components/`

### Mobile Responsiveness

Fix:

- Wide tables on student, fees, academics, analytics, library.
- Button groups that overflow.
- Sidebar overlay behavior.
- Search/filter forms on small screens.

Acceptance checks:

- Pages usable at 360px width.
- No horizontal overflow except intentional scrollable tables.
- Primary actions remain visible.

### Accessibility

Fix:

- Icon-only buttons need `aria-label` or visible text.
- Status color must have text labels.
- Forms need clear labels and error messages.
- Keyboard focus states must be visible.
- Modal flows must be keyboard accessible.

Acceptance checks:

- Core pages pass manual keyboard navigation.
- Important actions are screen-reader understandable.

## Priority 3: Route Coverage Tests

Add route-render tests for seeded records:

- ADOM Institute pages
- Course/LMS pages
- Student portal pages
- Teacher dashboard pages
- Fee self-service pages
- Library student discovery pages
- Communication inbox pages
- Timetable role-specific pages
- Analytics role-specific pages

Test goals:

- Page returns `< 400`.
- Page contains role-appropriate heading.
- Page does not show forbidden action text.
- Page does not crash with empty datasets.

## Suggested Next Session Order

1. Build ADOM Institute frontend pages because backend/API is newly available and currently underexposed.
2. Build course/LMS frontend using existing academics/library data.
3. Modernize student and teacher dashboards because they are highest-frequency users.
4. Modernize fees self-service and accountant views.
5. Modernize communication and timetable role-specific screens.
6. Add route coverage tests for each completed page group.

## Definition Of Done

A frontend endpoint is considered complete when:

- It has a named URL route.
- It has a template using the ADOM Institute design system.
- It dynamically fetches scoped data.
- It hides irrelevant or forbidden actions by role.
- It handles empty states.
- It works on mobile.
- It has at least one route-render regression test.
- It is linked from role-appropriate navigation or dashboard actions.

## Notes For Next Session

- Keep using open-source AI models only.
- Do not add GPT dependencies.
- Keep backend changes minimal unless a page needs them.
- Prefer class-based views and scoped querysets.
- Use existing permission helpers before creating new ones.
- Update `docs/AUDIT_REPORT.md` after each completed frontend group.
