---
name: django_caching
description: Enterprise Django 6 caching — Redis strategies, cache invalidation, per-object and per-query caching, GraphQL response caching, and cache stampede prevention.
---

# Django Caching Skill

## Purpose

Define and enforce caching strategies for enterprise Django 6 systems using Redis, covering per-object caching, query result caching, GraphQL response caching, cache invalidation discipline, and cache stampede prevention.

## Scope

- Redis cache configuration
- Cache key naming conventions
- Per-object, per-query, and fragment caching
- Cache invalidation strategies
- Cache stampede prevention
- GraphQL caching patterns
- Session and rate-limit caching
- Cache monitoring and debugging

## Responsibilities

1. ENFORCE Redis as the primary cache backend.
2. ENFORCE consistent cache key naming conventions.
3. ENFORCE TTL (time-to-live) on all cached values.
4. ENFORCE cache invalidation on data mutation.
5. ENFORCE cache stampede prevention for hot keys.
6. PREVENT stale cache serving incorrect data.
7. PREVENT unbounded cache growth.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use Redis as the cache backend in production:
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': env('REDIS_CACHE_URL', default='redis://localhost:6379/2'),
           'OPTIONS': {
               'db': 2,
           },
           'KEY_PREFIX': 'cms',
           'TIMEOUT': 300,  # Default 5-minute TTL
       }
   }
   ```
2. ALWAYS use a consistent key naming convention: `{app}:{entity}:{identifier}:{variant}`:
   ```python
   # Examples
   "notifications:unread_count:user:42"
   "grades:semester_gpa:student:123:sem:5"
   "system:config:feature_flags"
   ```
3. ALWAYS set a TTL on every cached value. Never cache without expiry:
   ```python
   cache.set('notifications:unread_count:user:42', count, timeout=60)
   ```
4. ALWAYS invalidate cache on mutation — when data changes, delete the relevant cache keys:
   ```python
   def mark_as_read(notification_id, user):
       # ... update DB
       cache.delete(f'notifications:unread_count:user:{user.id}')
       cache.delete(f'notifications:list:user:{user.id}')
   ```
5. ALWAYS use cache versioning for cache key schema changes:
   ```python
   CACHE_VERSION = 'v2'
   key = f"cms:{CACHE_VERSION}:notifications:unread_count:user:{user_id}"
   ```
6. ALWAYS use `cache.get_or_set()` or the lock-based pattern for cache stampede prevention:
   ```python
   # Simple approach
   count = cache.get_or_set(
       f'notifications:unread_count:user:{user_id}',
       lambda: notification_service.get_unread_count(user),
       timeout=60
   )

   # Lock-based approach for expensive computations
   from django.core.cache import cache
   import hashlib

   def cached_expensive_query(user_id):
       key = f'reports:summary:user:{user_id}'
       lock_key = f'{key}:lock'
       result = cache.get(key)
       if result is not None:
           return result
       # Acquire lock to prevent stampede
       if cache.add(lock_key, '1', timeout=30):
           try:
               result = compute_expensive_summary(user_id)
               cache.set(key, result, timeout=300)
               return result
           finally:
               cache.delete(lock_key)
       else:
           # Another process is computing — wait and retry
           import time
           time.sleep(0.5)
           return cache.get(key) or compute_expensive_summary(user_id)
   ```
7. ALWAYS separate cache databases by purpose:
   - DB 0: Django sessions
   - DB 1: Celery broker
   - DB 2: Application cache
   - DB 3: Pub/Sub (notifications)
8. ALWAYS log cache hit/miss rates in monitoring:
   ```python
   result = cache.get(key)
   if result is not None:
       metrics.increment('cache.hit', tags=['key_type:unread_count'])
   else:
       metrics.increment('cache.miss', tags=['key_type:unread_count'])
   ```

### NEVER

1. NEVER cache without a TTL. Unbounded cache leads to stale data and memory exhaustion.
2. NEVER cache user-specific data with a generic key (missing user ID in key → data leakage).
3. NEVER cache mutable Python objects by reference. Redis serializes/deserializes — this is safe, but in-memory caches (LocMemCache) can cause mutations.
4. NEVER cache sensitive data (passwords, tokens, PII) unless encrypted.
5. NEVER use cache as the source of truth. Database is always the source of truth. Cache is an optimization layer.
6. NEVER assume cache is available. Handle `cache.get()` returning `None` gracefully — always have a fallback to database.
7. NEVER cache error responses or exceptions.
8. NEVER use wildcard `cache.delete_pattern()` in request hot paths — it scans all keys and blocks Redis.
9. NEVER cache across users without explicit key separation.

---

## Caching Strategies

### Per-Object Caching

Cache individual model instances or computed values:
```python
def get_student_gpa(student_id: int) -> float:
    key = f'grades:gpa:student:{student_id}'
    gpa = cache.get(key)
    if gpa is None:
        gpa = SemesterGPA.objects.filter(student_id=student_id).aggregate(
            avg=Avg('gpa')
        )['avg'] or 0.0
        cache.set(key, gpa, timeout=600)  # 10 minutes
    return gpa
