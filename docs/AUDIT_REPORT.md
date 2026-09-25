# ADOM Institute Student Management System Audit and Modernization Report

Audit date: 2026-06-13  
Last updated: 2026-06-16  
Project path: `C:\Users\YOGA\Documents\project\student management system`

## 1. Executive Summary

This project is a promising Django monolith with the right first-level modules for a school platform: accounts, students, teachers, academics, fees, attendance, communication, timetable, library, and analytics. It already uses a custom user model, Django REST Framework, class-based views in several areas, templates, admin registration, Docker, Celery, Channels, and a basic analytics concept.

The current implementation is not yet ready for 100,000+ students, national deployment, universities, government adoption, or investor due diligence. Since the original audit, the platform has moved forward on the highest-risk Phase 1 items: institution tenancy primitives, role-aware permissions, scoped web/API querysets, role-specific templates, shared file validators, transactional payment recording, locked receipt sequencing, direct API v1 router mounts, production configuration guards, environment-driven database configuration, conditional debug toolbar loading, and baseline regression tests. The AI foundation has also started with an open-source model registry, RAG blueprint, agent definitions, consent records, knowledge-document metadata, conversations, messages, and agent task APIs. The largest remaining gaps are full production multi-tenancy coverage, private media/malware scanning, mobile/accessibility polish, deployment/observability depth, and missing full LMS/AI execution pipelines.

Readiness summary:

| Area | Score | Reason |
|---|---:|---|
| Product foundation | 6/10 | Broad modules exist and role-specific workflows are improving, but LMS/course workflows remain shallow. |
| Technical readiness | 5/10 | Loads successfully, has 61 regression tests, env-driven DB config, scoped permissions, and initial AI persistence, but needs deployment and observability hardening. |
| Security readiness | 5/10 | Major role/tenant controls were added; remaining risks are full API coverage, media privacy/scanning, MFA/session hardening, and audit depth. |
| AI readiness | 3/10 | Open-source model configuration, agent registry, RAG blueprint, consent records, knowledge-document metadata, text ingestion/search, conversations, messages, agent task APIs, and usage ledger now exist. Actual inference, OCR, vector indexing, evaluation, and orchestration workers remain. |
| Investor readiness | 5/10 | Strong vision and better technical controls, but still needs pilots, scale proof, polished UX, and AI defensibility. |

### Implementation Progress Since Original Audit

Completed:

- Added `Institution` and `InstitutionMembership` tenant primitives with migrations and backfill.
- Added reusable role and institution permission helpers in `accounts.permissions`.
- Scoped major student, academic, attendance, fee, timetable, teacher, library, and communication views by role/institution.
- Restricted admin, teacher, accountant, and self-service pages with class-based permission mixins.
- Added role-aware UI context in `accounts.context_processors.role_ui`.
- Updated many templates so students, parents, teachers, accountants, and admins see role-relevant labels/actions.
- Added shared file validators for common upload surfaces and aligned the digital-resource upload form with the same policy.
- Hardened payment recording through a transactional service that locks the student fee row, rejects overpayment under the lock, updates balances/statuses, and creates receipts for completed payments.
- Added a locked receipt sequence model so receipt numbers no longer depend on unsafe latest-receipt lookups.
- Changed settings to support PostgreSQL through environment variables with SQLite only as local fallback.
- Added production startup guards requiring a real `SECRET_KEY`, production `ALLOWED_HOSTS`, and PostgreSQL when `DEBUG=False`.
- Made debug toolbar local-only and required a real `SECRET_KEY` when `DEBUG=False`.
- Added baseline tests for role access, route rendering, student scoping, attendance, academics, fees, API v1 routing, and upload validation.
- Mounted `/api/v1/` directly to DRF routers so preferred API paths are clean, for example `/api/v1/students/students/` instead of `/api/v1/students/api/students/`.
- Added `adom_institute` as a Django app with models, admin, DRF endpoints, migration, and tests for AI consent/task foundations using open-source model defaults.
- Updated the ADOM Institute AI Hub to dynamically show scoped knowledge-document, conversation, and agent-task counts plus recent agent tasks.

Unblocked on 2026-06-16:

- `templates/timetable/timetable_view.html` was normalized to UTF-8 and the invalid URL tags `timetable_create` and `timetable_settings` were replaced with `schedule_create` and `room_list`.

## 2. Architecture Review

### Current Strengths

- Clear app separation by domain: accounts, students, teachers, academics, attendance, fees, communication, timetable, library, analytics.
- Custom email-based user model exists in `accounts.models.User`.
- DRF is installed and many apps expose model viewsets.
- Bootstrap templates exist for most workflows.
- Celery, Channels, Redis, S3 options, Swagger, and Docker are present as architectural intent.
- AuditLog, AnalyticsEvent, Report, Notification, and DigitalResource models are good starting points.
- Institution and institution membership models now provide an initial tenant boundary.
- Role-aware permission helpers and UI context are now present.
- A baseline regression suite now exists and currently passes.

