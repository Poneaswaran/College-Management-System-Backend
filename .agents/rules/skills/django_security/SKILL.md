---
name: django_security
description: Enterprise Django 6 security — authentication, authorization, CSRF/CORS, input sanitization, GraphQL introspection protection, secret management, and audit logging.
---

# Django Security Skill

## Purpose

Define and enforce comprehensive security standards for enterprise Django 6 systems with Strawberry GraphQL and SSE, covering authentication, authorization, data protection, input validation, and audit logging.

## Scope

- Authentication mechanisms (JWT, session, signed tokens)
- Authorization and permission enforcement
- CSRF and CORS configuration
- Input sanitization and validation
- GraphQL-specific security (introspection, depth, complexity)
- Secret management
- Audit logging
- Mass assignment prevention
- Security headers

## Responsibilities

1. ENFORCE authentication on all endpoints.
2. ENFORCE field-level and resource-level authorization.
3. ENFORCE CSRF protection for session-based auth and proper CORS for token-based auth.
4. ENFORCE input sanitization on all user-provided data.
5. ENFORCE secret management via environment variables.
6. ENFORCE audit logging for security-sensitive operations.
7. PREVENT mass assignment vulnerabilities.
8. PREVENT information leakage via error messages or introspection.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use `settings.AUTH_USER_MODEL` or `get_user_model()` for user references. Never import the User model directly.
2. ALWAYS hash passwords using Django's built-in `make_password()` or the auth system. Never store plaintext passwords.
3. ALWAYS use HTTPS in production. Set `SECURE_SSL_REDIRECT = True`.
4. ALWAYS set security headers in production:
   ```python
   SECURE_HSTS_SECONDS = 31536000
   SECURE_HSTS_INCLUDE_SUBDOMAINS = True
   SECURE_HSTS_PRELOAD = True
   SECURE_CONTENT_TYPE_NOSNIFF = True
   X_FRAME_OPTIONS = 'DENY'
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   SESSION_COOKIE_HTTPONLY = True
   CSRF_COOKIE_HTTPONLY = True
   ```
5. ALWAYS validate and sanitize all user inputs before storage:
   - Strip leading/trailing whitespace.
   - Validate email format, URL format, phone format using Django's validators.
   - Sanitize HTML content using `bleach.clean()` if HTML input is accepted.
   - Enforce maximum length limits on all string inputs.
6. ALWAYS use parameterized queries for raw SQL. Never string-interpolate user input into SQL.
7. ALWAYS implement rate limiting on authentication endpoints (login, token refresh, password reset).
8. ALWAYS log authentication events (login success, login failure, password change, token refresh) with user identifier and IP address.
9. ALWAYS use `permission_classes` on every GraphQL query and mutation resolver.
10. ALWAYS implement resource-level authorization — verify the user owns or has access to the specific resource being requested.
    ```python
    # CORRECT — verify ownership
    notification = Notification.objects.get(id=notification_id, recipient=user)
    # WRONG — fetch any notification by ID
    notification = Notification.objects.get(id=notification_id)
    ```
11. ALWAYS use `SECRET_KEY` from environment variable. Never commit to version control.
12. ALWAYS rotate `SECRET_KEY` periodically and maintain `SECRET_KEY_FALLBACKS` for session continuity.
13. ALWAYS set `ALLOWED_HOSTS` explicitly. Never use `['*']` in production.
14. ALWAYS set `DEBUG = False` in production. Enforce via environment variable with no fallback to `True`.
15. ALWAYS use `django.contrib.auth.password_validation` validators.

### NEVER

1. NEVER expose stack traces, database errors, or internal paths in API responses.
2. NEVER log passwords, tokens, API keys, or other secrets. Log metadata only.
3. NEVER store secrets in code, settings files, or version control. Use environment variables exclusively.
4. NEVER allow GraphQL introspection in production.
5. NEVER trust client-provided data without validation — including IDs, roles, permissions, or user types.
6. NEVER use `eval()`, `exec()`, or `__import__()` with user-provided input.
7. NEVER disable CSRF protection globally. Exempt only specific views with explicit justification.
8. NEVER use `GET` requests for state-changing operations.
9. NEVER return different error messages for "user not found" vs "wrong password" — this leaks user enumeration information. Use generic messages.
10. NEVER store session data or tokens in `localStorage` (XSS vulnerable). Use `httpOnly` cookies when possible.
11. NEVER send long-lived tokens in URL query parameters. URLs are logged everywhere.
12. NEVER allow mass assignment — always use explicit field lists in serializers and input types.

---

## CSRF Handling Rules

1. For session-based auth (browsers): CSRF protection is mandatory. Django's `CsrfViewMiddleware` must be active.
2. For token-based auth (JWT, API keys): CSRF is not applicable. The GraphQL endpoint using token auth may be `@csrf_exempt`, but only if it exclusively uses token authentication.
3. For SSE endpoints: Use signed tokens, not session cookies. CSRF is not a concern for SSE with token auth.
4. NEVER globally disable CSRF. Apply `@csrf_exempt` only to views that exclusively use non-cookie authentication.

```python
# GraphQL view with JWT auth — CSRF exempt is acceptable
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
async def graphql_view(request):
    # Only accepts JWT Bearer tokens, never session cookies
    ...
```

---

## CORS Configuration Rules

1. NEVER use `CORS_ALLOW_ALL_ORIGINS = True` in production.
2. Explicitly list allowed origins:
   ```python
   CORS_ALLOWED_ORIGINS = [
       "https://app.example.com",
       "https://admin.example.com",
   ]
   ```
