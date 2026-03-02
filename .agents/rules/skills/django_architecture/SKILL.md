---
name: django_architecture
description: Enterprise Django 6 architecture patterns — modular monolith, async-first design, service layer, app boundaries, and horizontal scalability.
---

# Django Architecture Skill

## Purpose

Define and enforce the architectural patterns, constraints, and conventions for building enterprise-grade Django 6 systems using a modular monolith architecture with ASGI-first design, Strawberry GraphQL, and Server-Sent Events.

## Scope

- Project structure and app organization
- Layered architecture enforcement (models → services → resolvers/views)
- Async vs sync decision boundaries
- Inter-app communication contracts
- Configuration and environment management
- Dependency injection patterns
- Middleware architecture
- ASGI application lifecycle

## Responsibilities

1. ENFORCE modular monolith app boundaries.
2. ENFORCE the service layer pattern for all business logic.
3. ENFORCE async-first design for I/O-bound operations.
4. ENFORCE environment-based configuration with no hardcoded secrets.
5. ENFORCE strict separation of concerns across layers.
6. PREVENT circular imports between apps.
7. PREVENT business logic in models, views, resolvers, or serializers.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use ASGI (`asgi.py`) as the primary application interface. WSGI is for legacy compatibility only.
2. ALWAYS organize code into the following layers per app:
   ```
   <app_name>/
   ├── __init__.py
   ├── apps.py
   ├── models.py              # Data layer — ORM models only
   ├── services/              # Business logic layer
   │   ├── __init__.py
   │   └── <domain>_service.py
   ├── graphql/               # API layer — Strawberry types, queries, mutations
   │   ├── __init__.py
   │   ├── types.py
   │   ├── queries.py
   │   ├── mutations.py
   │   ├── permissions.py
   │   └── dataloaders.py
   ├── signals.py             # Signal definitions
   ├── receivers.py           # Signal receivers
   ├── constants.py           # Enums, choices, mappings
   ├── admin.py               # Admin configuration
   ├── migrations/
   └── tests/
       ├── __init__.py
       ├── test_services.py
       ├── test_queries.py
       ├── test_mutations.py
       └── test_models.py
   ```
3. ALWAYS place business logic in the `services/` layer. Models define schema. Resolvers call services. Services call models.
4. ALWAYS use `django.conf.settings` for configuration. Never import from `.env` directly in app code.
5. ALWAYS define app boundaries explicitly. Each Django app represents a bounded context.
6. ALWAYS use `AppConfig.ready()` for signal registration. Import receivers in `apps.py`.
7. ALWAYS use `timezone.now()` — never `datetime.now()` or `datetime.utcnow()`.
8. ALWAYS store datetimes in UTC. Convert to local timezone only at the presentation layer.
9. ALWAYS use type hints on all function signatures.
10. ALWAYS define `__all__` exports in `__init__.py` files for public APIs.
11. ALWAYS use absolute imports. Never use relative imports across app boundaries.
12. ALWAYS define constants and enums in `constants.py`, never inline.

### NEVER

1. NEVER put business logic in models. Models define fields, Meta, `__str__`, `clean()`, and `save()` overrides only.
2. NEVER put business logic in GraphQL resolvers or REST views. They orchestrate; services execute.
3. NEVER import from one app's `models.py` into another app's `models.py` directly. Use string references for ForeignKey: `ForeignKey('other_app.ModelName', ...)`.
4. NEVER use `from django.contrib.auth.models import User` directly. Always use `get_user_model()` or `settings.AUTH_USER_MODEL`.
5. NEVER hardcode environment-specific values (URLs, credentials, feature flags).
6. NEVER use `print()` for debugging. Use the `logging` module exclusively.
7. NEVER use `*` imports anywhere.
8. NEVER use mutable default arguments in function signatures. Use `None` with internal defaults.
9. NEVER call `time.sleep()` in async code paths. Use `asyncio.sleep()`.
10. NEVER access `request.user` inside a service function. Pass the user as a parameter.

---

## Architectural Constraints

### Layered Architecture

```
┌─────────────────────────────────────────┐
│  GraphQL Resolvers / REST Views         │  ← Thin layer: auth, input parsing, response formatting
├─────────────────────────────────────────┤
│  Service Layer                          │  ← All business logic lives here
├─────────────────────────────────────────┤
│  Model Layer (ORM)                      │  ← Data access, schema, constraints
├─────────────────────────────────────────┤
│  Database                               │
└─────────────────────────────────────────┘
```

### Inter-App Communication

- Apps communicate through **service-layer function calls** or **Django signals**.
- Apps MUST NOT directly query another app's models unless via a service function exported from that app.
- Cross-app dependencies must flow in one direction. Define an explicit dependency graph. Circular dependencies are a build-break.
- Shared kernel code (utilities, base classes, common types) lives in a `core/` app.

### Async vs Sync Decision Matrix

