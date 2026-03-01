---
name: sse_notifications
description: Enterprise Server-Sent Events (SSE) notification system — async streaming, Redis pub/sub fanout, connection lifecycle, authentication, heartbeats, and backpressure handling.
---

# SSE Notifications Skill

## Purpose

Define and enforce strict standards for implementing Server-Sent Events (SSE) for real-time notification delivery in a Django 6 ASGI system, using Redis pub/sub for horizontal scaling and multi-instance fanout.

## Scope

- SSE endpoint design and streaming
- Authentication and authorization for SSE connections
- Redis pub/sub integration for broadcasting
- Connection lifecycle management
- Heartbeat mechanism
- Reconnection strategy
- Backpressure handling
- Rate limiting
- Security hardening

## Responsibilities

1. ENFORCE async-only SSE endpoints.
2. ENFORCE authentication before stream opening.
3. ENFORCE Redis pub/sub for multi-instance broadcasting.
4. ENFORCE connection lifecycle management with heartbeats.
5. ENFORCE rate limiting on connection establishment.
6. PREVENT blocking operations in the event loop.
7. PREVENT token leakage via URLs or logs.
8. PREVENT resource exhaustion via unbounded connections.

---

## Mandatory Rules

### ALWAYS

1. ALWAYS use ASGI (`StreamingHttpResponse` or equivalent async streaming) for SSE endpoints. Never use WSGI.
2. ALWAYS authenticate the user BEFORE opening the SSE stream.
3. ALWAYS use short-lived, signed stream tokens for SSE authentication instead of long-lived JWTs in query params:
   ```python
   # Generate a signed stream token (valid for 60 seconds)
   from django.core.signing import TimestampSigner
   signer = TimestampSigner()
   stream_token = signer.sign(str(user.id))

   # Validate on SSE connection
   user_id = signer.unsign(stream_token, max_age=60)  # Expires after 60 seconds
   ```
4. ALWAYS send a `connected` event immediately upon successful connection:
   ```
   event: connected
   data: {"user_id": 123, "connection_id": "uuid"}
   retry: 3000
   ```
5. ALWAYS send heartbeat events at a regular interval (30 seconds default) to keep the connection alive and detect stale connections:
   ```
   event: heartbeat
   data: {}
   ```
6. ALWAYS set SSE headers correctly:
   ```python
   response['Content-Type'] = 'text/event-stream'
   response['Cache-Control'] = 'no-cache'
   response['Connection'] = 'keep-alive'
   response['X-Accel-Buffering'] = 'no'  # Disable nginx/proxy buffering
   ```
7. ALWAYS set the `retry` field on the initial event to control client reconnection delay (recommended: 3000ms).
8. ALWAYS include `id` field on notification events to support `Last-Event-ID` for missed event recovery:
   ```
   id: 456
   event: ASSIGNMENT_PUBLISHED
   data: {"id": 456, "title": "...", ...}
   ```
9. ALWAYS use Redis pub/sub for broadcasting notifications to SSE connections across multiple server instances:
   ```python
   # Publishing (in notification service after DB write)
   redis_client.publish(f"notifications:{user_id}", json.dumps(notification_data))

   # Subscribing (in SSE view)
   pubsub = redis_client.pubsub()
   await pubsub.subscribe(f"notifications:{user_id}")
   async for message in pubsub.listen():
       yield format_sse_event(message)
   ```
10. ALWAYS enforce per-user connection limits (max 3-5 concurrent SSE connections per user). Reject with HTTP 429 if exceeded.
11. ALWAYS clean up resources (Redis subscriptions, connection tracking) in a `finally` block when the SSE connection closes.
12. ALWAYS use non-blocking async operations in the event loop. Never call synchronous ORM queries, `time.sleep()`, or blocking I/O inside the SSE generator.
13. ALWAYS format SSE events according to the spec — double newline (`\n\n`) terminates each event:
    ```
    id: 123\n
    event: NOTIFICATION_TYPE\n
    data: {"key": "value"}\n
    \n
    ```
14. ALWAYS log connection open, close, and error events with user ID and connection ID.

### NEVER

