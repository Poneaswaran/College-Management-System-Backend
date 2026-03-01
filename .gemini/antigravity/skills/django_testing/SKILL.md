---
name: django_testing
description: Enterprise Django 6 testing — unit tests, integration tests, GraphQL resolver tests, SSE stream tests, permission tests, transaction rollback validation, and load testing guidance.
---

# Django Testing Skill

## Purpose

Define and enforce comprehensive testing standards for enterprise Django 6 systems, covering unit tests, integration tests, GraphQL resolver tests, SSE stream tests, permission tests, and performance/load testing.

## Scope

- Unit testing for services and models
- Integration testing for API flows
- GraphQL query and mutation testing
- SSE endpoint testing
- Permission and authorization testing
- Transaction and rollback testing
- Factory and fixture patterns
- Test isolation and performance
- Load testing guidance

## Responsibilities

1. ENFORCE test coverage for all services, resolvers, and critical paths.
2. ENFORCE test isolation — tests must not share state.
3. ENFORCE permission testing for every query and mutation.
4. ENFORCE transaction rollback validation for write operations.
5. ENFORCE SSE connection lifecycle testing.
6. PREVENT flaky tests, shared mutable state, and slow test suites.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS follow the Arrange-Act-Assert (AAA) pattern in every test:
   ```python
   def test_mark_notification_read(self):
       # Arrange
       notification = NotificationFactory(recipient=self.user, is_read=False)
       # Act
       result = notification_service.mark_as_read(notification.id, self.user)
       # Assert
       assert result.is_read is True
       assert result.read_at is not None
   ```
2. ALWAYS use `pytest` as the test runner with `pytest-django`.
3. ALWAYS use factory libraries (`factory_boy` / `model_bakery`) for test data creation. Never create test data with raw `Model.objects.create()` in multiple tests.
   ```python
   import factory
   from notifications.models import Notification

   class NotificationFactory(factory.django.DjangoModelFactory):
       class Meta:
           model = Notification
       recipient = factory.SubFactory(UserFactory)
       notification_type = "ASSIGNMENT_PUBLISHED"
       category = "ASSIGNMENT"
       priority = "MEDIUM"
       title = factory.Faker('sentence')
       message = factory.Faker('paragraph')
   ```
4. ALWAYS use `@pytest.mark.django_db` for tests that access the database.
5. ALWAYS test the happy path AND at least 2 edge cases / error paths per function.
6. ALWAYS test permission checks:
   - Unauthenticated user → rejected
   - Authenticated user without permission → rejected
   - Authenticated user with permission → allowed
   - User accessing another user's resource → rejected
7. ALWAYS test transaction behavior:
   ```python
   def test_bulk_create_is_atomic(self):
       """If one notification fails, none should be created."""
       with pytest.raises(ValueError):
           notification_service.bulk_create_notifications(
               recipients=[valid_user, invalid_user],
               notification_type="INVALID_TYPE",
               title="Test"
           )
       assert Notification.objects.count() == 0
   ```
8. ALWAYS use `freezegun` or `time_machine` for time-dependent tests. Never rely on wall clock time:
   ```python
   from time_machine import travel

   @travel("2026-02-25 12:00:00", tick=False)
   def test_notification_time_ago(self):
       notification = NotificationFactory(created_at=timezone.now() - timedelta(hours=2))
       assert get_time_ago(notification.created_at) == "2 hours ago"
   ```
9. ALWAYS name test methods descriptively: `test_<function>_<scenario>_<expected_result>`:
   ```python
   def test_mark_as_read_own_notification_succeeds(self): ...
   def test_mark_as_read_other_users_notification_raises_permission_error(self): ...
   def test_mark_as_read_nonexistent_notification_raises_not_found(self): ...
   ```
10. ALWAYS clean up any external resources (Redis connections, files, SSE connections) in test teardown.
11. ALWAYS use `assertNumQueries` or `django-assert-num-queries` to verify N+1 prevention:
    ```python
    def test_get_notifications_no_n_plus_1(self):
        NotificationFactory.create_batch(20, recipient=self.user)
        with self.assertNumQueries(2):  # 1 for notifications + 1 for actor
            list(notification_service.get_user_notifications(self.user, limit=20))
    ```
12. ALWAYS write separate test files per concern: `test_services.py`, `test_queries.py`, `test_mutations.py`, `test_models.py`, `test_permissions.py`.
13. ALWAYS use `conftest.py` for shared fixtures:
    ```python
    # conftest.py
    @pytest.fixture
    def authenticated_user(db):
        return UserFactory(is_active=True)

    @pytest.fixture
    def auth_context(authenticated_user):
        request = RequestFactory().get('/')
        request.user = authenticated_user
        return {"request": request}
    ```

### NEVER

1. NEVER use the production database for testing. Use Django's test database (`--keepdb` for speed).
2. NEVER share mutable state between tests. Each test must be fully independent.
3. NEVER use `time.sleep()` in tests to wait for async operations. Use `asyncio` event loop or mocks.
4. NEVER mock the function under test. Mock its dependencies, not itself.
5. NEVER write tests that depend on execution order.
6. NEVER hardcode absolute timestamps that break when run in different timezones. Use `timezone.now()` + deltas.
7. NEVER skip tests without a documented reason and a ticket/issue link:
   ```python
   @pytest.mark.skip(reason="Blocked by #GH-123: Redis not available in CI")
   def test_sse_broadcast(self): ...
   ```
8. NEVER write tests with no assertions.
9. NEVER use `print()` for test debugging. Use `pytest --capture=no` and `logging`.

---