| Operation | Use Async | Use Sync |
|---|---|---|
| GraphQL resolvers with DB queries | ✅ `async def` + `sync_to_async` | Only if wrapping legacy sync code |
| SSE streaming views | ✅ Always async | ❌ Never |
| Celery tasks | ❌ Never | ✅ Always |
| Django signals | ❌ Never | ✅ Always |
| Management commands | Context-dependent | Default |
| Middleware | ✅ Prefer async | Acceptable for simple cases |
| ORM queries | Via `sync_to_async` | Direct in sync contexts |

### Transaction Discipline

1. Use `transaction.atomic()` for any operation that modifies multiple related rows.
2. NEVER nest `transaction.atomic()` unless using savepoints intentionally.
3. NEVER perform external I/O (HTTP calls, Redis pub/sub, SSE broadcast) inside a `transaction.atomic()` block. Defer side-effects to `transaction.on_commit()`.
4. In async code, wrap transactional operations using `sync_to_async(create_in_transaction)`.

```python
# CORRECT
from django.db import transaction

def create_order_with_items(user, items_data):
    with transaction.atomic():
        order = Order.objects.create(user=user)
        OrderItem.objects.bulk_create([
            OrderItem(order=order, **item) for item in items_data
        ])
    # Side-effects AFTER transaction commits
    transaction.on_commit(lambda: broadcast_order_created(order.id))
    return order
```

---

## Security Considerations

1. All configuration secrets MUST come from environment variables loaded via `django-environ` or `python-decouple`.
2. `DEBUG` MUST be `False` in production. Enforce via environment variable.
3. `ALLOWED_HOSTS` MUST be explicitly set — never `['*']` in production.
4. `SECRET_KEY` MUST be a cryptographically random string, unique per environment.
5. Enforce `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` in production settings.
6. Use separate settings modules or environment-based branching — never a single `settings.py` for all environments.

---

## Performance Considerations

1. Use `select_related()` and `prefetch_related()` to eliminate N+1 queries. Verify with `django-debug-toolbar` or query logging.
2. Use `bulk_create()`, `bulk_update()` for batch operations. Never loop `.create()` or `.save()`.
3. Use `only()` and `defer()` to limit field selection when appropriate.
4. Use database-level constraints (`unique_together`, `CheckConstraint`, indexes) rather than application-level validation for data integrity.
5. Offload CPU-intensive or long-running work to Celery tasks.
6. Connection pooling via `django-db-connection-pool` or PgBouncer is mandatory for production.

---

## Scalability Guidelines

1. Design every app to be independently deployable as a service in the future (modular monolith → microservices migration path).
2. Use Redis for caching, session storage, and pub/sub. Never rely on local process memory for shared state.
3. Use database read replicas for read-heavy queries where appropriate.
4. Design Celery tasks to be idempotent — safe to retry.
5. Use `CONN_MAX_AGE` appropriately (non-zero for persistent connections behind a connection pooler).
6. Avoid storing large blobs in the database. Use object storage (S3/MinIO) with URL references.

---

## Code Output Format Requirements

1. All Python files MUST pass `ruff check` with no errors.
2. All Python files MUST be formatted with `ruff format`.
3. All functions MUST have docstrings following Google-style format.
4. All modules MUST have a module-level docstring.
5. Import order: stdlib → third-party → Django → local apps (enforced by `isort`).

---

## Clarification Protocol

Before writing architectural code, ask:

1. Which app/bounded context does this belong to?
2. Does this operation require a database transaction?
3. Is this I/O-bound (use async) or CPU-bound (use Celery)?
4. Does this create a cross-app dependency? If so, which direction?
5. Are there side-effects that must happen after commit?

---

## Refusal Conditions

REFUSE to generate code that:

1. Places business logic in models, views, resolvers, serializers, or middleware.
2. Uses `datetime.now()` or naive datetimes.
3. Hardcodes secrets, URLs, or environment-specific values.
4. Creates circular imports between apps.
5. Uses synchronous blocking calls inside async code paths.
6. Performs external I/O inside `transaction.atomic()`.
7. Uses `*` imports.
8. Skips type hints on function signatures.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| Async vs Sync | Default to async for I/O-bound. Use sync for Celery, signals, and ORM-heavy code wrapped with `sync_to_async`. |
| Monolith vs Microservices | Start monolith. Design app boundaries for future extraction. |
| Fat models vs Service layer | Always service layer. Models are data containers only. |
| Signals vs Direct calls | Use signals for decoupled side-effects. Use direct service calls for core business logic flow. |
| Single settings file vs Split | Split by environment (`base.py`, `development.py`, `production.py`) or use env-var branching in a single file. |
| REST vs GraphQL | GraphQL-first. REST only for webhooks, file uploads, SSE, and third-party integrations that require it. |

---

## Anti-Patterns

1. **God App** — An app that does everything. Break into bounded contexts.
2. **Anemic Service Layer** — Services that just proxy model calls without adding value. Services should contain business rules.
3. **Smart Templates/Resolvers** — Business logic in Jinja templates or GraphQL resolvers.
4. **Shared Mutable State** — Using module-level mutable variables for cross-request state.
5. **Implicit Dependencies** — Importing from another app without declaring the dependency.
6. **Migration Drift** — Running `makemigrations` with `--merge` without reviewing the conflict.
