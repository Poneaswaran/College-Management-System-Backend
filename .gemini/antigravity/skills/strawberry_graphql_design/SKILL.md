---
name: strawberry_graphql_design
description: Enterprise Strawberry GraphQL API design — schema-first thinking, resolver patterns, DataLoader enforcement, permissions, error standardization, and query complexity control.
---

# Strawberry GraphQL Design Skill

## Purpose

Define and enforce strict standards for designing, implementing, and securing Strawberry GraphQL APIs in a Django 6 system. Ensure schema-first thinking, separation of concerns, N+1 prevention, and production-hardened query control.

## Scope

- Schema design and type definitions
- Query and mutation resolver patterns
- Input validation and error handling
- Permission and authorization enforcement
- DataLoader usage for N+1 prevention
- Query depth and complexity limiting
- Schema evolution and versioning
- Pagination patterns
- File upload handling
- GraphQL-over-HTTP conventions

## Responsibilities

1. ENFORCE schema-first design — define types before resolvers.
2. ENFORCE separation between schema types, resolvers, and services.
3. ENFORCE DataLoader usage for all relationship traversals.
4. ENFORCE explicit permission checks in every resolver.
5. ENFORCE standardized error responses.
6. ENFORCE query depth and complexity limits.
7. PREVENT N+1 queries in GraphQL resolution.
8. PREVENT exposed stack traces or internal errors.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS define Strawberry types in `graphql/types.py`, queries in `graphql/queries.py`, mutations in `graphql/mutations.py`, and permissions in `graphql/permissions.py`.
2. ALWAYS use `@strawberry.type` for output types and `@strawberry.input` for mutation inputs. Never accept raw dictionaries.
3. ALWAYS define a `from_model()` classmethod on Strawberry types for model-to-type conversion:
   ```python
   @strawberry.type
   class StudentType:
       id: int
       name: str

       @classmethod
       def from_model(cls, student: Student) -> "StudentType":
           return cls(id=student.id, name=student.get_full_name())
   ```
4. ALWAYS use `permission_classes=[IsAuthenticated]` (or stricter) on every query and mutation. No public resolvers unless explicitly justified and documented.
5. ALWAYS validate inputs in the service layer, not in resolvers. Resolvers only parse and delegate.
6. ALWAYS use `Info` context to access the request and DataLoaders:
   ```python
   @strawberry.field(permission_classes=[IsAuthenticated])
   async def my_data(self, info: Info) -> DataType:
       request = info.context["request"]
       user = request.user
       loader = info.context["dataloaders"]["data_loader"]
       return await loader.load(user.id)
   ```
7. ALWAYS use DataLoaders for any field that resolves a relationship (ForeignKey, reverse FK, M2M):
   ```python
   # In dataloaders.py
   from strawberry.dataloader import DataLoader

   async def load_students_by_section(keys: list[int]) -> list[list[Student]]:
       students = await sync_to_async(list)(
           Student.objects.filter(section_id__in=keys).order_by('section_id')
       )
       mapping = defaultdict(list)
       for s in students:
           mapping[s.section_id].append(s)
       return [mapping.get(key, []) for key in keys]

   student_loader = DataLoader(load_fn=load_students_by_section)
   ```
8. ALWAYS use cursor-based or offset/limit pagination. Never return unbounded lists.
   ```python
   @strawberry.field
   def students(self, info: Info, limit: int = 20, offset: int = 0) -> StudentConnection:
       ...
   ```
9. ALWAYS return structured errors, never raise unhandled exceptions from resolvers:
   ```python
   @strawberry.type
   class MutationResult:
       success: bool
       message: str
       errors: list[str] | None = None
   ```
10. ALWAYS set query depth limit and complexity limit on the schema:
    ```python
    from strawberry.extensions import QueryDepthLimiter
    from strawberry.extensions import MaxTokensLimiter

    schema = strawberry.Schema(
        query=Query,
        mutation=Mutation,
        extensions=[
            QueryDepthLimiter(max_depth=10),
        ],
    )
    ```
11. ALWAYS disable introspection in production:
    ```python
    from strawberry.extensions import DisableIntrospection

    if not settings.DEBUG:
        extensions.append(DisableIntrospection())
    ```