## Test Organization

```
<app>/tests/
├── __init__.py
├── conftest.py            # Shared fixtures
├── factories.py           # Factory Boy factories
├── test_models.py         # Model validation, constraints, clean()
├── test_services.py       # Service layer business logic
├── test_queries.py        # GraphQL query resolvers
├── test_mutations.py      # GraphQL mutation resolvers
├── test_permissions.py    # Permission class tests
├── test_signals.py        # Signal receiver tests
└── test_sse.py            # SSE endpoint tests (if applicable)
```

---

## GraphQL Resolver Testing

### Query Testing

```python
import strawberry
from strawberry.test import GraphQLTestClient

@pytest.fixture
def graphql_client(auth_context):
    from project.schema import schema
    return GraphQLTestClient(schema, context_value=auth_context)

def test_my_notifications_query(graphql_client, authenticated_user):
    NotificationFactory.create_batch(5, recipient=authenticated_user)

    response = graphql_client.query("""
        query {
            myNotifications(limit: 10, offset: 0) {
                notifications {
                    id
                    title
                    isRead
                }
                totalCount
                unreadCount
                hasMore
            }
        }
    """)

    assert response.errors is None
    assert response.data["myNotifications"]["totalCount"] == 5
    assert len(response.data["myNotifications"]["notifications"]) == 5
```

### Mutation Testing

```python
def test_mark_notification_read_mutation(graphql_client, authenticated_user):
    notification = NotificationFactory(recipient=authenticated_user, is_read=False)

    response = graphql_client.query("""
        mutation MarkRead($id: Int!) {
            markNotificationRead(notificationId: $id) {
                id
                isRead
            }
        }
    """, variables={"id": notification.id})

    assert response.errors is None
    assert response.data["markNotificationRead"]["isRead"] is True
```

### Permission Testing

```python
def test_query_requires_authentication(graphql_client_anonymous):
    response = graphql_client_anonymous.query("""
        query { myNotifications(limit: 10, offset: 0) { totalCount } }
    """)
    assert response.errors is not None
    assert "not authenticated" in str(response.errors[0].message).lower()

def test_cannot_read_other_users_notification(graphql_client, authenticated_user):
    other_user = UserFactory()
    notification = NotificationFactory(recipient=other_user)

    response = graphql_client.query("""
        query GetNotif($id: Int!) {
            notificationById(notificationId: $id) { id }
        }
    """, variables={"id": notification.id})

    assert response.data["notificationById"] is None
```

---

## SSE Testing

```python
import asyncio
from django.test import AsyncRequestFactory
from notifications.sse.views import SSENotificationView

@pytest.mark.asyncio
async def test_sse_connection_requires_auth():
    factory = AsyncRequestFactory()
    request = factory.get('/api/notifications/stream/')
    # No token provided
    view = SSENotificationView.as_view()
    response = await view(request)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_sse_sends_connected_event(authenticated_sse_request):
    view = SSENotificationView.as_view()
    response = await view(authenticated_sse_request)
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/event-stream'
    # Read first event
    content = b''
    async for chunk in response.streaming_content:
        content += chunk
        if b'event: connected' in content:
            break
    assert b'event: connected' in content
```

---

## Transaction Rollback Testing

```python
def test_failed_bulk_create_rolls_back(db):
    """Verify atomic transaction on bulk notification creation."""
    initial_count = Notification.objects.count()

    with pytest.raises(Exception):
        with transaction.atomic():
            NotificationFactory.create_batch(5)
            raise IntegrityError("Simulated failure")

    assert Notification.objects.count() == initial_count  # Rolled back
```

---

## Load Testing Guidance

### Tools

- **Locust** for HTTP/GraphQL load testing.
- **k6** for SSE connection load testing.

### Scenarios to Test

1. **GraphQL query throughput**: 100 concurrent users querying `myNotifications`.
2. **GraphQL mutation throughput**: 50 concurrent users calling `markNotificationRead`.
3. **SSE connection capacity**: Ramp up to 1000 concurrent SSE connections.
4. **SSE notification delivery latency**: Measure time from notification creation to SSE event delivery.
5. **Bulk notification broadcast**: Create notification for 10,000 users and measure delivery time.

### Acceptance Criteria

| Metric | Target |
|---|---|
| GraphQL query p95 latency | < 200ms |
| GraphQL mutation p95 latency | < 500ms |
| SSE event delivery latency | < 1 second |
| Concurrent SSE connections (per instance) | > 5000 |
| Database query count per resolver | ≤ 3 |

---

## Code Output Format Requirements

1. All test files must have module-level docstrings describing what they test.
2. All test functions must have descriptive names following `test_<function>_<scenario>_<result>`.
3. Use `pytest.mark` annotations for categorization: `@pytest.mark.slow`, `@pytest.mark.integration`.
4. Factories must be in a dedicated `factories.py` file.

---

## Refusal Conditions

REFUSE to generate test code that:
1. Uses the production database.
2. Depends on test execution order.
3. Has no assertions.
4. Uses `time.sleep()` for synchronization.
5. Mocks the function under test.
6. Shares mutable state between tests.
7. Hardcodes wall clock timestamps.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| Unit vs Integration | Unit tests for services. Integration tests for full resolver flows. Both are required. |
| Real DB vs Mocked DB | Real test DB for model tests. Mock ORM for pure service logic tests. |
| Speed vs Coverage | Aim for 80%+ coverage. Mark slow tests with `@pytest.mark.slow` for optional exclusion. |
| Factory vs Fixture | Factories for dynamic test data. Fixtures for static shared setup (auth, context). |
