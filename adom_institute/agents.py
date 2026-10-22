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


# Agents that only support a learner or a member of staff one to one. They
# never change institutional data, so every role may use them.
STUDENT_AGENT_KEYS = frozenset({
    'student_success',
    'learning_coach',
    'research',
    'career_guidance',
    'scholarship_opportunities',
})

# Agents that prepare content for staff. They still work on the institution's
# material, so students are kept away from them.
STAFF_AGENT_KEYS = frozenset({
    'assessment',
    'academic_integrity',
    'content_management',
    'zambian_curriculum',
})

# Agents that act on the institution itself. Only administrators may run them.
ADMIN_AGENT_KEYS = frozenset({
    'administrative',
})

# Agents that change shared data and therefore need a human to approve the
# result before it is applied.
HUMAN_APPROVAL_AGENT_KEYS = frozenset({
    'assessment',
    'academic_integrity',
    'content_management',
    'administrative',
    'zambian_curriculum',
})


def agent_keys_for_role(user):
    """Return the agent keys the given user may queue or talk to.

    Platform administrators may use every agent. Teachers and other staff
    members may use the student agents plus the content agents, and only
    administrators may use the administrative agent.
    """
    from accounts.permissions import is_admin_user, is_platform_admin, is_teacher_user

    if is_platform_admin(user):
        return frozenset(AGENT_DEFINITIONS)
    if is_admin_user(user):
        return frozenset(AGENT_DEFINITIONS) - ADMIN_AGENT_KEYS
    if is_teacher_user(user):
        return STUDENT_AGENT_KEYS | STAFF_AGENT_KEYS
    return STUDENT_AGENT_KEYS


def agent_choices_for_user(user):
    """Return the (key, label) choices the given user may pick."""
    allowed = agent_keys_for_role(user)
    return [
        (key, definition.name)
        for key, definition in AGENT_DEFINITIONS.items()
        if key in allowed
    ]


def requires_human_approval(agent_key):
    """Whether the given agent should be reviewed by a human by default."""
    return agent_key in HUMAN_APPROVAL_AGENT_KEYS
