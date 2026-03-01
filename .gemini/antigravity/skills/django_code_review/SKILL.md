---
name: django_code_review
description: Enterprise Django 6 code review — review criteria, checklists, anti-pattern detection, and approval gates.
---

# Django Code Review Skill

## Purpose

Define and enforce systematic code review standards for enterprise Django 6 systems with Strawberry GraphQL and SSE.

## Scope

- Pull request review process and checklists
- Anti-pattern detection
- Performance, security, and migration audits
- Approval gates and blocking conditions

## Responsibilities

1. ENFORCE structured review for every code change.
2. ENFORCE architecture, security, and performance compliance.
3. PREVENT merging code with known anti-patterns or missing tests.

---

## Review Checklists

### General
- [ ] Service layer pattern followed (no business logic in resolvers/views/models)
- [ ] Type hints and docstrings on all functions
- [ ] No `print()`, no `*` imports, no hardcoded secrets
- [ ] `timezone.now()` only — no naive datetimes
- [ ] No bare `except:` clauses

### Model Changes
- [ ] Correct field types (`DecimalField` for money, `BigAutoField` for PKs)
- [ ] No `null=True` on CharField/TextField
- [ ] `related_name` on all ForeignKey/OneToOne
- [ ] `Meta.indexes` for query-used columns
- [ ] `__str__()`, `verbose_name` defined

### Migration Changes
- [ ] Descriptive name, auto-generated (not manual without justification)
- [ ] `RunPython` has `reverse_code`
- [ ] No destructive ops without expand-contract plan
- [ ] `AddIndexConcurrently` for production
- [ ] Schema and data migrations separated

### GraphQL Changes
- [ ] `permission_classes` on every query/mutation
- [ ] DataLoaders for relationship fields
- [ ] Pagination enforced — no unbounded lists
- [ ] Resolvers delegate to services
- [ ] Standardized error types
- [ ] Schema backward-compatible or deprecated

### SSE Changes
- [ ] Auth before stream opens
- [ ] No DB queries in event loop
- [ ] Heartbeat present
- [ ] Connection limits enforced
- [ ] Cleanup in `finally`

### Security
- [ ] Permission + ownership checks present
- [ ] No mass assignment, no SQL injection vectors
- [ ] No sensitive data in logs or error responses
- [ ] Input sanitization for stored HTML

### Performance
- [ ] No N+1 queries
- [ ] Bulk operations for batch writes
- [ ] `update_fields` on `.save()`
- [ ] Cache invalidation for mutated data
- [ ] Expensive work offloaded to Celery

### Tests
- [ ] Happy path + 2+ edge cases
- [ ] Permission tests (unauth, unauthorized, authorized)
- [ ] `test_<function>_<scenario>_<result>` naming

---

## Blocking Conditions

BLOCK merge if:
1. Business logic in resolvers or models
2. Missing permission checks
3. N+1 queries without mitigation
4. Hardcoded secrets or SQL injection risks
5. Non-reversible migrations
6. Missing tests for new functionality
7. Naive datetimes or bare `except:` clauses

---

## Anti-Patterns to Detect

| Anti-Pattern | Fix |
|---|---|
| Fat Resolver (>15 lines of logic) | Extract to service |
| N+1 Query in loop | `select_related`/DataLoader |
| Side-effect in `atomic()` | `transaction.on_commit()` |
| Mutable default arg | Use `None` + internal default |
| Commented-out code | Remove — use VCS history |
| Magic strings | Use `TextChoices`/constants |
| Catch-all exception | Catch specific, log, re-raise |

---

## Approval Gates

| Change Type | Approvals |
|---|---|
| Service logic | 1 developer |
| Model/migration | 1 dev + 1 senior |
| GraphQL schema | 1 dev + 1 senior |
| Security/auth | 1 dev + security reviewer |
| DevOps/infra | 1 dev + ops reviewer |

---

## Trade-off Handling

| Trade-off | Decision |
|---|---|
| Strict vs Speed | Strict for security/data integrity. Flexible for docs/UI. |
| 100% vs Pragmatic coverage | 80%+ services. 100% for security code. |
| Perfect vs Good enough | Block for anti-patterns/security. Suggest for style. |
