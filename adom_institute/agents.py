from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    name: str
    purpose: str
    responsibilities: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    tools: tuple[str, ...]
    model_profile: str


AGENT_DEFINITIONS = {
    'student_success': AgentDefinition(
        key='student_success',
        name='Student Success Agent',
        purpose='Detect academic risk early and recommend interventions.',
        responsibilities=('Monitor grades', 'Monitor attendance', 'Flag risk', 'Recommend interventions'),
        inputs=('exam_results', 'attendance', 'assignments', 'fees', 'teacher_notes'),
        outputs=('risk_score', 'intervention_plan', 'guardian_summary'),
        tools=('analytics_queries', 'notification_service', 'report_generator'),
        model_profile='reasoning',
    ),
    'assessment': AgentDefinition(
        key='assessment',
        name='Assessment Agent',
        purpose='Generate quizzes, exams, marking schemes, and explanations aligned to curriculum.',
        responsibilities=('Generate questions', 'Create marking schemes', 'Explain answers', 'Balance difficulty'),
        inputs=('syllabus', 'lesson_notes', 'past_papers', 'learning_objectives'),
        outputs=('quiz', 'exam', 'rubric', 'answer_explanations'),
        tools=('rag_search', 'question_bank', 'export_service'),
        model_profile='reasoning',
    ),
    'learning_coach': AgentDefinition(
        key='learning_coach',
        name='Learning Coach Agent',
        purpose='Create adaptive study plans and resource recommendations.',
        responsibilities=('Plan study sessions', 'Recommend resources', 'Track progress', 'Adjust workload'),
        inputs=('student_profile', 'performance_history', 'deadlines', 'knowledge_gaps'),
        outputs=('study_plan', 'resource_list', 'progress_summary'),
        tools=('calendar_service', 'rag_search', 'progress_tracker'),
        model_profile='chat',
    ),
    'research': AgentDefinition(
        key='research',
        name='Research Agent',
        purpose='Help students and staff search, summarize, and explain academic sources.',
        responsibilities=('Search sources', 'Summarize papers', 'Explain concepts', 'Cite evidence'),
        inputs=('research_question', 'approved_sources', 'uploaded_documents'),
        outputs=('source_summary', 'concept_explanation', 'citation_pack'),
        tools=('academic_search', 'rag_search', 'citation_formatter'),
        model_profile='chat',
    ),
    'career_guidance': AgentDefinition(
        key='career_guidance',
        name='Career Guidance Agent',
        purpose='Recommend careers, improve CVs, and match opportunities.',
        responsibilities=('Recommend careers', 'Review CVs', 'Match internships', 'Suggest scholarships'),
        inputs=('student_interests', 'grades', 'skills', 'location', 'opportunity_feed'),
        outputs=('career_plan', 'cv_feedback', 'opportunity_matches'),
        tools=('opportunity_search', 'document_review', 'notification_service'),
        model_profile='chat',
    ),
    'academic_integrity': AgentDefinition(
        key='academic_integrity',
        name='Academic Integrity Agent',
        purpose='Support plagiarism, AI-content, and misconduct review workflows.',
        responsibilities=('Compare submissions', 'Flag similarity', 'Explain evidence', 'Route review'),
        inputs=('submission', 'source_corpus', 'rubric', 'student_history'),
        outputs=('integrity_report', 'evidence_links', 'review_recommendation'),
        tools=('similarity_search', 'document_parser', 'case_manager'),
        model_profile='reasoning',
    ),
    'content_management': AgentDefinition(
        key='content_management',
        name='Content Management Agent',
        purpose='Organize, classify, and tag institutional learning resources.',
        responsibilities=('Classify resources', 'Extract metadata', 'Auto-tag content', 'Detect duplicates'),
        inputs=('uploaded_file', 'course_catalog', 'curriculum_map'),
        outputs=('metadata', 'tags', 'recommended_folder', 'duplicate_warning'),
        tools=('ocr', 'document_parser', 'rag_indexer'),
        model_profile='embedding',
    ),
    'administrative': AgentDefinition(
        key='administrative',
        name='Administrative Agent',
        purpose='Assist registration, timetable, fee reminders, and notifications.',
        responsibilities=('Draft reminders', 'Support registration', 'Prepare timetables', 'Route notices'),
        inputs=('student_records', 'fee_records', 'calendar', 'communication_policy'),
        outputs=('draft_message', 'task_queue', 'exception_report'),
        tools=('workflow_engine', 'notification_service', 'scheduler'),
        model_profile='chat',
    ),
    'zambian_curriculum': AgentDefinition(
        key='zambian_curriculum',
        name='Zambian Curriculum Agent',
        purpose='Align learning content to ECZ syllabi, curriculum outcomes, and past papers.',
        responsibilities=('Map topics to ECZ outcomes', 'Suggest past-paper practice', 'Generate curriculum-aligned explanations'),
        inputs=('ecz_syllabus', 'past_papers', 'grade_level', 'subject', 'student_gap'),
        outputs=('curriculum_map', 'practice_set', 'topic_explanation'),
        tools=('institutional_rag', 'past_paper_index', 'assessment_generator'),
        model_profile='reasoning',
    ),
    'scholarship_opportunities': AgentDefinition(
        key='scholarship_opportunities',
        name='Scholarship & Opportunities Agent',
        purpose='Match students to scholarships, internships, competitions, grants, and jobs across Africa.',
        responsibilities=('Scan opportunity feeds', 'Match eligibility', 'Rank deadlines', 'Draft application checklists'),
        inputs=('student_profile', 'eligibility_data', 'location', 'opportunity_sources'),
        outputs=('opportunity_matches', 'deadline_alerts', 'application_checklist'),
        tools=('opportunity_crawler', 'eligibility_matcher', 'notification_service'),
        model_profile='chat',
    ),
}


def list_agent_definitions():
    return list(AGENT_DEFINITIONS.values())


def get_agent_definition(agent_key):
    return AGENT_DEFINITIONS[agent_key]
