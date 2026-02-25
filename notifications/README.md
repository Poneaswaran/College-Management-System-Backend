# Notifications System

A production-grade, real-time notification system for the College Management System built with Django 6.0, Strawberry GraphQL, and Server-Sent Events (SSE).

## Features

- **Real-time Delivery**: Server-Sent Events (SSE) for instant notification delivery
- **GraphQL API**: Full CRUD operations via Strawberry GraphQL
- **Category-Based**: Organized by Attendance, Assignment, Grade, and System notifications
- **User Preferences**: Per-category notification settings
- **Redis Pub/Sub**: Scalable real-time broadcasting
- **Auto-generation**: Signal-based automatic notification creation
- **Production-Ready**: Proper error handling, logging, pagination, and indexes

## Architecture

```
notifications/
├── models.py                    # Notification & NotificationPreference models
├── constants.py                 # Enums for types, priorities, categories
├── services/                    # All business logic
│   ├── notification_service.py  # Core CRUD operations
│   ├── preference_service.py    # User preference management
│   ├── broadcast_service.py     # Redis pub/sub broadcasting
│   └── cleanup_service.py       # Periodic cleanup
├── graphql/                     # GraphQL API
│   ├── types.py                 # Strawberry types
│   ├── queries.py               # GraphQL queries
│   ├── mutations.py             # GraphQL mutations
│   └── permissions.py           # Permission classes
├── attendance/                  # Attendance notifications
├── assignments/                 # Assignment notifications
├── grades/                      # Grade notifications
├── system/                      # System announcements
└── sse/                         # SSE delivery
    ├── views.py                 # SSE streaming endpoint
    ├── authentication.py        # JWT auth for SSE
    └── connection_manager.py    # Connection tracking
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `redis==5.0.1` - Redis client for pub/sub
- `djangorestframework==3.14.0` - For SSE endpoint

### 2. Install and Start Redis

**Windows:**
```bash
# Download Redis from https://github.com/microsoftarchive/redis/releases
# Or use WSL/Docker
docker run -d -p 6379:6379 redis:latest
```

**Linux/Mac:**
```bash
# Install Redis
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis                  # macOS

# Start Redis
redis-server
```

### 3. Run Migrations

```bash
python manage.py makemigrations notifications
python manage.py migrate
```

### 4. Configure Settings

The app is already configured in `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'notifications',
]

# Redis Configuration
REDIS_URL = 'redis://localhost:6379/0'

# Notification Settings
NOTIFICATION_SSE_HEARTBEAT_INTERVAL = 30
NOTIFICATION_SSE_MAX_CONNECTIONS_PER_USER = 3
NOTIFICATION_CLEANUP_DAYS = 90
NOTIFICATION_DEFAULT_EXPIRY_HOURS = 168
```

## Usage

### GraphQL API

#### Queries

```graphql
# Get user's notifications (paginated)
query {
  myNotifications(category: "ATTENDANCE", isRead: false, limit: 20, offset: 0) {
    notifications {
      id
      title
      message
      notificationType
      category
      priority
      actionUrl
      metadata
      isRead
      actorName
      createdAt
      timeAgo
    }
    totalCount
    unreadCount
    hasMore
  }
}

# Get unread count
query {
  unreadCount(category: "ASSIGNMENT")
}

# Get notification preferences
query {
  myNotificationPreferences {
    category
    isEnabled
    isSseEnabled
    isEmailEnabled
  }
}

# Get notification statistics
query {
  notificationStats {
    totalCount
    unreadCount
    readCount
    byCategory
  }
}
```

#### Mutations

```graphql
# Mark notification as read
mutation {
  markNotificationRead(notificationId: 123) {
    id
    isRead
    readAt
  }
}

# Mark all notifications as read
mutation {
  markAllNotificationsRead(category: "ATTENDANCE")
}

# Dismiss notification
mutation {
  dismissNotification(notificationId: 123)
}

# Bulk dismiss notifications
mutation {
  bulkDismissNotifications(notificationIds: [1, 2, 3])
}

# Update notification preference
mutation {
  updateNotificationPreference(
    category: "ATTENDANCE"
    isEnabled: true
    isSseEnabled: true
    isEmailEnabled: false
  ) {
    category
    isEnabled
    isSseEnabled
  }
}

# Send announcement (admin only)
mutation {
  sendAnnouncement(
    title: "System Maintenance"
    message: "Scheduled maintenance on Sunday"
    recipientRole: "STUDENT"
    priority: "HIGH"
  )
}
```

### SSE (Real-time Notifications)

#### JavaScript/Frontend Example

```javascript
// Connect to SSE stream
const token = 'your-jwt-token';
const eventSource = new EventSource(
  `http://localhost:8000/api/notifications/stream/?token=${token}`
);

// Listen for connection
eventSource.addEventListener('connected', (e) => {
  const data = JSON.parse(e.data);
  console.log('Connected to notification stream:', data);
});

// Listen for notifications
eventSource.addEventListener('ASSIGNMENT_PUBLISHED', (e) => {
  const notification = JSON.parse(e.data);
  console.log('New assignment:', notification);
  // Update UI with notification
  showNotification(notification);
});

eventSource.addEventListener('ATTENDANCE_SESSION_OPENED', (e) => {
  const notification = JSON.parse(e.data);
  showAttendanceAlert(notification);
});

