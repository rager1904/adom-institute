"""Read-only, authenticated delivery of learning-material files.

Learning materials (library digital resources, assignment attachments and
student submissions) must not be reachable through the public ``/media/``
route, and must never be delivered with a ``Content-Disposition: attachment``
header. Everything in this module exists to funnel those files through
authenticated, inline-only responses served by Django itself.

Two settings drive the policy:

``ALLOW_MATERIAL_DOWNLOADS``
    Defaults to ``False``. When false, download endpoints refuse to serve an
    attachment and the UI never offers a download affordance.

``MATERIALS_READ_ONLY``
    Defaults to ``True``. When true, only administrators and teachers may
    upload, edit or delete material.

Note: no web application can stop a user from saving or screenshotting content
the browser is able to render. What this module guarantees is that the platform
itself provides no download path, never exposes the raw file URL, and never
lets a browser or proxy cache a copy of the material.
"""

import mimetypes
import re
from urllib.parse import quote

from django.conf import settings
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    StreamingHttpResponse,
)
from django.utils.http import http_date
from django.views.static import serve as django_serve

# Directories under MEDIA_ROOT that hold learning material. They mirror the
# ``upload_to`` values declared on the models and must never be served by the
# public media route.
_PROTECTED_ROOT_DIRS = frozenset({
    'assignments',             # academics.models.Assignment.attachment
    'assignment_submissions',  # academics.models.StudentAssignment.submission_file
})
_PROTECTED_NESTED_DIRS = frozenset({
    'library/digital',         # library.models.DigitalResource.file
})

# Anything a browser cannot render itself. Served with a neutral type and
# ``nosniff`` so it is never silently opened as active content.
_OPAQUE_CONTENT_TYPE = 'application/octet-stream'

_RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')
_STREAM_CHUNK_SIZE = 64 * 1024


def is_protected_media_path(path):
    """Return True when ``path`` (relative to MEDIA_ROOT) holds material."""
    normalized = str(path or '').replace('\\', '/').strip('/')
    if not normalized:
        return False
    parts = normalized.split('/')
    if parts[0] in _PROTECTED_ROOT_DIRS:
        return True
    return '/'.join(parts[:2]) in _PROTECTED_NESTED_DIRS


def material_downloads_allowed():
    """True only when the operator has explicitly re-enabled downloads."""
    return bool(getattr(settings, 'ALLOW_MATERIAL_DOWNLOADS', False))


def guess_material_content_type(name):
    """Best-effort inline content type for a stored material file."""
    guessed, _encoding = mimetypes.guess_type(name or '')
    return guessed or _OPAQUE_CONTENT_TYPE


def _content_disposition(filename, attachment):
    """Build an RFC 6266 ``Content-Disposition`` value."""
    safe_name = (
        (filename or 'material')
        .replace('"', '')
        .replace('\\', '')
        .replace('\r', '')
        .replace('\n', '')
    )
    disposition = 'attachment' if attachment else 'inline'
    return f"{disposition}; filename=\"{safe_name}\"; filename*=UTF-8''{quote(safe_name)}"


def _apply_no_store(response):
    """Strip every caching path a browser or CDN could use to keep a copy."""
    response['Cache-Control'] = 'private, no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    # Block plugins, framing by third parties and outbound calls from the file.
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response


def _parse_byte_range(header, size):
    """Parse a single ``Range: bytes=`` header.

    Returns ``None`` when there is no usable range, ``'unsatisfiable'`` when the
    range cannot be served, or a ``(start, end)`` inclusive tuple.
    """
    if not header:
        return None
    match = _RANGE_RE.match(header.strip())
    if not match:
        return None
    first, last = match.group(1), match.group(2)
    if not first and not last:
        return None
    try:
        if not first:
            # Suffix range: the final ``last`` bytes.
            suffix_length = int(last)
            if suffix_length <= 0:
                return None
            start = max(size - suffix_length, 0)
            end = size - 1
        else:
            start = int(first)
            end = int(last) if last else size - 1
    except ValueError:
        return None
    end = min(end, size - 1)
    if start > end or start >= size:
        return 'unsatisfiable'
    return start, end


