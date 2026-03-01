---
name: django_error_handling_and_logging
description: Enterprise Django 6 error handling and logging — structured logging, exception hierarchy, GraphQL error standardization, and observability.
---

# Django Error Handling and Logging Skill

## Purpose

Define and enforce error handling and logging standards for enterprise Django 6 systems, ensuring consistent error responses, structured logging, audit trails, and observability.

## Scope

- Exception hierarchy and custom exceptions
- Error handling in services, resolvers, and views
- GraphQL error standardization
- Structured logging configuration
- Audit logging
- Error monitoring and alerting
- Async error handling

## Responsibilities

1. ENFORCE structured, JSON-formatted logging in production.
2. ENFORCE custom exception hierarchy for domain errors.
3. ENFORCE standardized error responses in GraphQL.
4. ENFORCE audit logging for sensitive operations.
5. PREVENT stack trace leakage to clients.
6. PREVENT silent error swallowing.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use Python's `logging` module. Never use `print()`.
2. ALWAYS use structured JSON logging in production:
   ```python
   LOGGING = {
       'version': 1,
       'disable_existing_loggers': False,
       'formatters': {
           'json': {
               '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
               'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
           },
       },
       'handlers': {
           'console': {'class': 'logging.StreamHandler', 'formatter': 'json'},
       },
       'loggers': {
           'django': {'handlers': ['console'], 'level': 'WARNING'},
           'notifications': {'handlers': ['console'], 'level': 'INFO'},
           'audit': {'handlers': ['console'], 'level': 'INFO'},
       },
       'root': {'handlers': ['console'], 'level': 'INFO'},
   }
   ```
3. ALWAYS define a custom exception hierarchy for domain errors:
   ```python
   # core/exceptions.py
   class AppError(Exception):
       """Base exception for all application errors."""
       def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
           self.message = message
           self.code = code
           super().__init__(message)

   class NotFoundError(AppError):
       def __init__(self, resource: str, identifier):
           super().__init__(f"{resource} not found: {identifier}", code="NOT_FOUND")

   class PermissionDeniedError(AppError):
       def __init__(self, message: str = "Permission denied"):
           super().__init__(message, code="PERMISSION_DENIED")

   class ValidationError(AppError):
       def __init__(self, message: str, field: str = None):
           self.field = field
           super().__init__(message, code="VALIDATION_ERROR")

   class ConflictError(AppError):
       def __init__(self, message: str):
           super().__init__(message, code="CONFLICT")
   ```
4. ALWAYS catch specific exceptions. Never use bare `except:` or `except Exception:` without re-raising:
   ```python
   # CORRECT
   try:
       notification = Notification.objects.get(id=nid, recipient=user)
   except Notification.DoesNotExist:
       raise NotFoundError("Notification", nid)

   # WRONG
   try:
       ...
   except:
       pass
   ```
5. ALWAYS log exceptions with full traceback at ERROR level:
   ```python
   try:
       result = service.process(data)
   except AppError:
       raise  # Domain errors propagate normally
   except Exception:
       logger.exception("Unexpected error in process()")  # Logs full traceback
       raise AppError("An unexpected error occurred")
   ```
6. ALWAYS return standardized error responses from GraphQL resolvers:
   ```python
   @strawberry.mutation(permission_classes=[IsAuthenticated])
   def mark_read(self, info: Info, notification_id: int) -> NotificationType | None:
       try:
           notification = notification_service.mark_as_read(notification_id, info.context["request"].user)
           return NotificationType.from_model(notification)
       except NotFoundError:
           return None
       except PermissionDeniedError:
           return None
       except Exception:
           logger.exception(f"Error marking notification {notification_id} as read")
           return None
   ```
7. ALWAYS include contextual information in log messages:
   ```python
   logger.info("Notification created", extra={
       "notification_id": notification.id,
       "recipient_id": notification.recipient_id,
       "notification_type": notification.notification_type,
       "actor_id": actor.id if actor else None,
   })
   ```
8. ALWAYS use separate loggers for different concerns:
   ```python
   logger = logging.getLogger(__name__)        # Module-level logger
   audit_logger = logging.getLogger('audit')    # Audit events
   perf_logger = logging.getLogger('performance')  # Performance metrics
   ```
