from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class OpenSourceModelProfile:
    key: str
    task: str
    default_model: str
    provider: str
    endpoint_setting: str
    context_window: int
    notes: str


MODEL_PROFILES = {
    'chat': OpenSourceModelProfile(
        key='chat',
        task='General tutoring, advising, and administrative chat',
        default_model='qwen2.5:7b-instruct',
        provider='ollama',
        endpoint_setting='OLLAMA_BASE_URL',
        context_window=32768,
        notes='Use Qwen, Llama, Mistral, or DeepSeek instruct models depending on local GPU capacity.',
    ),
    'reasoning': OpenSourceModelProfile(
        key='reasoning',
        task='Complex academic planning, risk analysis, and report generation',
        default_model='deepseek-r1:8b',
        provider='ollama',
        endpoint_setting='OLLAMA_BASE_URL',
        context_window=32768,
        notes='Use a distilled reasoning model for intervention planning where latency is acceptable.',
    ),
    'embedding': OpenSourceModelProfile(
        key='embedding',
        task='Knowledge-base retrieval embeddings',
        default_model='BAAI/bge-m3',
        provider='sentence-transformers',
        endpoint_setting='EMBEDDING_MODEL_PATH',
        context_window=8192,
        notes='Use bge-m3 or multilingual-e5 for English plus regional African education content.',
    ),
    'reranker': OpenSourceModelProfile(
        key='reranker',
        task='RAG result reranking',
        default_model='BAAI/bge-reranker-v2-m3',
        provider='sentence-transformers',
        endpoint_setting='RERANKER_MODEL_PATH',
        context_window=8192,
        notes='Rerank retrieved chunks before answer generation to reduce hallucinations.',
    ),
    'ocr': OpenSourceModelProfile(
        key='ocr',
        task='Past-paper, policy, and notes digitization',
        default_model='PaddleOCR',
        provider='local',
        endpoint_setting='OCR_ENGINE_PATH',
        context_window=0,
        notes='Use OCR before chunking ECZ past papers, syllabi, books, and scanned notes.',
    ),
}


def get_model_profile(task_key):
    return MODEL_PROFILES[task_key]


def get_ai_runtime_config():
    return {
        'enabled': getattr(settings, 'ADOM_INSTITUTE_AI_ENABLED', False),
        'default_chat_model': getattr(settings, 'ADOM_INSTITUTE_AI_CHAT_MODEL', MODEL_PROFILES['chat'].default_model),
        'default_embedding_model': getattr(settings, 'ADOM_INSTITUTE_AI_EMBEDDING_MODEL', MODEL_PROFILES['embedding'].default_model),
        'vector_store': getattr(settings, 'ADOM_INSTITUTE_AI_VECTOR_STORE', 'pgvector'),
        'provider': getattr(settings, 'ADOM_INSTITUTE_AI_PROVIDER', 'ollama'),
        'base_url': getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434'),
    }


def list_supported_model_profiles():
    return list(MODEL_PROFILES.values())
