from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSourceType:
    key: str
    description: str
    retention_policy: str
    access_scope: str


KNOWLEDGE_SOURCE_TYPES = (
    KnowledgeSourceType('course_material', 'Teacher-approved notes, slides, videos, and handouts.', 'Keep while course is active.', 'institution_course'),
    KnowledgeSourceType('policy', 'Institution policies, fee rules, conduct rules, and administrative guides.', 'Version permanently.', 'institution'),
    KnowledgeSourceType('past_paper', 'ECZ, college, and university past papers with marking schemes.', 'Version permanently.', 'institution_subject'),
    KnowledgeSourceType('curriculum', 'Syllabi, curriculum documents, outcomes, and lesson plans.', 'Version permanently.', 'institution_subject'),
    KnowledgeSourceType('research_paper', 'Academic research documents uploaded by staff or library teams.', 'Keep while licensed/approved.', 'institution_library'),
)


RAG_PIPELINE = (
    'upload_validation',
    'virus_scan',
    'ocr_if_scanned',
    'text_extraction',
    'metadata_extraction',
    'chunking',
    'embedding',
    'vector_index',
    'permission_filter',
    'hybrid_search',
    'reranking',
    'answer_generation_with_citations',
)


def get_rag_blueprint():
    return {
        'vector_store': 'PostgreSQL + pgvector for first production version; Qdrant when vector traffic outgrows app DB.',
        'embedding_model': 'BAAI/bge-m3 or intfloat/multilingual-e5-large',
        'reranker': 'BAAI/bge-reranker-v2-m3',
        'chunking': 'Semantic chunking with page/source metadata and institution-level permissions.',
        'pipeline': RAG_PIPELINE,
        'source_types': KNOWLEDGE_SOURCE_TYPES,
    }
