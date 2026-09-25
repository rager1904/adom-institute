import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adom.settings')

app = Celery('adom')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Celery Beat Schedule
app.conf.beat_schedule = {
    'send-fee-reminders': {
        'task': 'fees.tasks.send_fee_reminders',
        'schedule': 86400.0,  # Daily
    },
    'send-attendance-alerts': {
        'task': 'attendance.tasks.send_attendance_alerts',
        'schedule': 86400.0,  # Daily
    },
    'generate-daily-reports': {
        'task': 'analytics.tasks.generate_daily_reports',
        'schedule': 86400.0,  # Daily
    },
    'cleanup-old-files': {
        'task': 'utils.tasks.cleanup_old_files',
        'schedule': 604800.0,  # Weekly
    },
}
