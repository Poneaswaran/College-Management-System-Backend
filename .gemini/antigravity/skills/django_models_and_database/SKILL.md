---
name: django_models_and_database
description: Enterprise Django 6 model design — schema discipline, migration safety, indexing strategy, query optimization, and PostgreSQL best practices.
---

# Django Models and Database Skill

## Purpose

Define and enforce strict standards for Django ORM model design, database schema evolution, query performance, migration safety, and PostgreSQL-specific best practices in an enterprise Django 6 system.

## Scope

- Model field design and constraints
- Migration creation, review, and deployment
- Query optimization and indexing
- PostgreSQL-specific features
- Database transaction discipline
- Data integrity enforcement
- Connection pooling and performance

## Responsibilities

1. ENFORCE correct field types, constraints, and indexes on all models.
2. ENFORCE migration safety — every migration must be reviewable and reversible.
3. ENFORCE query performance standards — no unbounded queries, no N+1 patterns.
4. ENFORCE timezone-aware datetime usage across all models.
5. ENFORCE PostgreSQL best practices for JSON fields, indexes, and constraints.
6. PREVENT schema drift, data loss migrations, and unreviewed schema changes.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use `BigAutoField` or `UUIDField` for primary keys. Never use default `AutoField` (32-bit integer) for new models.
   ```python
   # In settings.py
   DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
   ```
2. ALWAYS define `Meta.ordering` explicitly if default ordering is needed. Never rely on implicit ordering.
3. ALWAYS define `Meta.indexes` for columns used in `WHERE`, `ORDER BY`, `JOIN`, or `GROUP BY` clauses.
4. ALWAYS define `Meta.constraints` for business rules that the database should enforce.
   ```python
   class Meta:
       constraints = [
           models.UniqueConstraint(fields=['student', 'semester', 'subject'], name='unique_student_semester_subject'),
           models.CheckConstraint(check=models.Q(marks__gte=0), name='non_negative_marks'),
       ]
   ```
5. ALWAYS use `models.TextChoices` or `models.IntegerChoices` for choice fields. Never use raw tuples.
6. ALWAYS use `DateTimeField(auto_now_add=True)` for creation timestamps and `DateTimeField(auto_now=True)` for update timestamps.
7. ALWAYS use `on_delete=models.CASCADE` only when child records must be deleted with parent. Use `SET_NULL`, `PROTECT`, or `RESTRICT` when cascading deletion is semantically wrong.
8. ALWAYS define `related_name` on all `ForeignKey` and `OneToOneField` fields. Never rely on Django's default `<model>_set`.
9. ALWAYS use `select_related()` for ForeignKey/OneToOne traversals and `prefetch_related()` for reverse ForeignKey/ManyToMany.
10. ALWAYS define `__str__()` on every model returning a human-readable representation.
11. ALWAYS define `verbose_name` and `verbose_name_plural` in `Meta`.
12. ALWAYS use `bulk_create()` and `bulk_update()` for batch operations. Never loop `.save()`.
13. ALWAYS use `update_fields` parameter in `.save()` when updating specific fields to avoid full-row writes and race conditions.
   ```python
   instance.status = 'ACTIVE'
   instance.save(update_fields=['status', 'updated_at'])
   ```
14. ALWAYS run `EXPLAIN ANALYZE` on queries touching tables with >10K rows before deploying.
15. ALWAYS create indexes concurrently in production using `AddIndexConcurrently` from `django.contrib.postgres.operations`.

### NEVER

1. NEVER use `null=True` on `CharField` or `TextField`. Use `blank=True, default=""` instead. `null` on string fields creates two possible "empty" values (`NULL` and `""`).
2. NEVER use `FloatField` for monetary or precision-critical values. Use `DecimalField`.
3. NEVER use `GenericForeignKey` / `ContentType` framework unless absolutely necessary. It defeats type safety and queryability.
4. NEVER perform raw SQL without parameterized queries. SQL injection is a build-break.
   ```python
   # CORRECT
   Model.objects.raw('SELECT * FROM app_model WHERE id = %s', [user_id])
   # WRONG — SQL injection vulnerability
   Model.objects.raw(f'SELECT * FROM app_model WHERE id = {user_id}')
   ```
