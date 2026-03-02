---
name: django_background_tasks
description: Enterprise Celery background task design — task architecture, idempotency, retry strategies, monitoring, and async offloading patterns for Django 6.
---

# Django Background Tasks Skill

## Purpose

Define and enforce standards for designing, implementing, and operating Celery background tasks in a Django 6 system, ensuring reliability, idempotency, observability, and proper integration with the notification and SSE subsystems.

## Scope

- Celery task design and organization
- Task idempotency and retry strategies
- Task prioritization and routing
- Periodic task scheduling (Celery Beat)
- Integration with Django ORM and Redis
- Error handling and dead letter queues
- Monitoring and alerting
- Async offloading patterns

## Responsibilities

1. ENFORCE idempotent task design.
2. ENFORCE retry strategies with exponential backoff.
3. ENFORCE task timeout limits.
4. ENFORCE proper serialization (JSON only, never pickle).
5. ENFORCE monitoring and alerting for task failures.
6. PREVENT long-running tasks without progress tracking.
7. PREVENT tasks that hold database transactions open.
8. PREVENT unbounded task queues.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS make tasks idempotent — safe to execute multiple times with the same arguments:
   ```python
   @shared_task(bind=True, max_retries=3)
   def send_notification_email(self, notification_id: int):
       notification = Notification.objects.get(id=notification_id)
       if notification.email_sent:
           return  # Idempotent: already processed
       # Send email...
       notification.email_sent = True
       notification.save(update_fields=['email_sent'])
   ```
2. ALWAYS use `shared_task` with `bind=True` for access to `self` (retry, task ID).
3. ALWAYS pass primitive types (int, str, float, bool, list, dict) as task arguments. NEVER pass model instances or querysets:
   ```python
   # CORRECT
   send_notification_email.delay(notification_id=123)
   # WRONG — model instance is not JSON-serializable
   send_notification_email.delay(notification=notification_obj)
   ```
4. ALWAYS set `task_serializer = 'json'` and `accept_content = ['json']` in Celery config. Never use pickle serialization.
5. ALWAYS set task time limits:
   ```python
   @shared_task(bind=True, time_limit=300, soft_time_limit=240)
   def process_grades(self, semester_id: int):
       ...
   ```
6. ALWAYS implement retry with exponential backoff:
   ```python
   @shared_task(bind=True, max_retries=5, default_retry_delay=60)
   def sync_external_data(self, source_id: int):
       try:
           # ... operation
       except TemporaryError as exc:
           raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
   ```
7. ALWAYS use `transaction.on_commit()` to dispatch tasks after database transactions:
   ```python
   def create_notification(recipient, notification_type, title, message, **kwargs):
       with transaction.atomic():
           notification = Notification.objects.create(...)
       # Dispatch AFTER commit — ensures notification exists when task runs
       transaction.on_commit(lambda: broadcast_notification.delay(notification.id))
       return notification
   ```
8. ALWAYS log task start, completion, and failure with task ID and arguments:
   ```python
   @shared_task(bind=True)
   def process_task(self, item_id: int):
       logger.info(f"Task {self.request.id} started: process_task(item_id={item_id})")
       try:
           # ... work
           logger.info(f"Task {self.request.id} completed successfully")
       except Exception as e:
           logger.error(f"Task {self.request.id} failed: {str(e)}")
           raise
   ```
9. ALWAYS organize tasks by app:
   ```
   <app>/tasks/
   ├── __init__.py
   ├── notification_tasks.py
   ├── cleanup_tasks.py
   └── report_tasks.py
   ```
10. ALWAYS use task routing for priority separation:
    ```python
    # celery.py
    task_routes = {
        'notifications.tasks.*': {'queue': 'notifications'},
        'reports.tasks.*': {'queue': 'reports'},
        'cleanup.tasks.*': {'queue': 'maintenance'},
    }
    ```
11. ALWAYS set `task_acks_late = True` for critical tasks so they are re-delivered if the worker crashes.
12. ALWAYS use Celery Beat for periodic tasks (cleanup, reminders, health checks). Never use cron to call management commands for scheduled work.

### NEVER