class _RangedFileStream:
    """Iterator over a byte range of a file that closes itself when exhausted.

    ``FileResponse`` owns its file handle, but a hand-rolled
    ``StreamingHttpResponse`` does not, so the handle is managed here instead
    of being closed before the iterator is ever consumed.
    """

    def __init__(self, field_file, start, length):
        self._field_file = field_file
        self._position = start
        self._remaining = length
        self._finished = False

    def __iter__(self):
        return self

    def __next__(self):
        if self._remaining <= 0:
            self.close()
            raise StopIteration
        chunk = self._field_file.read(min(_STREAM_CHUNK_SIZE, self._remaining))
        if not chunk:
            self.close()
            raise StopIteration
        self._remaining -= len(chunk)
        return chunk

    def close(self):
        if not self._finished:
            self._finished = True
            try:
                self._field_file.close()
            except (OSError, ValueError):
                pass


def _ranged_file_response(field_file, start, end, total, content_type, filename, attachment):
    """Serve bytes ``start``..``end`` of ``field_file`` so media can seek."""
    field_file.open('rb')
    try:
        field_file.seek(start)
    except (OSError, ValueError):
        field_file.close()
        raise
    length = end - start + 1
    stream = _RangedFileStream(field_file, start, length)
    response = StreamingHttpResponse(stream, content_type=content_type)
    response._resource_closers.append(stream.close)
    response['Content-Length'] = str(length)
    response['Content-Range'] = f'bytes {start}-{end}/{total}'
    response.status_code = 206
    response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = _content_disposition(filename, attachment)
    return _apply_no_store(response)


def protected_file_response(field_file, *, request=None, filename=None, attachment=False):
    """Return an inline, non-cacheable response for a material ``FieldFile``.

    ``attachment=True`` is only honoured when ``ALLOW_MATERIAL_DOWNLOADS`` is
    enabled; otherwise the file is always delivered inline.
    """
    if not field_file:
        raise Http404('No file is attached to this record.')

    stored_name = field_file.name.rsplit('/', 1)[-1]
    display_name = filename or stored_name
    try:
        total = field_file.size
    except (OSError, ValueError):
        total = None

    attachment = attachment and material_downloads_allowed()
    # Guess from the stored name so a friendly display title never strips the
    # extension the browser needs in order to render the file inline.
    content_type = guess_material_content_type(stored_name)
    if content_type == _OPAQUE_CONTENT_TYPE:
        content_type = guess_material_content_type(display_name)

    if not total:
        # Size is unknown (remote storage without a reported length): send the
        # whole stream rather than guessing a Content-Length.
        response = FileResponse(field_file.open('rb'), content_type=content_type)
        response['Accept-Ranges'] = 'none'
        response['Content-Disposition'] = _content_disposition(display_name, attachment)
        return _apply_no_store(response)

    # Conditional requests are deliberately ignored: answering 304 would let a
    # client keep using a copy it already holds.
    range_header = request.META.get('HTTP_RANGE', '') if request is not None else ''
    byte_range = _parse_byte_range(range_header, total)
    if byte_range == 'unsatisfiable':
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{total}'
        return _apply_no_store(response)
    if byte_range is not None:
        start, end = byte_range
        return _ranged_file_response(
            field_file, start, end, total, content_type, display_name, attachment,
        )

    response = FileResponse(field_file.open('rb'), content_type=content_type)
    response['Content-Length'] = str(total)
    response['Accept-Ranges'] = 'bytes'
    try:
        modified_at = field_file.storage.get_modified_time(field_file.name)
    except (NotImplementedError, OSError, ValueError):
        modified_at = None
    if modified_at is not None:
        response['Last-Modified'] = http_date(modified_at.timestamp())
    response['Content-Disposition'] = _content_disposition(display_name, attachment)
    return _apply_no_store(response)


def serve_public_media(request, path, document_root=None, show_indexes=False):
    """Replacement for ``django.conf.urls.static.static()`` in DEBUG.

    Behaves exactly like Django's static media view except that learning
    material paths 404 instead of being served, which keeps material
    unreachable even when someone guesses the raw ``/media/`` URL.
    """
    if is_protected_media_path(path):
        raise Http404('Learning material is served through the authenticated read-only viewer.')
    return django_serve(
        request,
        path,
        document_root=document_root or settings.MEDIA_ROOT,
        show_indexes=show_indexes,
    )