```

### Per-Query Caching

Cache query results for specific parameter combinations:
```python
def get_notifications(user_id: int, category: str = None, limit: int = 20) -> list:
    key = f'notifications:list:user:{user_id}:cat:{category}:limit:{limit}'
    result = cache.get(key)
    if result is None:
        result = list(notification_service.get_user_notifications(...))
        cache.set(key, result, timeout=30)  # Short TTL for frequently changing data
    return result
```

### Fragment Caching

Cache expensive sub-computations within a larger operation:
```python
def get_dashboard_data(user_id: int) -> dict:
    # Fragment 1: Unread count (cached 60s)
    unread = cache.get_or_set(
        f'notifications:unread_count:user:{user_id}',
        lambda: Notification.objects.filter(recipient_id=user_id, is_read=False).count(),
        timeout=60
    )
    # Fragment 2: GPA (cached 10 min)
    gpa = cache.get_or_set(
        f'grades:gpa:student:{user_id}',
        lambda: compute_gpa(user_id),
        timeout=600
    )
    return {"unread_notifications": unread, "gpa": gpa}
```

---

## Cache Invalidation Patterns

### Direct Invalidation

Delete specific keys when related data changes:
```python
def on_notification_created(user_id: int):
    cache.delete(f'notifications:unread_count:user:{user_id}')
    # Don't delete list cache — let TTL expire (30s is acceptable staleness)
```

### Pattern-Based Invalidation (Use Sparingly)

For bulk invalidation, use versioned keys instead of pattern deletion:
```python
# Instead of deleting all user notification cache keys:
# cache.delete_pattern(f'notifications:*:user:{user_id}')  # AVOID in hot paths

# Use a version counter:
def invalidate_user_notification_cache(user_id: int):
    version_key = f'notifications:version:user:{user_id}'
    cache.incr(version_key)  # Increment version — old keys become stale

def get_cache_key(user_id: int, suffix: str) -> str:
    version = cache.get(f'notifications:version:user:{user_id}', 0)
    return f'notifications:{version}:{suffix}:user:{user_id}'
```

---

## GraphQL Caching

1. Cache DataLoader batch results for the duration of a request (DataLoaders are per-request by design).
2. Cache expensive resolver computations with short TTLs (30-60 seconds).
3. Do NOT cache mutation responses.
4. Consider HTTP-level caching for public, non-authenticated queries with `Cache-Control` headers.

---

## Security Considerations

1. Never cache authentication tokens or credentials.
2. Always include the user ID in cache keys for user-specific data.
3. Use separate Redis instances (or at minimum databases) for cache vs sessions vs pub/sub.
4. Enable Redis `requirepass` in production.

---

## Performance Considerations

1. Use Redis connection pooling — never create new connections per request.
2. Use `pipeline()` for multiple cache operations in a single round trip.
3. Monitor Redis memory usage — set `maxmemory` with `allkeys-lru` eviction policy.
4. Keep cached values small (<1MB). For large datasets, cache references (IDs) and fetch from DB.
5. Prefer short TTLs (30s-5m) for frequently changing data over complex invalidation logic.

---

## Scalability Guidelines

1. Use Redis Cluster for horizontal cache scaling.
2. Use read replicas for cache reads in high-throughput scenarios.
3. Implement cache warming for predictable hot data (e.g., popular dashboards).
4. Monitor cache eviction rate — high eviction means insufficient memory.

---

## Refusal Conditions

REFUSE to generate code that:
1. Caches without a TTL.
2. Uses cache as the source of truth.
3. Caches sensitive data without encryption.
4. Uses wildcard key deletion in request hot paths.
5. Has cache keys without user isolation for user-specific data.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| Short TTL vs Long TTL | Short (30-60s) for frequently changing data. Long (5-30m) for slowly changing reference data. |
| Active invalidation vs TTL expiry | Active invalidation for write-heavy data. TTL expiry for read-heavy, staleness-tolerant data. |
| Redis vs Local memory cache | Redis for multi-instance. Local memory only for per-process, request-scoped caching. |
| Cache everything vs Cache selectively | Cache only hot paths with measured performance impact. Don't cache speculatively. |