1. NEVER pass ORM objects, querysets, or request objects as task arguments.
2. NEVER use pickle serialization. JSON only.
3. NEVER run long database transactions inside tasks. Fetch, process, update in small batches.
4. NEVER dispatch Celery tasks inside `transaction.atomic()` — use `transaction.on_commit()`.
5. NEVER create tasks without timeout limits.
6. NEVER retry indefinitely. Always set `max_retries`.
7. NEVER silently swallow exceptions in tasks. Log and re-raise, or handle explicitly.
8. NEVER use `delay()` in synchronous request hot paths for work that the user is waiting for. Use it only for fire-and-forget work.
9. NEVER store large payloads in task arguments (>10KB). Store in database/S3 and pass the reference ID.
10. NEVER use `apply()` (synchronous execution) in production. Use `delay()` or `apply_async()`.

---

## Task Architecture

### Task Categories

| Category | Queue | Priority | Examples |
|---|---|---|---|
| Real-time | `notifications` | High | SSE broadcast, push notifications |
| Standard | `default` | Normal | Email sending, report generation |
| Maintenance | `maintenance` | Low | Cleanup, archival, statistics |
| Scheduled | `beat` | Normal | Reminders, periodic checks |

### Celery Configuration

```python
# celery.py
from celery import Celery
from django.conf import settings

app = Celery('cms')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Settings
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/2')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_TIME_LIMIT = 600     # 10 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 540  # 9 minutes soft limit
```

---

## Periodic Tasks (Celery Beat)

```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_expired_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM UTC
    },
    'cleanup-stale-sse-connections': {
        'task': 'notifications.tasks.cleanup_stale_connections',
        'schedule': 300.0,  # Every 5 minutes
    },
    'send-assignment-reminders': {
        'task': 'assignments.tasks.send_due_soon_reminders',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}
```

---

## Error Handling

1. Use `autoretry_for` for known transient errors:
   ```python
   @shared_task(
       bind=True,
       autoretry_for=(ConnectionError, TimeoutError),
       retry_backoff=True,
       retry_backoff_max=600,
       max_retries=5,
   )
   def external_api_call(self, endpoint_id: int):
       ...
   ```
2. Implement dead letter handling for tasks that exceed max retries:
   ```python
   @shared_task(bind=True, max_retries=3)
   def critical_task(self, item_id: int):
       try:
           ...
       except Exception as exc:
           if self.request.retries >= self.max_retries:
               # Send to dead letter queue / alert
               logger.critical(f"Task permanently failed after {self.max_retries} retries: {item_id}")
               alert_ops_team(task_name='critical_task', item_id=item_id, error=str(exc))
               return
           raise self.retry(exc=exc)
   ```

---

## Security Considerations

1. Never log sensitive task arguments (tokens, passwords, PII).
2. Use separate Redis databases for Celery broker and result backend.
3. Restrict Flower (Celery monitoring) access with authentication.
4. Validate task arguments at the start of every task — don't trust caller input.

---

## Performance Considerations

1. Batch database operations inside tasks — use `bulk_create`, `bulk_update`.
2. Use `prefetch_related` and `select_related` for queries inside tasks.
3. For large datasets, process in chunks with progress tracking:
   ```python
   @shared_task(bind=True)
   def process_large_dataset(self, dataset_id: int, batch_size: int = 1000):
       total = Item.objects.filter(dataset_id=dataset_id).count()
       for offset in range(0, total, batch_size):
           batch = Item.objects.filter(dataset_id=dataset_id)[offset:offset + batch_size]
           process_batch(batch)
           self.update_state(state='PROGRESS', meta={'current': offset + batch_size, 'total': total})
   ```
4. Use separate queues and workers for CPU-intensive tasks.

---

## Scalability Guidelines

1. Scale workers horizontally by adding more Celery processes/containers.
2. Use `--concurrency` flag to control worker parallelism.
3. Use priority queues for urgent tasks (notifications) vs background tasks (cleanup).
4. Use Redis Sentinel or Cluster for broker high availability.
5. Monitor queue depths — alert when backlog exceeds threshold.

---

## Refusal Conditions

REFUSE to generate code that:
1. Passes model instances as task arguments.
2. Uses pickle serialization.
3. Dispatches tasks inside `transaction.atomic()`.
4. Creates tasks without time limits.
5. Retries indefinitely without max_retries.
6. Silently ignores task failures.
7. Stores large payloads in task arguments.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| Celery vs Django-Q vs RQ | Celery for enterprise. Django-Q for simple projects only. |
| Redis vs RabbitMQ broker | Redis for simplicity and dual-use (cache + broker). RabbitMQ if advanced routing needed. |
| Sync task vs Async offload | Offload if operation takes >500ms or involves external I/O. |
| In-process vs Worker | Workers for reliability. In-process only for development/testing. |
| `acks_late` vs Early ack | `acks_late` for critical tasks. Early ack for fire-and-forget. |