### Major Weaknesses

| Finding | Why Needed | Impact | Implementation Approach | Complexity | Business Value |
|---|---|---|---|---:|---:|
| Multi-tenancy is started but incomplete | National deployment needs multiple schools, campuses, provinces, terms, and ownership boundaries. | Tenant primitives exist, but every workflow still needs production-grade tenant guarantees. | Continue scoping every major model/queryset; add `Campus`, `AcademicTerm`, and tenant-aware audit/reporting. | High | Very High |
| SQLite is now local fallback, not production target | PostgreSQL config exists through env vars, and production startup now rejects SQLite. | Better for development while reducing accidental deployment risk. | Keep `DB_ENGINE=postgresql` in production manifests; add backup/restore automation. | Medium | Very High |
| API route cleanup is partially complete | `/api/v1/` now mounts direct DRF routers, but app-level legacy `/app/api/` routes still exist for compatibility. | Preferred API paths are cleaner; future work should deprecate legacy paths and document versioning. | Keep `/api/v1/` direct; later remove app-level API includes after clients migrate. | Medium | High |
| Authorization coverage is improved but not complete | Major web/API querysets are role-scoped, but every endpoint still needs route-by-route review. | Remaining IDOR/privacy risk if any API or report bypasses the shared helpers. | Continue using role mixins and scoped querysets; add negative tests for every module. | High | Very High |
| No service layer for financial/academic operations | Payments, receipt generation, grade entry, and attendance updates are done inline. | Hard to test, race-prone, inconsistent validation. | Create domain services: `record_payment`, `generate_receipt`, `bulk_mark_attendance`, `publish_result`. | Medium | High |
| Runtime bugs in query logic | Several views filter or aggregate Python properties as DB fields. | APIs fail at runtime under normal use. | Replace with ORM expressions or persisted computed fields. | Medium | High |
| Tests exist but coverage is still narrow | 61 tests now pass for critical access, route, API mount, payment, receipt, upload, and initial AI/RAG flows. | Regression risk is lower, but edge-case workflows still need coverage. | Expand model, permission, API, concurrent payment, upload, AI worker, and workflow tests. | Medium | Very High |

## 3. UI/UX Audit

There are 123 templates. The current UI is Bootstrap-based, functional, and broad, but not yet a modern SaaS product experience.

### Global Issues

- Navigation and many templates are now role-aware, but the UI still needs a consistent design system and full mobile polish.
- Visual language depends heavily on Bootstrap defaults, gradients, Font Awesome, and page-level custom CSS.
- Information architecture is module-first rather than user-task-first.
- Dashboards are mostly counters and lists, not decision surfaces.
- Mobile support is partial: sidebar collapse exists, but dense tables, cards, filters, and modals will be difficult on phones.
- Accessibility is inconsistent: icon-only actions often lack accessible names, color is used as status signal, and focus states are not designed as a system.
- Templates duplicate card/table patterns instead of using reusable components.
- Recent work removed many admin-only buttons from student, parent, teacher, accountant, and learner views, but a full page-by-page accessibility pass is still required.

### Page-Level Review By Area

| Area | Usability Problems | Design Issues | Accessibility/Mobile Risks | Recommended Redesign |
|---|---|---|---|---|
| Accounts/login/register/profile | Basic forms, little onboarding, no SSO/2FA flow exposed. | Generic branding. | Missing stronger error guidance and password UX. | Add branded auth layout, MFA setup, recovery, role onboarding. |
| Student pages | Good list/detail CRUD foundation, but admin-oriented. | Tables dominate; little student journey context. | Wide tables on mobile. | Role-specific student portal with progress, attendance, fees, assignments. |
| Teacher pages | Staff directory exists, but teaching workflow is fragmented. | Limited course analytics. | Actions not optimized for repeated grading/attendance. | Teacher cockpit: today schedule, classes, grading queue, risk alerts. |
| Academics | Exams/assignments exist, but flows contain runtime bugs and generic UX. | Many custom cards/modals. | File submission and grading modals need keyboard/accessibility review. | Course-centric LMS layout with assessment builder and rubric workflow. |
| Attendance | Useful bulk attendance idea. | Needs faster classroom marking UX. | Large rosters need mobile-friendly tap targets. | Grid/tap roster, QR optional, absence notes, parent alerts. |
| Fees | Core financial entities exist. | Needs clearer balances, receipts, payment history. | Financial tables must be responsive and exportable. | Accountant dashboard with aging, collections, reconciliation, audit trail. |
| Communication | Messages, announcements, notifications exist. | Needs inbox-like UX and notification preferences. | Attachments need safe previews. | Unified communication center with segments, templates, delivery status. |
| Timetable | Good scheduling models and conflict checks. | Timetable visual design is promising but inconsistent. | Grid views may overflow. | Calendar-grade timetable with filters, room/teacher conflict visualization. |
| Library | Stronger than average module with physical/digital resources. | Needs content discovery UX. | Digital access controls need clarity. | Knowledge library with search, tags, curriculum mapping, RAG ingestion status. |
| Analytics | Concept exists but uses static snapshots. | Dashboard lacks drill-down and evidence. | Charts must include text alternatives. | Executive analytics: enrollment, risk, finance, performance, system health. |

