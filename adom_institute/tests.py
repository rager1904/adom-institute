from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Institution, InstitutionMembership, User
from .models import AIUsageLedger, AgentTask, KnowledgeChunk, KnowledgeDocument
from .registry import get_ai_runtime_config
from .services import KnowledgeIngestionError, ingest_knowledge_document, record_ai_usage
from .views import AgentTaskViewSet, KnowledgeDocumentViewSet


class AdomInstituteFoundationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.institution = Institution.objects.create(name='ADOM Institute Pilot', code='ADOM')
        self.other_institution = Institution.objects.create(name='Other School', code='OTHERAI')
        self.teacher = User.objects.create_user(
            email='teacher-ai@example.com',
            password='pass12345',
            user_type='teacher',
        )
        InstitutionMembership.objects.create(
            user=self.teacher,
            institution=self.institution,
            role=InstitutionMembership.MembershipRole.TEACHER,
        )

    def test_ai_runtime_defaults_to_open_source_models(self):
        config = get_ai_runtime_config()

        self.assertEqual(config['provider'], 'ollama')
        self.assertIn('qwen', config['default_chat_model'])
        self.assertIn('bge', config['default_embedding_model'].lower())

    def test_agent_task_create_is_scoped_to_user_institution(self):
        request = self.factory.post(
            '/api/v1/adom-institute/agent-tasks/',
            {
                'institution': self.institution.pk,
                'agent_key': 'zambian_curriculum',
                'model_profile': 'reasoning',
                'input_payload': {'subject': 'Mathematics', 'grade_level': '12'},
            },
            format='json',
        )
        force_authenticate(request, user=self.teacher)

        response = AgentTaskViewSet.as_view({'post': 'create'})(request)

        self.assertEqual(response.status_code, 201)
        task = AgentTask.objects.get()
        self.assertEqual(task.created_by, self.teacher)
        self.assertEqual(task.agent_key, 'zambian_curriculum')

    def test_agent_task_rejects_other_institution(self):
        request = self.factory.post(
            '/api/v1/adom-institute/agent-tasks/',
            {
                'institution': self.other_institution.pk,
                'agent_key': 'student_success',
                'input_payload': {'student_id': 'S1'},
            },
            format='json',
        )
        force_authenticate(request, user=self.teacher)

        response = AgentTaskViewSet.as_view({'post': 'create'})(request)

        self.assertEqual(response.status_code, 403)

    def test_adom_institute_api_route_is_mounted(self):
        self.client.force_login(self.teacher)

        response = self.client.get('/api/v1/adom-institute/agent-tasks/')

        self.assertEqual(response.status_code, 200)

    def test_ingest_text_knowledge_document_creates_chunks(self):
        document = KnowledgeDocument.objects.create(
            institution=self.institution,
            uploaded_by=self.teacher,
            title='ECZ Mathematics Notes',
            source_type='course_material',
            file=SimpleUploadedFile(
                'math-notes.txt',
                b'Algebra fundamentals for grade twelve. ' * 80,
                content_type='text/plain',
            ),
        )

        result = ingest_knowledge_document(document.pk)

        self.assertEqual(result.processing_status, KnowledgeDocument.ProcessingStatus.READY)
        self.assertTrue(result.checksum)
        self.assertGreater(KnowledgeChunk.objects.filter(document=document).count(), 0)
        self.assertEqual(result.metadata['embedding_status'], 'pending')

    def test_ingest_unsupported_document_marks_failed(self):
        document = KnowledgeDocument.objects.create(
            institution=self.institution,
            uploaded_by=self.teacher,
            title='Scanned Paper',
            source_type='past_paper',
            file=SimpleUploadedFile(
                'paper.pdf',
                b'%PDF-1.4 placeholder',
                content_type='application/pdf',
            ),
        )

        with self.assertRaises(KnowledgeIngestionError):
            ingest_knowledge_document(document.pk)

        document.refresh_from_db()
        self.assertEqual(document.processing_status, KnowledgeDocument.ProcessingStatus.FAILED)
        self.assertIn('OCR/document parsing is required', document.error_message)

    def test_knowledge_document_process_action_runs_ingestion(self):
        document = KnowledgeDocument.objects.create(
            institution=self.institution,
            uploaded_by=self.teacher,
            title='Policy Notes',
            source_type='policy',
            file=SimpleUploadedFile(
                'policy.txt',
                b'Learner conduct and assessment policy. ' * 50,
                content_type='text/plain',
            ),
        )
        request = self.factory.post(f'/api/v1/adom-institute/knowledge-documents/{document.pk}/process/')
        force_authenticate(request, user=self.teacher)

        response = KnowledgeDocumentViewSet.as_view({'post': 'process'})(request, pk=document.pk)

        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.processing_status, KnowledgeDocument.ProcessingStatus.READY)

    def test_knowledge_document_search_returns_scoped_chunks(self):
        allowed = KnowledgeDocument.objects.create(
            institution=self.institution,
            uploaded_by=self.teacher,
            title='Allowed ECZ Notes',
            source_type='curriculum',
            file=SimpleUploadedFile('allowed.txt', b'fractions and algebra practice'),
            processing_status=KnowledgeDocument.ProcessingStatus.READY,
        )
        blocked = KnowledgeDocument.objects.create(
            institution=self.other_institution,
            uploaded_by=self.teacher,
            title='Blocked Notes',
            source_type='curriculum',
            file=SimpleUploadedFile('blocked.txt', b'algebra private content'),
            processing_status=KnowledgeDocument.ProcessingStatus.READY,
        )
        KnowledgeChunk.objects.create(document=allowed, chunk_index=0, content='algebra practice for ECZ learners')
        KnowledgeChunk.objects.create(document=blocked, chunk_index=0, content='algebra from another institution')
        request = self.factory.get('/api/v1/adom-institute/knowledge-documents/search/?q=algebra')
        force_authenticate(request, user=self.teacher)

        response = KnowledgeDocumentViewSet.as_view({'get': 'search'})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['document_title'], 'Allowed ECZ Notes')

    def test_knowledge_document_search_rejects_empty_query(self):
        request = self.factory.get('/api/v1/adom-institute/knowledge-documents/search/?q=')
        force_authenticate(request, user=self.teacher)

        response = KnowledgeDocumentViewSet.as_view({'get': 'search'})(request)

        self.assertEqual(response.status_code, 400)

    def test_record_ai_usage_totals_tokens_with_zero_cost_for_open_source_runtime(self):
        usage = record_ai_usage(
            user=self.teacher,
            institution=self.institution,
            provider='ollama',
            model_name='qwen2.5:7b-instruct',
            prompt_tokens=120,
            completion_tokens=80,
            latency_ms=1500,
            metadata={'agent': 'learning_coach'},
        )

        self.assertEqual(usage.total_tokens, 200)
        self.assertEqual(usage.estimated_cost, 0)
        self.assertEqual(AIUsageLedger.objects.count(), 1)

    def test_usage_ledger_api_is_read_only_and_scoped(self):
        record_ai_usage(
            user=self.teacher,
            institution=self.institution,
            provider='ollama',
            model_name='qwen2.5:7b-instruct',
            prompt_tokens=10,
        )
        self.client.force_login(self.teacher)

        list_response = self.client.get('/api/v1/adom-institute/usage-ledger/')
        create_response = self.client.post(
            '/api/v1/adom-institute/usage-ledger/',
            {'model_name': 'bad', 'total_tokens': 1},
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()['results']), 1)
        self.assertEqual(create_response.status_code, 405)

    def test_adom_institute_frontend_pages_render(self):
        document = KnowledgeDocument.objects.create(
            institution=self.institution,
            uploaded_by=self.teacher,
            title='Frontend ECZ Notes',
            source_type='curriculum',
            file=SimpleUploadedFile('frontend.txt', b'algebra frontend search'),
            processing_status=KnowledgeDocument.ProcessingStatus.READY,
        )
        KnowledgeChunk.objects.create(document=document, chunk_index=0, content='algebra frontend search')
        self.client.force_login(self.teacher)

        checks = [
            ('/adom-institute/', 'ADOM Institute'),
            ('/adom-institute/knowledge/', 'Knowledge Library'),
            ('/adom-institute/knowledge/search/?q=algebra', 'Frontend ECZ Notes'),
            (f'/adom-institute/knowledge/{document.pk}/', 'Frontend ECZ Notes'),
        ]
        for url, text in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_knowledge_document_upload_and_process_pages(self):
        self.client.force_login(self.teacher)

        upload_response = self.client.post(
            '/adom-institute/knowledge/upload/',
            {
                'institution': self.institution.pk,
                'title': 'Uploaded Frontend Notes',
                'source_type': 'course_material',
                'subject': 'Mathematics',
                'grade_level': '12',
                'access_scope': 'institution',
                'file': SimpleUploadedFile('uploaded.txt', b'quadratic equations and algebra'),
            },
        )

        self.assertEqual(upload_response.status_code, 302)
        document = KnowledgeDocument.objects.get(title='Uploaded Frontend Notes')
        detail_response = self.client.get(f'/adom-institute/knowledge/{document.pk}/')
        process_response = self.client.post(f'/adom-institute/knowledge/{document.pk}/process/')

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(process_response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.processing_status, KnowledgeDocument.ProcessingStatus.READY)
        self.assertGreater(document.chunks.count(), 0)

    def test_agent_frontend_pages_render_and_create_task(self):
        self.client.force_login(self.teacher)

        create_response = self.client.post(
            '/adom-institute/tasks/create/',
            {
                'institution': self.institution.pk,
                'agent_key': 'zambian_curriculum',
                'model_profile': 'reasoning',
                'input_payload': '{"subject": "Mathematics", "grade_level": "12"}',
            },
        )

        self.assertEqual(create_response.status_code, 302)
        task = AgentTask.objects.get(agent_key='zambian_curriculum')
        checks = [
            ('/adom-institute/agents/', 'Zambian Curriculum Agent'),
            ('/adom-institute/tasks/', 'Zambian Curriculum Agent'),
            (f'/adom-institute/tasks/{task.pk}/', 'Mathematics'),
        ]
        for url, text in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_usage_and_consent_frontend_pages_render(self):
        record_ai_usage(
            user=self.teacher,
            institution=self.institution,
            provider='ollama',
            model_name='qwen2.5:7b-instruct',
            prompt_tokens=5,
        )
        self.client.force_login(self.teacher)

        consent_response = self.client.post(
            '/adom-institute/consent/create/',
            {
                'institution': self.institution.pk,
                'status': 'granted',
                'allow_personalization': 'on',
                'allow_academic_analysis': 'on',
                'allow_opportunity_matching': 'on',
            },
        )

        self.assertEqual(consent_response.status_code, 302)
        checks = [
            ('/adom-institute/usage/', 'qwen2.5:7b-instruct'),
            ('/adom-institute/consent/', 'Consent Preferences'),
        ]
        for url, text in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_conversation_frontend_pages_render_and_add_message(self):
        self.client.force_login(self.teacher)
        create_response = self.client.post(
            '/adom-institute/conversations/create/',
            {
                'institution': self.institution.pk,
                'agent_key': 'learning_coach',
                'title': 'Study plan',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        conversation = self.teacher.ai_conversations.get(title='Study plan')
        message_response = self.client.post(
            f'/adom-institute/conversations/{conversation.pk}/messages/create/',
            {'content': 'Help me revise algebra.'},
        )
        self.assertEqual(message_response.status_code, 302)

        checks = [
            ('/adom-institute/conversations/', 'Study plan'),
            (f'/adom-institute/conversations/{conversation.pk}/', 'Help me revise algebra.'),
        ]
        for url, text in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_opportunity_hub_renders_scoped_opportunity_tasks(self):
        AgentTask.objects.create(
            institution=self.institution,
            created_by=self.teacher,
            agent_key='scholarship_opportunities',
            input_payload={'location': 'Zambia'},
        )
        self.client.force_login(self.teacher)

        response = self.client.get('/adom-institute/opportunities/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scholarships & Opportunities')
        self.assertContains(response, 'Zambia')