5. NEVER use `.all()` without `.limit()`, pagination, or aggregation in production code paths. Unbounded querysets are forbidden.
6. NEVER add `db_index=True` on fields that are already part of `unique=True`, `unique_together`, or a composite index — it creates redundant indexes.
7. NEVER use `auto_now=True` or `auto_now_add=True` on fields that need manual updates. These fields are not settable via ORM.
8. NEVER use `ManyToManyField` with `through` model and also define `through_fields` incorrectly.
9. NEVER create migrations that contain both schema changes AND data migrations. Separate them.
10. NEVER delete or squash migrations in production without coordinating with all deployment environments.

---

## Migration Discipline

### Creation Rules

1. Run `makemigrations` for ONE app at a time. Never run `makemigrations` without specifying the app name.
   ```bash
   python manage.py makemigrations <app_name>
   ```
2. Name migrations descriptively using `--name`:
   ```bash
   python manage.py makemigrations attendance --name add_session_status_index
   ```
3. Review every generated migration file before committing. Check for:
   - Destructive operations (`RemoveField`, `DeleteModel`, `AlterField` that narrows type)
   - Missing `reverse_code` in `RunPython` operations
   - Lock-heavy operations on large tables (`AddField` with default on tables >1M rows)

### Safety Rules

1. NEVER use `RunPython` without a `reverse_code` function. Every data migration must be reversible.
   ```python
   operations = [
       migrations.RunPython(forward_func, reverse_func),
   ]
   ```
2. For large tables, add columns as `NULL` first, backfill data, then add `NOT NULL` constraint — never add `NOT NULL` column with default to large tables in one step.
3. Renaming a column or table requires a multi-step migration strategy:
   - Step 1: Add new column/table
   - Step 2: Backfill data
   - Step 3: Update code to use new column/table
   - Step 4: Remove old column/table
4. NEVER auto-merge conflicting migrations. Review the dependency graph manually.
5. Test migrations against a production-size database copy before deploying.

### Index Migration Rules

1. Use `AddIndexConcurrently` for production PostgreSQL databases to avoid table locks.
   ```python
   from django.contrib.postgres.operations import AddIndexConcurrently

   class Migration(migrations.Migration):
       atomic = False  # Required for concurrent index creation
       operations = [
           AddIndexConcurrently(
               model_name='notification',
               index=models.Index(fields=['recipient', '-created_at'], name='idx_notif_recipient_created'),
           ),
       ]
   ```
2. Index naming convention: `idx_<table_short>_<column1>_<column2>`.

---

## Query Optimization Rules

### Indexing Strategy

1. ALWAYS index: foreign keys, columns in `WHERE` filters, columns in `ORDER BY`, columns in `JOIN` conditions.
2. Use composite indexes for queries that filter on multiple columns together.
3. Use partial indexes for queries that filter on a subset of rows:
   ```python
   models.Index(
       fields=['recipient', '-created_at'],
       condition=models.Q(is_read=False),
       name='idx_notif_unread',
   )
   ```
4. Use `GIN` indexes for `JSONField` and `ArrayField` queries:
   ```python
   from django.contrib.postgres.indexes import GinIndex
   indexes = [GinIndex(fields=['metadata'], name='idx_notif_metadata_gin')]
   ```

### Query Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| `Model.objects.all()` in a loop | Use `prefetch_related()` or `Subquery` |
| `for obj in qs: obj.related.name` | Use `select_related('related')` |
| `.count()` followed by `.filter().count()` | Use `annotate()` with `Count` and `Case/When` |
| `.filter(...).first()` without index | Add index on filter columns |
| `len(qs)` | Use `qs.count()` — `len()` loads all rows into memory |
| `.values_list(flat=True)` then Python filtering | Move filtering to the database query |

