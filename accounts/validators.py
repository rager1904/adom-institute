from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible


IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv']
LEARNING_RESOURCE_EXTENSIONS = DOCUMENT_EXTENSIONS + ['mp4', 'mp3', 'wav']

MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_RESOURCE_UPLOAD_SIZE = 100 * 1024 * 1024


@deconstructible
class FileSizeValidator:
    def __init__(self, max_size):
        self.max_size = max_size

    def __call__(self, file_obj):
        if file_obj.size > self.max_size:
            max_size_mb = self.max_size / (1024 * 1024)
            raise ValidationError(f'File size cannot exceed {max_size_mb:.0f} MB.')

    def __eq__(self, other):
        return isinstance(other, FileSizeValidator) and self.max_size == other.max_size


def validate_safe_filename(file_obj):
    name = Path(file_obj.name).name
    if name != file_obj.name or '\x00' in file_obj.name:
        raise ValidationError('Invalid file name.')


validate_image_extension = FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)
validate_document_extension = FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS)
validate_learning_resource_extension = FileExtensionValidator(allowed_extensions=LEARNING_RESOURCE_EXTENSIONS)

validate_image_size = FileSizeValidator(MAX_IMAGE_UPLOAD_SIZE)
validate_document_size = FileSizeValidator(MAX_DOCUMENT_UPLOAD_SIZE)
validate_resource_size = FileSizeValidator(MAX_RESOURCE_UPLOAD_SIZE)

image_upload_validators = [validate_safe_filename, validate_image_extension, validate_image_size]
document_upload_validators = [validate_safe_filename, validate_document_extension, validate_document_size]
resource_upload_validators = [validate_safe_filename, validate_learning_resource_extension, validate_resource_size]