1. NEVER send long-lived access tokens (JWTs) in query parameters. Query params are logged by proxies, CDNs, and browsers. Use short-lived signed tokens exchanged right before connection.
2. NEVER perform database queries inside the SSE event loop. All data must come from Redis pub/sub messages or pre-computed payloads.
3. NEVER use `time.sleep()` inside async SSE generators. Use `asyncio.sleep()`.
4. NEVER keep stale connections open indefinitely. Implement a maximum connection duration (e.g., 30 minutes) and force reconnection.
5. NEVER block the event loop with CPU-intensive computations. Offload to Celery or thread pool.
6. NEVER log the stream authentication token value. Log token metadata (user ID, expiry) only.
7. NEVER send SSE events to a user without checking their notification preferences first.
8. NEVER rely on SSE as the sole delivery mechanism. Always persist notifications to the database. SSE is a delivery optimization, not a source of truth.
9. NEVER send sensitive data (passwords, tokens, PII beyond what's necessary) in SSE payloads.
10. NEVER use GraphQL subscriptions as a substitute for SSE in this architecture.

---

## Architectural Constraints

### SSE Flow Architecture

```
┌───────────────┐     ┌───────────────┐     ┌───────────────────┐
│  Frontend     │     │  Django ASGI  │     │  Redis Pub/Sub    │
│  EventSource  │────▶│  SSE View     │◀────│  Channel          │
│               │     │  (streaming)  │     │  notifications:42 │
└───────────────┘     └───────────────┘     └───────────────────┘
                                                     ▲
                                                     │
                                            ┌────────┴─────────┐
                                            │  Notification    │
                                            │  Service         │
                                            │  (after DB write)│
                                            └──────────────────┘
```

### Connection Lifecycle

```
1. Client sends GET /api/notifications/stream/?token=<signed_token>
2. Server validates signed token (max_age=60s)
3. Server checks per-user connection limit
4. Server sends "connected" event with retry=3000
5. Server subscribes to Redis channel notifications:{user_id}
6. Loop:
   a. Listen for Redis messages → yield SSE event
   b. Every 30s → yield heartbeat event
   c. If client disconnects → break
   d. If max_duration exceeded → send "reconnect" event, break
7. Finally: unsubscribe Redis, remove connection tracking, log
```

### Notification Broadcast Flow

```
1. Business event occurs (e.g., assignment published)
2. Signal receiver or service calls notification_service.create_notification()
3. Notification saved to database (source of truth)
4. transaction.on_commit() triggers Redis publish to user's channel
5. SSE view receives via Redis pubsub → streams to client
6. Client receives event → updates UI, shows toast
```

---

## Authentication Pattern

### Short-Lived Stream Token Flow

```python
# Step 1: Client requests a stream token via GraphQL mutation
@strawberry.mutation(permission_classes=[IsAuthenticated])
def create_stream_token(self, info: Info) -> str:
    user = info.context["request"].user
    signer = TimestampSigner(salt='sse-stream')
    return signer.sign(str(user.id))

# Step 2: Client opens EventSource with the short-lived token
# new EventSource(`/api/notifications/stream/?token=${streamToken}`)

# Step 3: SSE view validates the token (max 60 seconds old)
def authenticate_stream(token: str) -> User:
    signer = TimestampSigner(salt='sse-stream')
    user_id = signer.unsign(token, max_age=60)
    return User.objects.get(id=user_id, is_active=True)
```

---

## Heartbeat Strategy

1. Send heartbeat every 30 seconds.
2. Track last heartbeat time per connection.
3. Mark connections as stale if no heartbeat acknowledgement for 5 minutes.
4. Clean up stale connections in a periodic background task:
   ```python
   # Celery beat task — runs every 5 minutes
   @shared_task
   def cleanup_stale_sse_connections():
       SSEConnectionManager.cleanup_stale_connections(max_age_seconds=300)
   ```

---

## Backpressure Handling

1. If a client is slow to consume events, buffer up to 100 events in memory per connection.
2. If the buffer exceeds 100 events, drop the oldest events and send a `missed_events` notification:
   ```
   event: missed_events
   data: {"count": 15, "message": "Some notifications were dropped. Refresh to see all."}
   ```
3. Monitor buffer sizes per connection. Alert if >50% of connections are buffering.

---

## Rate Limiting

1. Limit SSE connection establishment to 10 attempts per minute per user.
2. Limit total concurrent SSE connections to 3 per user.
3. Limit total concurrent SSE connections per server instance based on available resources.
4. Return HTTP 429 with `Retry-After` header when limits are exceeded.

---

## Reconnection Strategy

1. Set `retry: 3000` on initial connection (3-second reconnection delay).
2. Clients should use the `Last-Event-ID` header on reconnection.
3. On reconnection, the server should check for missed notifications between `Last-Event-ID` and current, and send them before entering the live stream.
4. If too many events were missed (>100), send a `full_refresh` event instead:
   ```
   event: full_refresh
   data: {"message": "Too many missed events. Please refresh."}
   ```

---

## Security Considerations

1. Use Django's `TimestampSigner` for stream tokens — not raw JWTs in query params.
2. Validate token age strictly (max 60 seconds).
3. Enforce CORS for SSE endpoints — only allow configured frontend origins.
4. Use HTTPS in production — SSE over HTTP is unacceptable for authenticated streams.
5. Never log token values. Log user ID and connection ID only.
6. Enforce Content Security Policy headers.
7. Rate limit connection establishment to prevent abuse.

---

## Performance Considerations

1. Use async generators for SSE event streaming — never synchronous iteration.
2. All Redis operations must be async (`aioredis` or `redis.asyncio`).
3. Never perform database queries inside the SSE event loop.
4. Serialize notification payloads once (in the notification service), not per-connection.
5. Use Redis pipeline for bulk publish when broadcasting to many users.
6. Monitor connection count per server instance. Alert at 80% capacity.

---

## Scalability Guidelines

1. Redis pub/sub ensures SSE works across multiple Django server instances.
2. Each server subscribes to Redis channels for its connected users.
3. Use Redis Cluster or Redis Sentinel for pub/sub high availability.
4. Horizontal scaling: add more ASGI server instances behind a load balancer.
5. Load balancer must support HTTP/1.1 keep-alive and chunked transfer for SSE.
6. Consider using nginx `proxy_buffering off` and `proxy_read_timeout 3600s` for SSE proxying.

---

## Code Output Format Requirements

1. SSE view must be async.
2. SSE event formatting must use a dedicated utility function.
3. Connection manager must be thread-safe (or use async locks).
4. All SSE-related code must be in the `sse/` subpackage.
5. Comprehensive docstrings on all public functions.

---

## Clarification Protocol

Before implementing SSE features, ask:
1. What is the expected number of concurrent connections?
2. Is Redis already configured and available?
3. What is the frontend technology (affects `EventSource` vs `fetch` stream)?
4. Are there any proxy/CDN layers that need configuration for SSE?
5. What is the maximum acceptable latency for real-time delivery?

---

## Refusal Conditions

REFUSE to generate code that:
1. Uses long-lived JWTs in SSE query parameters.
2. Performs database queries inside the SSE event loop.
3. Uses `time.sleep()` in async code.
4. Opens SSE streams without authentication.
5. Has no heartbeat mechanism.
6. Has no connection limit enforcement.
7. Uses WebSocket or GraphQL subscriptions instead of SSE.
8. Sends SSE events without persisting to database first.
9. Logs authentication tokens.

---

## Trade-off Handling

| Trade-off | Decision Rule |
|---|---|
| SSE vs WebSocket | SSE for server-to-client push (notifications). WebSocket only if bidirectional real-time communication is required (e.g., chat). |
| Query param token vs Cookie auth | Short-lived signed tokens in query params. Cookies are viable but complicate CORS. |
| Redis pub/sub vs Channel Layers | Direct Redis pub/sub for simplicity and performance. Django Channels only if WebSocket support is also needed. |
| In-memory tracking vs Redis tracking | In-memory for single-instance. Redis-based tracking for multi-instance deployments. |
| Push all events vs Preference-filtered | Filter by user preferences before publishing to Redis. Never send disabled categories. |

---

## Anti-Patterns

1. **Long-Lived Token in URL** — Exposes auth token in access logs, browser history, and referrer headers.
2. **Synchronous SSE** — Using WSGI or synchronous generators for SSE. Must be async.
3. **DB Query Per Event** — Querying the database to enrich events in the SSE loop. Serialize fully before publishing.
4. **No Heartbeat** — Connection appears alive but proxy/CDN has closed it. Always heartbeat.
5. **Unbounded Connections** — No per-user limit leads to resource exhaustion.
6. **Fire and Forget** — Relying on SSE as the only delivery channel without database persistence.
