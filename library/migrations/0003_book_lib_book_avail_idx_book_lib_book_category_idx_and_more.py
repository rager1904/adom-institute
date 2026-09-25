from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0002_alter_book_cover_image_alter_digitalresource_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex('book', models.Index(fields=['availability', 'is_active'], name='lib_book_avail_idx')),
        migrations.AddIndex('book', models.Index(fields=['category', 'is_active'], name='lib_book_category_idx')),
        migrations.AddIndex('bookborrowing', models.Index(fields=['borrower', 'return_date', 'due_date'], name='lib_borrow_user_idx')),
        migrations.AddIndex('bookborrowing', models.Index(fields=['book', 'return_date'], name='lib_borrow_book_idx')),
        migrations.AddIndex('bookreservation', models.Index(fields=['user', 'status'], name='lib_reserve_user_idx')),
        migrations.AddIndex('bookreservation', models.Index(fields=['book', 'status'], name='lib_reserve_book_idx')),
        migrations.AddIndex('digitalresource', models.Index(fields=['access_level', 'is_active'], name='lib_resource_access_idx')),
        migrations.AddIndex('digitalresource', models.Index(fields=['resource_type', 'is_active'], name='lib_resource_type_idx')),
        migrations.AddIndex('digitalresourceaccess', models.Index(fields=['resource', 'action', 'access_date'], name='lib_access_resource_idx')),
        migrations.AddIndex('digitalresourceaccess', models.Index(fields=['user', 'access_date'], name='lib_access_user_idx')),
        migrations.AddIndex('libraryreport', models.Index(fields=['report_type', 'report_date'], name='lib_report_type_idx')),
        migrations.AddConstraint(
            'book',
            models.CheckConstraint(check=models.Q(price__isnull=True) | models.Q(price__gte=0), name='lib_book_price_ck'),
        ),
        migrations.AddConstraint(
            'bookborrowing',
            models.CheckConstraint(
                check=models.Q(return_date__isnull=True) | models.Q(return_date__gte=models.F('borrowed_date')),
                name='lib_borrow_return_ck',
            ),
        ),
        migrations.AddConstraint(
            'bookborrowing',
            models.CheckConstraint(check=models.Q(due_date__gte=models.F('borrowed_date')), name='lib_borrow_due_ck'),
        ),
        migrations.AddConstraint('bookborrowing', models.CheckConstraint(check=models.Q(late_fee__gte=0), name='lib_borrow_fee_ck')),
        migrations.AddConstraint(
            'bookreservation',
            models.CheckConstraint(check=models.Q(expiry_date__gte=models.F('reservation_date')), name='lib_reserve_expiry_ck'),
        ),
        migrations.AddConstraint(
            'digitalresource',
            models.CheckConstraint(
                check=models.Q(current_downloads__lte=models.F('download_limit')) | models.Q(download_limit__isnull=True),
                name='lib_resource_dl_ck',
            ),
        ),
    ]