### Modern Dashboard Targets

Student dashboard:

- GPA overview, grade trend, course progress, attendance summary, fee balance, timetable today.
- Upcoming exams, assignments due, unread announcements, library recommendations.
- AI study recommendations based on weak topics, attendance, past papers, and upcoming assessments.

Teacher dashboard:

- Classes today, attendance pending, grading queue, student risk list, course analytics.
- Assessment creation, rubric marking, lesson resources, parent communication.
- AI teaching assistant for quizzes, lesson plans, explanations, differentiated materials.

Administrator dashboard:

- Institution analytics, enrollment, attendance, pass rates, teacher workload, fee collection, system health.
- User management, audit events, active incidents, storage usage, message delivery.
- AI insights: risk cohorts, curriculum coverage, scholarship opportunities, intervention ROI.

## 4. Security Audit

| Risk | Level | Evidence | Fix | Code Example |
|---|---|---|---|---|
| IDOR / excessive data exposure | High | Major scoping helpers and view restrictions now exist, but every API/report endpoint still needs negative tests. | Keep role/institution scoping centralized; expand coverage to every endpoint. | Use `InstitutionScopedQuerysetMixin` and route-level tests. |
| Privilege escalation through role APIs | High | Role and permission APIs are now restricted to platform/institution admin users. | Add audit events for role changes and test cross-institution role assignment denial. | Use `permission_classes = [IsPlatformOrInstitutionAdmin]`. |
| Debug tooling in installed middleware | Resolved for current settings | `debug_toolbar` is loaded only when `DEBUG=True`. | Keep production config checks in CI/deployment. | Conditional `INSTALLED_APPS` and `MIDDLEWARE` are already present. |
| Secret key fallback | Resolved for non-debug mode | Settings now raises `ImproperlyConfigured` if `DEBUG=False` and the default key is still used. | Document deployment env requirements. | Current settings already enforce this. |
| File upload abuse | Medium/High | Shared extension/size/filename validators now cover current common upload surfaces and digital-resource forms, but private storage and AV scanning are still missing. | Add private media, signed downloads, malware scanning, and content-disposition rules. | Add async scan status and deny serving unsafe files. |
| Receipt number race condition | Resolved for current model | Receipt numbers now use `ReceiptSequence.next_receipt_number()` with `select_for_update()`. | Extend sequence to institution/year when finance becomes multi-tenant. | Keep locked sequence calls inside receipt creation. |
| Broken auth/session hardening | Medium | Email verification disabled; 2FA fields exist but no full flow. | Require email verification, MFA for staff/admins, login throttling. | Add django-axes or DRF throttles. |
| CSRF posture is mixed | Medium | Django CSRF middleware exists, but API token/session auth coexists. | Separate API token/JWT auth from browser session endpoints. | Use CSRF for browser views, JWT/Token for APIs. |
| Sensitive education/financial data exposure | High | Broad list APIs and reports return student and financial data without object scope. | Data minimization, field-level permissions, audit logs. | Serializer fields should vary by role. |
| XSS | Medium | Django autoescaping helps; uploaded HTML/files and rich text are not sanitized. | Sanitize rich content and serve uploads from separate domain/private storage. | Use Bleach for user HTML, avoid inline unsafe rendering. |

### Example: Scoped Queryset Permission Pattern

```python
class ScopedStudentQuerysetMixin:
    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.select_related("user", "current_class", "current_class__academic_year")

        if user.is_superuser or user.user_type in ["super_admin", "administrator"]:
            return qs.filter(institution__memberships__user=user)
        if user.user_type == "teacher":
            return qs.filter(current_class__schedules__teacher__user=user).distinct()
        if user.user_type == "student":
            return qs.filter(user=user)
        if user.user_type == "parent":
            return qs.filter(parents__user=user)
        return qs.none()
```

## 5. Database Audit

### Current Strengths

- Core relationships exist for users, students, parents, classes, teachers, subjects, exams, assignments, fees, attendance, timetable, library, analytics.
- Many uniqueness constraints exist.
- Several useful read models exist in analytics.

### Major Missing Tables

