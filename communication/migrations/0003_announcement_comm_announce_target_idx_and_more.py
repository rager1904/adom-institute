from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0002_alter_announcement_attachment_and_more'),
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex('announcement', models.Index(fields=['target_audience', 'is_published', 'expires_at'], name='comm_announce_target_idx')),
        migrations.AddIndex('announcement', models.Index(fields=['announcement_type', 'is_published'], name='comm_announce_type_idx')),
        migrations.AddIndex('communicationlog', models.Index(fields=['recipient', 'status', 'created_at'], name='comm_log_recipient_idx')),
        migrations.AddIndex('communicationlog', models.Index(fields=['communication_type', 'status'], name='comm_log_type_idx')),
        migrations.AddIndex('emailtemplate', models.Index(fields=['template_type', 'is_active'], name='comm_email_template_idx')),
        migrations.AddIndex('message', models.Index(fields=['sender', 'status', 'sent_at'], name='comm_message_sender_idx')),
        migrations.AddIndex('message', models.Index(fields=['message_type', 'sent_at'], name='comm_message_type_idx')),
        migrations.AddIndex('messagerecipient', models.Index(fields=['recipient', 'is_read', 'is_deleted'], name='comm_recipient_state_idx')),
        migrations.AddIndex('notification', models.Index(fields=['recipient', 'status', 'created_at'], name='comm_notif_recipient_idx')),
        migrations.AddIndex('notification', models.Index(fields=['notification_type', 'status'], name='comm_notif_type_idx')),
        migrations.AddIndex('smstemplate', models.Index(fields=['template_type', 'is_active'], name='comm_sms_template_idx')),
        migrations.AddConstraint(
            'announcement',
            models.CheckConstraint(
                check=(
                    models.Q(expires_at__isnull=True)
                    | models.Q(expires_at__gte=models.F('published_at'))
                    | models.Q(published_at__isnull=True)
                ),
                name='comm_announce_expiry_ck',
            ),
        ),
    ]