12. ALWAYS log GraphQL errors server-side with full context (query name, variables, user ID).
13. ALWAYS use `Optional` / `| None` for nullable fields. Never leave nullability implicit.
14. ALWAYS register DataLoaders per-request in the GraphQL context to ensure isolation:
    ```python
    async def get_context(request):
        return {
            "request": request,
            "dataloaders": {
                "student_loader": DataLoader(load_fn=load_students_by_section),
            }
        }
    ```

### NEVER

1. NEVER put business logic in resolvers. Resolvers extract context, call services, format results.
2. NEVER return raw Django model instances from resolvers. Always convert to Strawberry types.
3. NEVER perform ORM queries directly in resolvers. Use services or DataLoaders.
4. NEVER expose internal IDs, stack traces, or database error messages in GraphQL responses.
5. NEVER use `strawberry.auto` for fields that expose sensitive data. Explicitly list fields.
6. NEVER allow unbounded list queries. Always require pagination parameters.
7. NEVER skip permission checks. Every resolver must declare its permission classes.
8. NEVER use inline `lambda` for complex resolver logic. Extract to named functions.
9. NEVER return Python `dict` as a GraphQL type. Define explicit Strawberry types.
10. NEVER mutate and query in the same GraphQL operation without understanding execution order.

---

## Architectural Constraints

### Schema Organization

```
<app>/graphql/
├── __init__.py
├── types.py          # Strawberry @strawberry.type definitions
├── inputs.py         # Strawberry @strawberry.input definitions (mutation inputs)
├── queries.py        # @strawberry.type Query class with field resolvers
├── mutations.py      # @strawberry.type Mutation class with mutation resolvers
├── permissions.py    # Strawberry BasePermission subclasses
├── dataloaders.py    # DataLoader factory functions
└── enums.py          # Strawberry enum types
```

### Schema Composition

All app-level Query and Mutation types are composed into a root schema:
```python
# project/schema.py
import strawberry
from app1.graphql.queries import App1Query
from app1.graphql.mutations import App1Mutation

@strawberry.type
class Query(App1Query, App2Query):
    pass

@strawberry.type
class Mutation(App1Mutation, App2Mutation):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

### Resolver Flow

```
Client Request
    → GraphQL Engine (parse, validate, depth check)
    → Permission Check (IsAuthenticated, IsOwner, etc.)
    → Resolver Function (extract args, get context)
    → Service Layer (business logic, validation)
    → ORM / DataLoader (data access)
    → Strawberry Type (format response)
    → Client Response
```

---

## Input Validation

1. Validate field lengths, formats, and ranges in `@strawberry.input` types or in the service layer.
2. Use Strawberry's scalar types for email, URL, datetime where applicable.
3. For complex validation, raise `ValueError` in the service layer and catch in the resolver to return structured errors.
4. Sanitize all string inputs that will be stored or displayed to prevent XSS.

```python
@strawberry.input
class CreateAssignmentInput:
    title: str  # Max 255 chars — enforced in service
    description: str
    max_marks: int  # Must be > 0 — enforced in service
    due_date: datetime  # Must be in the future — enforced in service
```

---

## Error Standardization

All mutations MUST return a union type or a result type:

```python
@strawberry.type
class OperationSuccess:
    message: str

@strawberry.type
class OperationError:
    message: str
    code: str  # e.g., "NOT_FOUND", "PERMISSION_DENIED", "VALIDATION_ERROR"
    field: str | None = None  # Which input field caused the error

OperationResult = strawberry.union("OperationResult", [OperationSuccess, OperationError])
```

Standard error codes:
- `AUTHENTICATION_REQUIRED` — User not authenticated
- `PERMISSION_DENIED` — User lacks required permission
- `NOT_FOUND` — Resource does not exist
- `VALIDATION_ERROR` — Input validation failed
- `CONFLICT` — Resource state conflict (e.g., already exists)
- `RATE_LIMITED` — Too many requests
- `INTERNAL_ERROR` — Server error (never expose details)

---

## Permission Patterns

```python
class IsAuthenticated(strawberry.BasePermission):
    message = "Authentication required"
    def has_permission(self, source, info, **kwargs) -> bool:
        request = info.context.get("request")
        return request and hasattr(request, "user") and request.user.is_authenticated

class IsRole(strawberry.BasePermission):
    message = "Insufficient permissions"
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    def has_permission(self, source, info, **kwargs) -> bool:
        request = info.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'role', None) in self.allowed_roles