- `Institution`, `Campus`, `Province/District`, `InstitutionMembership`
- `AcademicTerm/Semester`, `Enrollment`, `Course`, `CourseSection`
- `Program`, `Department` linked to institution, `Curriculum`, `Syllabus`, `LearningOutcome`
- `Assessment`, `QuestionBank`, `Rubric`, `SubmissionAttempt`, `Gradebook`
- `GuardianStudentRelationship` instead of one parent profile per user only
- `Invoice`, `PaymentAllocation`, `Refund`, `PaymentProviderTransaction`
- `NotificationPreference`, `DeviceToken`, `MessageDelivery`
- `KnowledgeDocument`, `DocumentChunk`, `Embedding`, `OCRJob`, `Citation`
- Started: `AIConversation`, `AIMessage`, `AgentTask`, `AIConsent`, `AIUsageLedger`
- Still missing: `AgentRun` execution traces and richer evaluation feedback records.
- `AuditEvent` with institution, actor, target, IP, user agent, diff, retention class

### Indexing and Constraint Recommendations

- Add indexes for common filters: `Student(current_class, is_active)`, `Attendance(student, date, status)`, `Payment(student, payment_status, payment_date)`, `StudentFee(payment_status, due_date)`, `StudentExamResult(student, exam_subject)`.
- Replace `unique_together` with `UniqueConstraint` for conditional constraints where needed.
- Use `CheckConstraint` for marks <= max marks, positive amounts, valid date ranges, attendance counts.
- Add institution foreign keys and composite indexes using `institution_id`.
- Persist or annotate metrics used in sorting/filtering; do not query Python properties.

## 6. Performance Review

| Issue | Impact | Fix |
|---|---|---|
| Broad `.objects.all()` APIs | Large unbounded scans and privacy leakage. | Scope, filter, paginate, and add indexes. |
| Dashboard aggregate queries recomputed per request | Slow at scale. | Materialized analytics tables refreshed by Celery. |
| File handling synchronous | Large uploads block web workers. | Direct-to-object-storage uploads and async scanning/OCR. |
| Repeated `.count()` calls in assignment summary | Extra queries. | Store class size or compute once. |
| Receipt sequence is locked globally by year | Current receipt numbers are concurrency-safe for the present model, but not institution-scoped. | Extend to per-institution/year sequence before national multi-tenant rollout. |
| No cache strategy | Repeated dashboard/report reads hit DB. | Redis cache for reference data, dashboard summaries, permissions. |

Recommended stack for scale:

- PostgreSQL 16+ with partitioning for audit/events/attendance.
- Redis for cache, Celery broker, channels layer.
- Celery workers for reports, notifications, OCR, embeddings, AI tasks.
- Object storage for uploads with signed URLs.
- Read replicas for analytics once usage grows.
- OpenTelemetry, Sentry, structured logs, Prometheus/Grafana.

## 7. AI Assistant Design: ADOM Institute

ADOM Institute should be a role-aware assistant embedded across dashboards, courses, library, assignments, and admin workflows.

Capabilities:

- Student Tutor: explain concepts, generate practice questions, mark self-tests, cite course materials.
- Academic Advisor: suggest course plans, detect risk, explain degree/program progress.
- Course Assistant: summarize lessons, generate quizzes, map content to learning outcomes.
- Career Advisor: CV feedback, career paths, internship/scholarship matching.
- Research Assistant: search institutional knowledge base, summarize papers, generate citations.
- Administrative Assistant: answer policy questions, fee deadlines, timetable queries, registration guidance.

Guardrails:

- Role and institution scoped retrieval.
- Human approval for grades, discipline, financial actions, enrollment changes, official notices.
- Citation-required responses for academic/policy claims.
- PII minimization and consent for student profiling.
- Full audit log of prompts, retrieved documents, tool calls, outputs, and user feedback.

## 8. Multi-Agent Design

### Recommended Orchestration

Best choice for this project: LangGraph with open-source model serving.

Why:

- Education workflows are stateful, auditable, and often require human approval.
- LangGraph supports deterministic workflow graphs, checkpoints, retries, tool routing, and supervised multi-agent flows.
- CrewAI is faster for demos but weaker for production governance.
- AutoGen is useful for research-style collaboration but less ideal as a controlled SaaS backend.
- For this project, avoid GPT dependency by default. Use LangGraph for orchestration and serve open-source models through vLLM, Hugging Face Text Generation Inference, Ollama, or llama.cpp depending on deployment size. LiteLLM can provide a provider-neutral gateway while still routing to self-hosted models.

Open-source model defaults:

- General ADOM Institute: Llama 3.1/3.3 70B Instruct, Qwen2.5/3 Instruct, or Mixtral-class models depending on available GPUs.
- Low-cost school deployments: Llama 3.1 8B Instruct, Qwen2.5 7B/14B Instruct, Phi-3.5/4 small models for constrained tasks.
- Embeddings: BAAI `bge-m3`, `bge-large-en-v1.5`, E5-large, or multilingual E5 for African multilingual support.
- Reranking: BAAI `bge-reranker-large` or Jina reranker.
- OCR/document AI: PaddleOCR, Tesseract, DocTR, LayoutParser, and marker/docling-style document extraction.
- Speech/video: Whisper large-v3 or faster-whisper for transcripts.