// Listen for heartbeat (connection keep-alive)
eventSource.addEventListener('heartbeat', () => {
  console.log('Heartbeat received');
});

// Handle errors
eventSource.onerror = (error) => {
  console.error('SSE connection error:', error);
  // EventSource will automatically reconnect
};

// Close connection when needed
eventSource.close();
```

## Creating Notifications

### Via Services (Recommended)

```python
from notifications.attendance import services as attendance_services
from notifications.assignments import services as assignment_services
from notifications.system import services as system_services

# Notify attendance session opened
attendance_services.notify_session_opened(
    session=attendance_session,
    students=student_list,
    actor=faculty_user
)

# Notify assignment graded
assignment_services.notify_assignment_graded(
    student=student_user,
    assignment=assignment_obj,
    grade_value="A+",
    actor=faculty_user
)

# Create announcement
system_services.create_announcement(
    recipients=all_students,
    title="Holiday Notice",
    message="College closed on Monday",
    priority="HIGH",
    actor=admin_user
)
```

### Via Signals

Notifications are automatically created for:

1. **Attendance Session Opened** - When session status → ACTIVE
2. **Attendance Session Closed** - Notifies absent students
3. **Assignment Published** - When assignment status → PUBLISHED
4. **Assignment Graded** - When Grade created
5. **Submission Received** - When student submits assignment

## Notification Types

### Attendance
- `ATTENDANCE_SESSION_OPENED` - Session opened for marking
- `ATTENDANCE_SESSION_CLOSED` - Session closed (for absent students)
- `LOW_ATTENDANCE_ALERT` - Attendance below threshold
- `ATTENDANCE_MARKED` - Attendance marked confirmation

### Assignments
- `ASSIGNMENT_PUBLISHED` - New assignment available
- `ASSIGNMENT_DUE_SOON` - Assignment deadline approaching
- `ASSIGNMENT_OVERDUE` - Missed assignment deadline
- `ASSIGNMENT_GRADED` - Assignment graded
- `SUBMISSION_RECEIVED` - Faculty notified of submission

### Grades
- `GRADE_PUBLISHED` - Grade published
- `RESULT_DECLARED` - Semester results declared

### System
- `ANNOUNCEMENT` - System/admin announcements
- `FEE_REMINDER` - Fee payment reminders
- `SYSTEM_ALERT` - Critical system alerts
- `PROFILE_UPDATE` - Profile change notifications

## Management Commands

### Cleanup Old Notifications

Run as a daily cron job:

```bash
# Preview what would be deleted
python manage.py cleanup_notifications --dry-run --verbose

# Actually delete old notifications
python manage.py cleanup_notifications
```

Deletes:
- Dismissed notifications older than 30 days
- Read notifications older than 90 days
- Expired notifications

### Cron Job Setup (Linux)

```bash
# Edit crontab
crontab -e

# Add daily cleanup at 2 AM
0 2 * * * cd /path/to/project && python manage.py cleanup_notifications
```

## Testing

```bash
# Run all notification tests
python manage.py test notifications

# Run specific test file
python manage.py test notifications.tests.test_notification_service

# Run with coverage
coverage run --source='notifications' manage.py test notifications
coverage report
```

## Production Deployment

### 1. Use PostgreSQL

Update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cms_db',
        'USER': 'cms_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 2. Redis Configuration

```python
# Production Redis with password
REDIS_URL = 'redis://:password@redis-host:6379/0'
```

### 3. CORS for SSE

```python
CORS_ALLOWED_ORIGINS = [
    "https://yourfrontend.com",
]
```

### 4. Logging

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'notifications.log',
        },
    },
    'loggers': {
        'notifications': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

## Security

- **JWT Authentication**: SSE endpoint requires valid JWT token
- **Ownership Checks**: Users can only access their own notifications
- **Connection Limits**: Maximum 3 concurrent SSE connections per user
- **Rate Limiting**: Consider adding rate limiting for GraphQL mutations
- **CORS**: Configure properly for production

## Performance Optimization

1. **Database Indexes**: Already configured on models
2. **Select Related**: Queries use `select_related()` for foreign keys
3. **Bulk Operations**: Use `bulk_create()` for multiple notifications
4. **Redis Pipelines**: Bulk broadcast uses Redis pipelines
5. **Pagination**: Queries are paginated by default

## Troubleshooting

### Redis Connection Error

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Check Redis connection in Python
python manage.py shell
>>> from notifications.services.broadcast_service import BroadcastService
>>> BroadcastService.test_connection()
```

### SSE Not Receiving Events

1. Check Redis is running
2. Verify JWT token is valid
3. Check browser console for SSE errors
4. Ensure CORS headers are set correctly

### Notifications Not Auto-Creating

1. Check signal receivers are registered (in `apps.py`)
2. Verify model signals are being fired
3. Check logs for errors in `receivers.py`

## API Reference

See inline documentation in:
- `services/notification_service.py` - Core functions
- `graphql/queries.py` - GraphQL queries
- `graphql/mutations.py` - GraphQL mutations
- `sse/views.py` - SSE endpoint

## Contributing

When adding new notification types:

1. Add to `constants.py` in appropriate enum
2. Create service function in relevant sub-module
3. Add signal receiver if auto-generating
4. Update this README

## License

Part of the College Management System project.
