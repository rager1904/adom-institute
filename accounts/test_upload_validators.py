from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from accounts.validators import MAX_DOCUMENT_UPLOAD_SIZE, validate_document_size, validate_safe_filename


class UploadValidatorTests(SimpleTestCase):
    def test_safe_filename_rejects_path_segments(self):
        with self.assertRaises(ValidationError):
            validate_safe_filename(SimpleNamespace(name='../payload.pdf', size=10))

    def test_safe_filename_rejects_null_byte(self):
        with self.assertRaises(ValidationError):
            validate_safe_filename(SimpleNamespace(name='payload\x00.pdf', size=10))

    def test_document_size_rejects_oversized_upload(self):
        oversized = SimpleUploadedFile('large.pdf', b'x')
        oversized.size = MAX_DOCUMENT_UPLOAD_SIZE + 1

        with self.assertRaises(ValidationError):
            validate_document_size(oversized)