### Agent Communication Flow

1. User request enters ADOM Institute Gateway.
2. Gateway authenticates user, role, institution, consent, and policy.
3. Router classifies task: tutoring, assessment, admin, research, risk, career, curriculum, opportunity.
4. LangGraph delegates to specialized agent.
5. Agent retrieves context from institutional DB, vector store, and approved tools.
6. Agent produces draft output with citations and confidence.
7. Policy layer checks safety, privacy, academic integrity, and permission.
8. Human approval is required for high-impact actions.
9. Final output and audit event are stored.

### Memory Architecture

- Short-term memory: conversation state per session.
- User memory: preferences, learning goals, weak topics, accessibility needs, only with consent.
- Institutional memory: policies, curriculum, course materials, past papers, announcements.
- Agent memory: previous task outcomes, feedback, evaluation scores.
- Audit memory: immutable logs for compliance and incident response.

### Agent Matrix

| Agent | Purpose | Responsibilities | Inputs | Outputs | Tools | Suggested Models |
|---|---|---|---|---|---|---|
| Student Success Agent | Improve retention/performance | Monitor grades, attendance, fees, engagement; detect risk; recommend interventions. | Results, attendance, submissions, fees, login events. | Risk score, intervention plan, reports. | Django ORM, analytics warehouse, notification service. | XGBoost/LightGBM risk model plus Llama/Qwen for explanations. |
| Assessment Agent | Help teachers create assessments | Generate quizzes/exams/rubrics/marking schemes/explanations. | Syllabus, learning outcomes, difficulty, past papers. | Draft assessments, rubrics, solutions. | RAG, question bank, export to PDF/DOCX. | Qwen2.5/3 32B or Llama 3.1/3.3 70B Instruct with RAG. |
| Learning Coach Agent | Personalized study support | Study plans, resource recommendations, progress tracking. | Student profile, grades, timetable, goals. | Weekly plan, reminders, practice sets. | Calendar, knowledge base, notifications. | Llama 3.1 8B/70B or Qwen2.5 14B depending on budget. |
| Research Agent | Academic research support | Search sources, summarize papers, explain concepts. | Query, course, citation style. | Cited summary, reading list, concept map. | Scholarly search APIs, RAG, citation manager. | Llama 3.1/3.3 70B, Qwen2.5/3 32B+, or Mixtral-class model with retrieval. |
| Career Guidance Agent | Employability | Career recommendations, CV review, internships, scholarships. | Skills, grades, interests, location. | Career plan, CV feedback, opportunity matches. | CV parser, opportunity crawler, email alerts. | Qwen/Llama instruct model plus embedding search. |
| Academic Integrity Agent | Protect assessment quality | Plagiarism signals, AI-content analysis, misconduct patterns. | Submissions, metadata, similarity index. | Risk report, evidence, reviewer queue. | Similarity engine, embeddings, file parsers. | Embedding model plus classifier; LLM only for explanations. |
| Content Management Agent | Keep learning resources organized | Auto-tag, categorize, map resources to syllabus. | Uploaded files, metadata, curriculum. | Tags, summaries, curriculum links. | OCR, document parser, vector DB. | Qwen/Llama small instruct model plus BGE embeddings. |
| Administrative Agent | Automate operations | Registration, timetable, fee reminders, notifications. | Student data, rules, calendar, balances. | Draft notices, task queues, suggested updates. | Django services, Celery, SMS/email. | Llama 3.1 8B or Qwen2.5 7B with strict tool schemas. |
| Zambian Curriculum Agent | Local defensibility | Understand ECZ syllabi, outcomes, past papers, grading expectations. | ECZ documents, school syllabus, past papers. | Curriculum map, lesson alignment, exam prep. | RAG, OCR, curriculum ontology. | Llama/Qwen 32B-70B with high-quality RAG and BGE embeddings. |
| Scholarship & Opportunities Agent | Africa-wide opportunity engine | Scan scholarships, internships, competitions, grants, jobs. | Student profile, eligibility, location, deadlines. | Matched opportunities, alerts, application checklist. | Web/API ingestion, dedupe, notification service. | Small Qwen/Llama for extraction; larger open model for fit analysis. |

## 9. Knowledge Base and RAG Architecture

### Institutional Knowledge Base

Content types:

- Course materials, notes, lesson plans, policies, books, past papers, research papers, curriculum documents, fee policies, timetables, handbooks.

Recommended architecture:

1. Upload document to private object storage.
2. Create `KnowledgeDocument` record with institution, owner, access level, source, checksum.
3. Run Celery OCR/parser pipeline.
4. Extract text, tables, images, metadata, and page numbers.
5. Chunk by semantic sections and learning outcomes.
6. Generate embeddings.
7. Store chunks in PostgreSQL + pgvector initially.
8. Use hybrid search: PostgreSQL full-text search + vector search + metadata filters.
9. Return citations with document, page, section, and access policy.

Current implementation status:

- Started: `adom_institute.KnowledgeDocument` stores institution-scoped source metadata and validated files.
- Started: `adom_institute.KnowledgeChunk` stores extracted chunks and placeholder JSON embeddings until pgvector is introduced.
- Started: `adom_institute.services.ingest_knowledge_document()` calculates checksums, extracts text-like files, chunks content, and exposes a `/process/` API action.
- Started: `/api/v1/adom-institute/knowledge-documents/search/` returns permission-scoped chunk search results with citation metadata.
- Started: `adom_institute.AIConsent`, `AIConversation`, `AIMessage`, and `AgentTask` provide the consent and orchestration data layer.
- Started: `adom_institute.AIUsageLedger` records provider, model, token counts, latency, zero-cost open-source accounting, and scoped read-only API access.
- Started: the AI Hub displays scoped AI module activity for authenticated users.
- Started: the AI Hub includes usage-ledger counts so open-source model activity is visible in the UI.
- Remaining: async virus scan, OCR for PDFs/scans, embedding generation, pgvector/Qdrant indexing, reranking, and answer-generation workers.

Vector DB recommendation:

| Option | Recommendation |
|---|---|
| PostgreSQL + pgvector | Best starting choice. Fits current Django stack, simpler operations, good enough for institution-scale RAG. |
| Qdrant | Best next step when vector workload grows or hybrid retrieval needs stronger performance. |
| Chroma | Good for prototypes, not best for national production. |
| Weaviate | Powerful but operationally heavier; consider later if semantic search becomes a core standalone platform. |

## 10. Missing Features Report

High-priority product modules:

- LMS course pages, modules, lessons, resources, quizzes, assignments, rubrics, gradebook.
- Virtual classroom integration: live sessions, recordings, attendance, chat.
- Video learning: upload/stream, transcripts, chapters, quizzes, analytics.
- Discussion forums and student communities with moderation.
- Scholarship portal and opportunity matching.
- Internship portal and employer partnerships.
- Research hub with institutional repository.
- Alumni network and mentorship.
- AI Study Buddy, AI Mentor, AI Exam Preparation, AI Curriculum Assistant.
- Parent portal with child progress, fees, attendance, messages.
- Mobile-first student app and offline/low-bandwidth mode.
- Multi-language/localization support for Zambia and Africa.
- Compliance module: consent, data retention, audit, incident response.

## 11. Investor and Government Assessment

| Criterion | Score | Assessment |
|---|---:|---|
| Market Opportunity | 8/10 | Strong need across Zambia/Africa for affordable SIS/LMS plus AI. |
| Competitive Advantage | 5/10 | Generic LMS features are easy to copy; Zambian Curriculum Agent and Opportunities Agent improve defensibility. |
| Scalability | 5/10 | Tenant primitives, env-driven DB config, and tests exist; production deployment, API cleanup, indexing depth, and observability still need work. |
| Revenue Potential | 7/10 | SaaS per institution/student, implementation services, AI add-ons, SMS/payment margin, government contracts. |
| Technical Quality | 5/10 | Broad platform with improved permissions and tests; still needs service-layer hardening, complete endpoint coverage, and UI polish. |
| AI Readiness | 3/10 | Initial AI data model, policy/consent layer, agent registry, and open-source runtime defaults exist; execution workers, RAG indexing, evaluations, and cost controls remain. |

Scores:

- Investment Readiness Score: 5/10
- Technical Readiness Score: 5/10
- Commercial Readiness Score: 6/10

Due diligence view:

- A VC would like the market and vision but ask for usage proof, school pilots, retention metrics, payment willingness, and technical hardening.
- An Education Ministry would require data residency, privacy controls, procurement compliance, audit logs, accessibility, uptime SLAs, and local curriculum alignment.
- A University Board would require SIS/LMS integration, SSO, role governance, data export, reporting, and support model.

## 12. Roadmap

### Phase 1: Critical Fixes

- Done: Add institution/multi-tenancy foundation.
- In progress: Fix runtime bugs in academics and fees.
- Done: Replace SQLite production posture with env-driven PostgreSQL/local SQLite fallback.
- Done: Add production startup guards for unsafe `SECRET_KEY`, localhost/wildcard `ALLOWED_HOSTS`, and SQLite under `DEBUG=False`.
- In progress: Lock down APIs and pages with role/object permissions.
- Done: Add shared file validators for current common upload surfaces; private media access and malware scanning still remain.
- Done: Add transactional payment and receipt service for current payment creation flows.
- Done: Remove debug toolbar from production config.
- In progress: Add baseline tests for authentication, permissions, payments, attendance, grading, uploads.
- Done: Fixed `templates/timetable/timetable_view.html` invalid URL tags after resolving Windows ransomware-protection write denial.
- Done: Mount `/api/v1/` directly to API routers instead of nested app web URLconfs.

