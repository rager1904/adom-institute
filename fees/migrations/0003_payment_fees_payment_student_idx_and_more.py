from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fees', '0002_receiptsequence'),
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex('payment', models.Index(fields=['student', 'payment_status', 'payment_date'], name='fees_payment_student_idx')),
        migrations.AddIndex('studentfee', models.Index(fields=['payment_status', 'due_date'], name='fees_status_due_idx')),
        migrations.AddIndex('studentfee', models.Index(fields=['student', 'payment_status'], name='fees_student_status_idx')),
        migrations.AddConstraint('feediscount', models.CheckConstraint(check=models.Q(discount_value__gte=0), name='fees_discount_value_ck')),
        migrations.AddConstraint('feestructuredetail', models.CheckConstraint(check=models.Q(amount__gte=0), name='fees_detail_amount_ck')),
        migrations.AddConstraint('payment', models.CheckConstraint(check=models.Q(amount__gt=0), name='fees_payment_amount_ck')),
        migrations.AddConstraint('studentfee', models.CheckConstraint(check=models.Q(amount__gte=0), name='fees_student_amount_ck')),
        migrations.AddConstraint('studentfee', models.CheckConstraint(check=models.Q(paid_amount__gte=0), name='fees_student_paid_ck')),
        migrations.AddConstraint(
            'studentfee',
            models.CheckConstraint(check=models.Q(paid_amount__lte=models.F('amount')), name='fees_student_balance_ck'),
        ),
        migrations.AddConstraint('studentfeediscount', models.CheckConstraint(check=models.Q(discount_amount__gte=0), name='fees_student_disc_ck')),
    ]