3. For development: allow `localhost` origins only via environment variable.
4. For SSE endpoints: set CORS headers in middleware or the view to allow `EventSource` connections from the frontend origin.
5. Set `CORS_ALLOW_CREDENTIALS = True` only if using cookie-based auth with cross-origin requests.

---

## GraphQL Security

1. **Introspection**: Disable in production using `DisableIntrospection` extension.
2. **Query Depth**: Limit to 10 using `QueryDepthLimiter`.
3. **Query Complexity**: Implement complexity analysis to prevent expensive queries.
4. **Batching**: Limit batched queries to 10 per request to prevent abuse.
5. **Body Size**: Limit GraphQL request body size (e.g., 100KB) at the web server level.
6. **Persisted Queries**: Consider requiring persisted queries in production to prevent arbitrary query execution.
7. **Field Authorization**: Implement field-level permission checks for sensitive fields (salary, SSN, email, phone):
   ```python
   @strawberry.field
   def email(self, info: Info) -> str | None:
       request = info.context["request"]
       if request.user == self._user or request.user.is_staff:
           return self._user.email
       return None
   ```

---

## Mass Assignment Prevention

1. NEVER use `Model.objects.create(**request.data)` or `Model(**kwargs)` with unvalidated input.
2. ALWAYS define explicit `@strawberry.input` types listing only the fields that the user is allowed to set.
3. ALWAYS validate that the user is not setting fields they shouldn't (e.g., `is_admin`, `role`, `created_by`):
   ```python
   # WRONG — mass assignment vulnerability
   user = User.objects.create(**input_data)

   # CORRECT — explicit field assignment
   user = User.objects.create(
       email=input_data.email,
       first_name=input_data.first_name,
       last_name=input_data.last_name,
       # role is NOT settable by user
   )
   ```

---

## Audit Logging

1. Log all authentication events: login, logout, failed attempts, token refresh, password change.
2. Log all authorization failures: permission denied responses.
3. Log all mutations that modify sensitive data: user creation, role changes, grade updates, permission changes.
4. Log format must include: timestamp (UTC), user_id, action, resource_type, resource_id, IP address, user_agent.
5. Use structured logging (JSON format) for audit logs to enable machine parsing.
6. Store audit logs in a separate, append-only location. Never allow application code to delete audit log entries.

```python
import logging
audit_logger = logging.getLogger('audit')

audit_logger.info(
    "Mutation executed",
    extra={
        "user_id": user.id,
        "action": "MARK_NOTIFICATION_READ",
        "resource_type": "Notification",
        "resource_id": notification_id,
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get('HTTP_USER_AGENT', ''),
    }
)
```

---

## Secret Management

1. All secrets MUST be loaded from environment variables.
2. Use `django-environ` or `python-decouple` for `.env` file support in development.
3. In production, inject secrets via the deployment platform's secret management (e.g., AWS Secrets Manager, Vault, Kubernetes Secrets).
4. Required environment variables must be validated at startup — fail fast if missing:
   ```python
   SECRET_KEY = env('SECRET_KEY')  # Raises ImproperlyConfigured if missing
   ```
5. Never use default values for security-sensitive settings:
   ```python
   # WRONG
   SECRET_KEY = env('SECRET_KEY', default='some-fallback')
   # CORRECT
   SECRET_KEY = env('SECRET_KEY')  # No default — must be set
   ```

---

## Security Considerations

1. Implement account lockout after N failed login attempts.
2. Use bcrypt or Argon2 for password hashing (`PASSWORD_HASHERS` configuration).
3. Implement password complexity requirements via `AUTH_PASSWORD_VALIDATORS`.
4. Set session expiry: `SESSION_COOKIE_AGE = 3600` (1 hour) for sensitive applications.
5. Implement TOTP/MFA for admin and privileged users.
6. Use `Content-Security-Policy` headers to prevent XSS.
7. Validate file uploads: check MIME type, file extension, and scan for malware.

---

## Performance Considerations

1. Cache permission checks for the duration of a request — don't re-query user roles on every resolver.
2. Use `select_related('user')` when checking permissions that require user profile data.
3. Rate limiting should use Redis-backed counters for consistency across instances.

---

## Scalability Guidelines

1. Use stateless JWT authentication for horizontal scaling. Session-based auth requires shared session store (Redis).
2. Rate limiting state must be stored in Redis, not in process memory.
3. Audit logs should be asynchronously written (via Celery task or async logging handler) to avoid blocking request processing.

---

## Refusal Conditions

REFUSE to generate code that:
1. Hardcodes secrets, API keys, or credentials.
2. Disables CSRF globally without justification.
3. Allows introspection in production.
4. Uses unsanitized user input in queries.
5. Returns internal error details to clients.
6. Logs sensitive data (passwords, tokens, PII).
7. Uses `eval()` or `exec()` with user input.
8. Allows mass assignment from unvalidated input.
9. Skips permission checks on resolvers.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| JWT vs Session auth | JWT for API/GraphQL (stateless). Session for admin panel (CSRF-protected). |
| httpOnly cookie vs Authorization header | httpOnly cookie for browser apps (XSS-safe). Authorization header for mobile/API clients. |
| Rate limiting precision vs Performance | Token bucket with Redis for per-user precision. IP-based at reverse proxy for DDoS protection. |
| Strict CORS vs Flexible CORS | Strict allowlist in production. Flexible localhost in development only. |
| Audit log sync vs async | Async (Celery) for non-blocking writes. Sync only for critical security events. |
