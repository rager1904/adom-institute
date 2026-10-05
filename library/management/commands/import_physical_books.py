from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import transaction
from library.models import Book, BookCategory
import os

PHYSICAL_MEDIA_BASE = os.path.join('media', 'library', 'pysical', 'media')
CATEGORY_MAP = {
    '3-4 years': 'Early Childhood (3-4 years)',
    '4-5 years': 'Early Childhood (4-5 years)',
    'grade 1': 'Primary - Grade 1',
    'grade 4': 'Primary - Grade 4',
    'form 1': 'Secondary - Form 1',
    'form 2': 'Secondary - Form 2',
}


def _clean_title(filename):
    name = os.path.splitext(filename)[0]
    return name.strip()


class Command(BaseCommand):
    help = 'Import physical library books from media/library/pysical/media as the source of truth'

    def add_arguments(self, parser):
        parser.add_argument('--clear-existing', action='store_true', help='Delete existing books and categories before import')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear_existing']:
            self.stdout.write('Clearing existing books and categories...')
            Book.objects.all().delete()
            BookCategory.objects.all().delete()

        category_objs = {}
        for key, display in CATEGORY_MAP.items():
            cat, _ = BookCategory.objects.get_or_create(
                name=display,
                defaults={'description': f'Books for {display}', 'color': '#007bff'}
            )
            category_objs[key] = cat

        base_path = PHYSICAL_MEDIA_BASE
        if not os.path.isabs(base_path):
            base_path = os.path.join(os.getcwd(), base_path)

        count = 0
        for root, dirs, filenames in os.walk(base_path):
            for fname in filenames:
                if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    continue
                rel_path = os.path.relpath(root, base_path)
                cat_key = rel_path.replace('\\', '/').lower()
                matched = None
                for k in CATEGORY_MAP.keys():
                    if cat_key == k or cat_key.startswith(k):
                        matched = k
                        break
                if matched is None:
                    if '3-4' in cat_key:
                        matched = '3-4 years'
                    elif '4-5' in cat_key:
                        matched = '4-5 years'
                    elif 'grade 1' in cat_key:
                        matched = 'grade 1'
                    elif 'grade 4' in cat_key:
                        matched = 'grade 4'
                    elif 'form 1' in cat_key:
                        matched = 'form 1'
                    elif 'form 2' in cat_key:
                        matched = 'form 2'

                if matched is None:
                    self.stdout.write(self.style.WARNING(f'Skipping {fname} (could not match category)'))
                    continue

                full_path = os.path.join(root, fname)
                title = _clean_title(fname)
                book = Book(
                    title=title,
                    author='Zambian Curriculum',
                    category=category_objs[matched],
                    description=f'Physical library book: {title}',
                    availability='available',
                    condition='good',
                    is_active=True,
                )
                try:
                    with open(full_path, 'rb') as f:
                        book.cover_image.save(fname, File(f), save=True)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not save cover for {fname}: {e}'))
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Imported: {title} -> {matched}'))

        self.stdout.write(self.style.SUCCESS(f'Imported {count} books from physical media'))