### Phase 2: UI Modernization

- Create design system: colors, typography, spacing, buttons, forms, tables, status badges.
- In progress: Build role-aware shell, dashboards, and page actions.
- Replace broad CRUD pages with task-based workflows.
- Make responsive table patterns and mobile action sheets.
- Add accessible labels, focus states, empty states, skeletons, and error states.

### Phase 3: AI Assistant

- Started: add knowledge document, chunk, consent, conversation, message, and agent task models.
- Started: add ADOM Institute role-scoped API endpoints under `/api/v1/adom-institute/`.
- Remaining: add OCR, embeddings, RAG workers, usage ledger, and evaluation feedback.
- Launch student tutor and teacher assistant first.
- Use open-source models by default: Qwen/Llama/DeepSeek-class models for chat/reasoning, BGE/E5 for embeddings, PaddleOCR/Tesseract/DocTR for OCR.

### Phase 4: Multi-Agent System

- Implement LangGraph orchestration.
- Add Student Success, Assessment, Learning Coach, Research, Career, Integrity, Content, Admin agents.
- Add Zambian Curriculum Agent and Scholarship & Opportunities Agent as differentiation.
- Add human approval queues for high-impact actions.

### Phase 5: National Deployment

- Multi-region deployment, backups, observability, audit, incident response.
- SSO, data retention policies, data residency controls.
- Government reporting dashboards and ministry-level analytics.
- Institution onboarding, migration tools, support playbooks.

### Phase 6: Africa-Wide Expansion

- Country-specific curriculum packs.
- Multi-currency fees, local payment integrations, SMS provider abstraction.
- Multilingual support.
- Regional scholarship/opportunity network.
- Partner APIs for universities, employers, NGOs, and ministries.

## 13. Priority Matrix

| Priority | Item | Why | Business Value | Complexity |
|---|---|---|---:|---:|
| P0 | Complete object-level permissions and tenant scoping | Prevents data leakage. Started, not complete. | Very High | High |
| P0 | Enforce PostgreSQL in production | Required for production. Settings now reject SQLite under `DEBUG=False`; deployment manifests and backups remain. | Very High | Medium |
| P0 | Fix broken query/property usage | Prevents runtime failures. Partially addressed; continue endpoint testing. | High | Medium |
| P0 | Private media and malware scanning | Validators exist; storage/privacy/scanning remain. | High | Medium |
| P0 | Extend finance ledger model | Current payment recording is transactional; allocations, refunds, provider transactions, and reversal audit trails remain. | Very High | Medium |
| P1 | Role-aware dashboards | Makes product usable for pilots. Started across major templates. | High | Medium |
| P1 | Expand test suite | Enables safe iteration and investor diligence. Baseline 61 tests pass. | Very High | Medium |
| P1 | API route cleanup | Improves integration readiness. Preferred `/api/v1/` paths are now direct; legacy app-level API paths remain temporarily. | Medium | Medium |
| P2 | RAG knowledge base | Enables ADOM Institute. | Very High | High |
| P2 | AI agents | Differentiates product. | Very High | High |
| P3 | Mobile/offline support | Critical for African market reach. | High | High |

## 14. Detailed Code Improvements

### Fix broken academic summaries

Problem:

- `academics/views.py` filters `is_pass` and aggregates `percentage`, but both are Python properties, not database fields.
- `StudentExamResultViewSet.filterset_fields` and `ordering_fields` include non-fields.
- `ExamResultSummarySerializer` requires `grade_distribution`, but the view does not provide it.

Approach:

- Annotate percentage in queryset or calculate in Python for small result sets.
- Replace `is_pass` filters with `marks_obtained__gte=F("exam_subject__passing_marks")`.
- Add `grade_distribution`.

Example:

```python
from django.db.models import Case, When, Value, BooleanField, F, DecimalField, ExpressionWrapper

results = StudentExamResult.objects.filter(exam_subject__exam=exam).annotate(
    percentage_value=ExpressionWrapper(
        F("marks_obtained") * 100.0 / F("exam_subject__max_marks"),
        output_field=DecimalField(max_digits=6, decimal_places=2),
    ),
    passed=Case(
        When(marks_obtained__gte=F("exam_subject__passing_marks"), then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    ),
)
```

### Fix teacher relation bugs

Problem:

- `academics/views.py` bulk grade entry sets `created_by=request.user`, but `created_by` expects `Teacher`.
- `StudentAssignmentViewSet.grade_submission` sets `graded_by=request.user`, but `graded_by` expects `Teacher`.
- `attendance/views.py` references `request.user.teacher`, but the related name is `teacher_profile`.