### EXPLAIN Plan Requirement

For any query on a table with >10,000 rows, run:
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) <your_query>;
```
Verify:
- No `Seq Scan` on large tables (should use Index Scan or Index Only Scan).
- `actual time` is within acceptable bounds.
- No excessive `Buffers: shared hit` indicating over-reading.

---

## Model Design Patterns

### Timestamps Mixin
```python
class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

### Soft Delete Pattern
```python
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
```

---

## Transaction Discipline

1. Use `transaction.atomic()` for multi-row writes.
2. Use `select_for_update()` for optimistic/pessimistic locking when concurrent modification is possible.
3. Use `transaction.on_commit()` for side-effects (notifications, cache invalidation, SSE broadcast).
4. In async contexts, wrap transactional code with `sync_to_async`:
   ```python
   from asgiref.sync import sync_to_async
   result = await sync_to_async(create_order_transactional)(user, items)
   ```

---

## Security Considerations

1. Validate all user input at the model level using `clean()` and field validators.
2. Use `models.CheckConstraint` for database-level invariants.
3. Never expose internal IDs that reveal information about data volume or ordering unless necessary.
4. Use field-level `editable=False` for fields that should not be user-modifiable.
5. Sanitize any HTML content before storing — use `bleach` or equivalent.

---

## Performance Considerations

1. Use `iterator()` for large querysets to avoid loading all rows into memory.
2. Use `values()` or `values_list()` when you only need specific fields and don't need model instances.
3. Use `Subquery` and `OuterRef` for correlated subqueries instead of Python loops.
4. Use `exists()` instead of `count() > 0` for existence checks.
5. Use `F()` expressions for field-reference updates to avoid race conditions.
   ```python
   Notification.objects.filter(id=pk).update(view_count=F('view_count') + 1)
   ```

---

## Scalability Guidelines

1. Partition large tables by date or tenant if row count exceeds 50M.
2. Use read replicas for read-heavy query paths via database routers.
3. Archive old data to cold storage tables periodically.
4. Use `CONN_MAX_AGE` > 0 with PgBouncer for connection pooling.
5. Monitor slow queries via `pg_stat_statements` and set up alerts for queries >500ms.

---

## Code Output Format Requirements

1. Every model file must have a module-level docstring.
2. Every model must have a class-level docstring.
3. Every field must have `help_text` for non-obvious fields.
4. Every `Meta` class must define `ordering`, `verbose_name`, `verbose_name_plural`, and `indexes`.
5. Model files must not exceed 300 lines. Split into multiple files using a `models/` package if needed.

---

## Clarification Protocol

Before writing model code, ask:
1. What are the uniqueness constraints?
2. What cascade behavior should foreign keys have?
3. Are there soft-delete requirements?
4. What queries will run against this table? (drives index design)
5. What is the expected row count at scale?
6. Are there audit logging requirements?

---

## Refusal Conditions

REFUSE to generate code that:
1. Uses `null=True` on `CharField` or `TextField`.
2. Uses `FloatField` for money or precision values.
3. Creates unbounded querysets without pagination.
4. Has N+1 query patterns without `select_related`/`prefetch_related`.
5. Uses raw SQL without parameterization.
6. Creates non-reversible data migrations.
7. Adds non-concurrent indexes on large production tables.
8. Uses naive datetimes.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| UUID vs BigInt PK | BigAutoField for internal models (faster joins). UUID for externally-exposed IDs. |
| JSONField vs Relational | Relational for structured, queryable data. JSONField for metadata/config that varies per record. |
| Soft delete vs Hard delete | Soft delete for audit-sensitive data. Hard delete for ephemeral/transient data. |
| Denormalization vs Joins | Denormalize only when measured query performance requires it. Document the source of truth. |
| Single table vs Table inheritance | Prefer single table with type discriminator over multi-table inheritance. Use proxy models for behavior variation. |
