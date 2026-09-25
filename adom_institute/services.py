import hashlib
from pathlib import Path

from django.db import transaction

from .models import AIUsageLedger, KnowledgeChunk, KnowledgeDocument
from .registry import get_ai_runtime_config


TEXT_EXTENSIONS = {'.txt', '.csv', '.md'}
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


class KnowledgeIngestionError(ValueError):
    pass


def calculate_file_checksum(file_field, algorithm='sha256'):
    hasher = hashlib.new(algorithm)
    file_field.open('rb')
    try:
        for chunk in file_field.chunks():
            hasher.update(chunk)
    finally:
        file_field.close()
    return hasher.hexdigest()


def extract_text_for_ingestion(document):
    extension = Path(document.file.name).suffix.lower()
    if extension not in TEXT_EXTENSIONS:
        raise KnowledgeIngestionError(
            'Only text-like files can be processed synchronously. OCR/document parsing is required for this file type.'
        )

    document.file.open('rb')
    try:
        raw = document.file.read()
    finally:
        document.file.close()

    for encoding in ('utf-8', 'utf-8-sig', 'latin-1'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise KnowledgeIngestionError('Unable to decode file content for ingestion.')


def chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP):
    normalized = ' '.join(text.split())
    if not normalized:
        return []
    if chunk_size <= overlap:
        raise KnowledgeIngestionError('Chunk size must be larger than overlap.')

    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = end - overlap
    return chunks


def search_knowledge_chunks(document_queryset, query, limit=10):
    query = (query or '').strip()
    if not query:
        raise KnowledgeIngestionError('Search query is required.')

    limit = max(1, min(int(limit), 25))
    chunks = KnowledgeChunk.objects.select_related('document').filter(
        document__in=document_queryset,
        document__processing_status=KnowledgeDocument.ProcessingStatus.READY,
        content__icontains=query,
    ).order_by('document_id', 'chunk_index')[:limit]

    return [
        {
            'document_id': chunk.document_id,
            'document_title': chunk.document.title,
            'source_type': chunk.document.source_type,
            'chunk_index': chunk.chunk_index,
            'content': chunk.content,
            'citation': {
                'document': chunk.document.title,
                'page': chunk.page_number,
                'chunk': chunk.chunk_index,
            },
        }
        for chunk in chunks
    ]


def record_ai_usage(*, user, institution=None, conversation=None, agent_task=None, provider='ollama',
                    model_name='', prompt_tokens=0, completion_tokens=0, latency_ms=0, metadata=None):
    prompt_tokens = int(prompt_tokens or 0)
    completion_tokens = int(completion_tokens or 0)
    return AIUsageLedger.objects.create(
        institution=institution,
        user=user,
        conversation=conversation,
        agent_task=agent_task,
        provider=provider,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=int(latency_ms or 0),
        estimated_cost=0,
        metadata=metadata or {},
    )


def ingest_knowledge_document(document_id):
    try:
        with transaction.atomic():
            document = KnowledgeDocument.objects.select_for_update().get(pk=document_id)
            document.processing_status = KnowledgeDocument.ProcessingStatus.INDEXING
            document.error_message = ''
            document.save(update_fields=['processing_status', 'error_message', 'updated_at'])

            checksum = calculate_file_checksum(document.file)
            text = extract_text_for_ingestion(document)
            chunks = chunk_text(text)
            if not chunks:
                raise KnowledgeIngestionError('No extractable text was found in the document.')

            KnowledgeChunk.objects.filter(document=document).delete()
            runtime = get_ai_runtime_config()
            chunk_objects = [
                KnowledgeChunk(
                    document=document,
                    chunk_index=index,
                    content=content,
                    embedding_model=runtime['default_embedding_model'],
                    embedding_vector=[],
                    metadata={
                        'embedding_status': 'pending',
                        'source_type': document.source_type,
                        'access_scope': document.access_scope,
                    },
                )
                for index, content in enumerate(chunks)
            ]
            KnowledgeChunk.objects.bulk_create(chunk_objects)

            document.checksum = checksum
            document.processing_status = KnowledgeDocument.ProcessingStatus.READY
            document.metadata = {
                **document.metadata,
                'chunk_count': len(chunk_objects),
                'extraction': 'text',
                'embedding_status': 'pending',
            }
            document.save(update_fields=['checksum', 'processing_status', 'metadata', 'updated_at'])
            return document
    except Exception as exc:
        document = KnowledgeDocument.objects.get(pk=document_id)
        document.processing_status = KnowledgeDocument.ProcessingStatus.FAILED
        document.error_message = str(exc)
        document.save(update_fields=['processing_status', 'error_message', 'updated_at'])
        raise