Approach:

- Standardize helper properties or always use `request.user.teacher_profile`.
- Add role permission checks before teacher-only actions.

Example:

```python
teacher = getattr(request.user, "teacher_profile", None)
if teacher is None:
    return Response({"detail": "Teacher profile required."}, status=403)
serializer.save(graded_by=teacher)
```

### Fix fee aggregation

Problem:

- `fees/views.py` uses `Sum("balance_amount")`, but `balance_amount` is a Python property.
- Fee reports filter `student__academic_year`, but `Student` has no `academic_year` field.

Approach:

- Use ORM expression `Sum(F("amount") - F("paid_amount"))`.
- Filter through `student__current_class__academic_year`.

Example:

```python
from django.db.models import F, Sum, DecimalField, ExpressionWrapper

balance_expr = ExpressionWrapper(
    F("amount") - F("paid_amount"),
    output_field=DecimalField(max_digits=10, decimal_places=2),
)
pending_amount = StudentFee.objects.filter(
    payment_status__in=["pending", "partial"]
).aggregate(total=Sum(balance_expr))["total"] or Decimal("0")
```

### Harden receipt generation

Problem:

- Original receipt numbers were generated by reading the last receipt, which could duplicate under concurrent payments.

Approach:

- Completed: `ReceiptSequence` now increments under `transaction.atomic()` with `select_for_update()`.
- Completed: payment creation now goes through a transactional service that locks the `StudentFee`, validates outstanding balance, updates fee status, and creates a receipt for completed payments.
- Remaining: add payment allocations, reversals/refunds, provider transaction records, and audit events around financial changes.

### Normalize API structure

Current:

- `/api/v1/students/api/students/`
- `/api/v1/accounts/api/users/`

Target:

- `/api/v1/students/`
- `/api/v1/classes/`
- `/api/v1/users/`
- `/api/v1/fees/payments/`

Approach:

- Create `api_urls.py` per app or one central `api.py`.
- Keep browser routes under app paths like `/students/`, `/fees/`, `/attendance/`.

### Production settings profile

Needed:

- `settings/base.py`, `settings/local.py`, `settings/production.py`.
- Env-driven DB, cache, email, storage, security, logging.
- `DEBUG=False`, secure cookies, HSTS only behind HTTPS, allowed hosts required.
- Remove debug toolbar unless local.
- Docker should run Gunicorn/Uvicorn, not `runserver`.

### Add tests first

Minimum Phase 1 tests:

- User roles cannot access other institutions.
- Parent sees only their child.
- Student cannot list all students, payments, or analytics.
- Teacher can grade only assigned classes.
- Payment updates balances transactionally.
- Receipt numbers are unique under concurrent calls.
- Upload rejects dangerous filenames, dangerous extensions, and oversized files.
- Fee dashboard and exam summary endpoints do not crash.

## Verification Performed

Commands run:

```powershell
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py test accounts.test_upload_validators library.tests
venv\Scripts\python.exe manage.py test fees
venv\Scripts\python.exe manage.py test academics attendance fees
venv\Scripts\python.exe manage.py test library timetable communication analytics
venv\Scripts\python.exe manage.py test accounts
venv\Scripts\python.exe manage.py test students
venv\Scripts\python.exe manage.py test adom_institute
venv\Scripts\python.exe manage.py test adom_institute fees accounts.test_upload_validators library.tests
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py makemigrations --check --dry-run
venv\Scripts\python.exe manage.py test
$env:DEBUG='False'; $env:SECRET_KEY='production-test-key-not-real'; $env:ALLOWED_HOSTS='adom.example.com'; $env:DB_ENGINE='sqlite'; venv\Scripts\python.exe manage.py check
```

Results:

- 2026-06-16: Django system check completed with no issues.
- 2026-06-16: Focused upload validator tests passed.
- 2026-06-16: Fee regression tests found and passed 11 tests, including transactional payment and receipt sequence coverage.
- 2026-06-16: AI foundation tests found and passed 4 tests for open-source defaults, scoped agent tasks, and `/api/v1/adom-institute/` routing.
- 2026-06-16: AI Hub route tests verify dynamic knowledge/task sections render.
- 2026-06-16: RAG ingestion tests verify text chunking, failed status persistence, and the knowledge-document process API action.
- 2026-06-16: RAG search tests verify permission-scoped chunk retrieval and empty-query validation.
- 2026-06-16: AI usage ledger tests verify token totals, zero-cost open-source accounting, and read-only scoped API access.
- 2026-06-16: Combined AI/fees/upload regression group found and passed 22 tests.
- 2026-06-16: `adom_institute.0001_initial` migration applied successfully.
- 2026-06-16: `adom_institute.0002_aiusageledger` migration applied successfully.
- 2026-06-16: Full Django test runner found and passed 61 tests.