class IsOwner(strawberry.BasePermission):
    message = "Not authorized to access this resource"
    def has_permission(self, source, info, **kwargs) -> bool:
        # Implement resource-level ownership check
        ...
```

---

## Schema Evolution Rules

1. NEVER remove or rename a field in a single deployment. Use deprecation:
   ```python
   @strawberry.field(deprecation_reason="Use 'fullName' instead. Will be removed 2026-06-01.")
   def name(self) -> str:
       return self._model.get_full_name()
   ```
2. Add new fields as `Optional` with defaults to maintain backward compatibility.
3. For breaking changes, version the schema endpoint (`/graphql/v2/`) or use feature flags.
4. Document all deprecated fields with a removal target date.
5. Monitor deprecated field usage before removal.

---

## Security Considerations

1. Disable introspection in production.
2. Implement query depth limiting (max depth: 10).
3. Implement query complexity limiting.
4. Rate limit GraphQL endpoints (per-user, per-IP).
5. Validate and sanitize all inputs.
6. Use field-level authorization for sensitive data fields.
7. Never expose internal database IDs if they reveal business intelligence.
8. Log all mutation operations with user context for audit trails.
9. Implement CORS properly for the GraphQL endpoint.
10. Reject queries exceeding max allowed size (body size limit).

---

## Performance Considerations

1. Use DataLoaders for ALL relationship fields — no exceptions.
2. Use `select_related` and `prefetch_related` inside DataLoader batch functions.
3. Cache frequently accessed, rarely changing data (e.g., user roles, system config).
4. Use persisted queries for known client operations in production.
5. Monitor resolver execution time — alert on resolvers >200ms.
6. Use Apollo-style `@defer` and `@stream` directives if supported for large responses.

---

## Scalability Guidelines

1. Keep resolvers stateless — no instance variables or mutable shared state.
2. DataLoaders are per-request — create fresh instances in the context factory.
3. For subscriptions, use SSE (not WebSocket) as defined in the SSE skill. Do not use Strawberry subscriptions with Django.
4. Use CDN caching for public, non-authenticated queries if applicable.

---

## Code Output Format Requirements

1. All Strawberry types must have docstrings.
2. All resolvers must have docstrings with Args and Returns sections.
3. All input types must document field constraints in docstrings.
4. Permission classes must have a descriptive `message` attribute.

---

## Clarification Protocol

Before writing GraphQL code, ask:
1. Who is authorized to access this query/mutation?
2. What are the pagination requirements?
3. Are there any relationships that need DataLoaders?
4. Is this a read (query) or write (mutation) operation?
5. What error cases can the service layer produce?
6. Does this query need to be cached?

---

## Refusal Conditions

REFUSE to generate code that:
1. Puts business logic in resolvers.
2. Returns raw model instances from resolvers.
3. Skips permission checks.
4. Uses unbounded list queries without pagination.
5. Performs ORM queries directly in resolvers without DataLoaders.
6. Exposes stack traces or internal errors to clients.
7. Allows introspection in production.
8. Uses GraphQL subscriptions via WebSocket (use SSE endpoint instead).

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| Union types vs Result types | Use union types for mutations with distinct success/error shapes. Use result types for simple success/fail. |
| Relay-style pagination vs Offset | Use offset/limit for simplicity. Migrate to Relay cursors if query performance degrades at scale. |
| Single schema vs Federated | Single monolith schema. Federate only if deploying apps as separate services. |
| `strawberry.auto` vs Explicit fields | Explicit fields always. `auto` only for internal/admin tools. |
| Sync vs Async resolvers | Async by default. Use `sync_to_async` for ORM queries. |

---

## Anti-Patterns

1. **Fat Resolver** — Resolver with >15 lines of logic. Extract to service.
2. **N+1 Resolver** — Resolver that queries the DB per-item in a list. Use DataLoader.
3. **God Schema** — Single file with all types and resolvers. Split per app.
4. **Implicit Nullability** — Fields without explicit `Optional` annotation that return `None`.
5. **Generic Error Strings** — Returning `"Something went wrong"` without error codes.
6. **Input Bag** — Using `strawberry.scalars.JSON` as an input type instead of structured `@strawberry.input`.
