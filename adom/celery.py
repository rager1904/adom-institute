import importlib
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


def _task_available(module_path, attr):
    """True only if the referenced Celery task module/attribute actually exists.

    Guards the beat schedule so that a task defined in the roadmap but not yet
    implemented cannot crash beat or spam workers with "unregistered task"
    errors in production.
    """
    try:
        return hasattr(importlib.import_module(module_path), attr)
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False


# Celery Beat Schedule
# Entries for tasks that are not yet implemented are skipped automatically.
_SCHEDULE_CANDIDATES = {
    'send-fee-reminders': ('fees.tasks', 'send_fee_reminders', 86400.0),        # Daily
    'send-attendance-alerts': ('attendance.tasks', 'send_attendance_alerts', 86400.0),  # Daily
    'generate-daily-reports': ('analytics.tasks', 'generate_daily_reports', 86400.0),   # Daily
    'cleanup-old-files': ('utils.tasks', 'cleanup_old_files', 604800.0),        # Weekly
}

app.conf.beat_schedule = {
    name: {
        'task': f'{module}.{attr}',
        'schedule': interval,
    }
    for name, (module, attr, interval) in _SCHEDULE_CANDIDATES.items()
    if _task_available(module, attr)
}