9. ALWAYS use `logger.exception()` (not `logger.error()`) when logging caught exceptions — it includes the traceback.
10. ALWAYS set appropriate log levels:
    - `DEBUG`: Detailed diagnostic info (dev only)
    - `INFO`: Routine operations (notification created, task started)
    - `WARNING`: Unexpected but recoverable situations (cache miss, retry)
    - `ERROR`: Failures requiring attention (DB error, external API failure)
    - `CRITICAL`: System-level failures (Redis down, DB connection lost)

### NEVER

1. NEVER use `print()` for logging or debugging.
2. NEVER use bare `except:` or `except Exception: pass`.
3. NEVER log sensitive data: passwords, tokens, API keys, full credit card numbers, SSNs.
4. NEVER expose internal stack traces, file paths, or SQL queries in API responses.
5. NEVER silently swallow exceptions without logging.
6. NEVER use string formatting in logger calls — use lazy formatting:
   ```python
   # CORRECT — lazy formatting, evaluated only if log level is active
   logger.info("User %s created notification %s", user_id, notification_id)
   # ALSO CORRECT — extra dict
   logger.info("Notification created", extra={"user_id": user_id, "notif_id": notification_id})
   # WRONG — always evaluated, even if log level is disabled
   logger.debug(f"Processing {expensive_computation()}")
   ```
7. NEVER log at ERROR level for expected business conditions (e.g., validation failures). Use WARNING or INFO.

---

## Error Handling Layers

```
┌─────────────────────────────┐
│ GraphQL Resolver            │  Catch AppError → return structured response
│                             │  Catch Exception → log, return generic error
├─────────────────────────────┤
│ Service Layer               │  Raise AppError subclasses for business errors
│                             │  Let unexpected exceptions propagate
├─────────────────────────────┤
│ Model Layer                 │  Raise Django ValidationError in clean()
│                             │  Raise IntegrityError on constraint violations
├─────────────────────────────┤
│ Database                    │  Raises OperationalError, IntegrityError
└─────────────────────────────┘
```

---

## Audit Logging

Log these events to the `audit` logger:
- Authentication: login, logout, failed login, password change
- Authorization: permission denied events
- Data mutations: create, update, delete of sensitive models
- Admin actions: role changes, user management
- Configuration changes: feature flags, settings updates

Format:
```python
audit_logger.info("action_performed", extra={
    "timestamp": timezone.now().isoformat(),
    "user_id": user.id,
    "action": "MARK_ALL_READ",
    "resource_type": "Notification",
    "resource_count": count,
    "ip_address": get_client_ip(request),
})
```

---

## Monitoring and Alerting

### Alert Conditions
- ERROR rate > 1% of requests in 5-minute window
- CRITICAL log emitted
- Unhandled exception in resolver
- Celery task failure rate > 5%
- SSE connection error rate > 10%
- Database connection pool exhaustion

### Monitoring Tools Integration
- Use Sentry for exception tracking and alerting.
- Use structured logs with ELK/Grafana Loki for log aggregation.
- Use Prometheus metrics for request latency and error rates.

---

## Async Error Handling

```python
async def sse_event_stream(user, connection_id):
    try:
        yield format_sse_event(event='connected', data={})
        async for message in pubsub.listen():
            yield format_sse_event(data=message)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for user %s", user.id)
    except Exception:
        logger.exception("SSE stream error for user %s", user.id)
        yield format_sse_event(event='error', data={"message": "Stream error"})
    finally:
        await cleanup_connection(user.id, connection_id)
```

---

## Security Considerations

1. Never expose internal error details to clients in production.
2. Log full error details server-side for debugging.
3. Use error codes (not messages) for client-side error handling.
4. Sanitize user input in error messages to prevent log injection.

---

## Refusal Conditions

REFUSE to generate code that:
1. Uses `print()` for logging.
2. Uses bare `except:` without re-raising.
3. Exposes stack traces to API clients.
4. Logs sensitive data.
5. Silently swallows exceptions.
6. Uses eager string formatting in logger calls for debug/info levels.

---

## Trade-off Handling

| Trade-off | Decision |
|---|---|
| Verbose vs Concise logging | Verbose in dev (DEBUG). Concise in prod (INFO+). |
| Log everything vs Log selectively | Log all mutations and errors. Skip high-volume reads at DEBUG level. |
| Inline error handling vs Middleware | Service errors in services. Global fallback in middleware. |
| Sentry vs Self-hosted | Sentry for simplicity. Self-hosted ELK for cost control at scale. |
