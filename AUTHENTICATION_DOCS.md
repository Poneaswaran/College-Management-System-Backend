# GraphQL Authentication Implementation

## Overview
All GraphQL queries and mutations now require authentication except for login-related operations.

## What Was Implemented

### 1. Authentication Utility Module
**File**: `core/graphql/auth.py`

Created reusable authentication utilities:
- `@require_auth` decorator - Enforces authentication on any resolver
- `IsAuthenticated` permission class - Strawberry-style permission
- `IsStaff`, `IsAdmin` permission classes - Role-based permissions
- `@require_role()` decorator - Enforce specific roles

### 2. Protected Resolvers

#### Core Module (`core/graphql/`)
**Queries** (5 resolvers - all require auth):
- `departments` - List all departments
- `courses` - List courses
- `sections` - List sections
- `roles` - List roles
- `users` - List users

**Mutations** (4 resolvers):
- `login` - ❌ NO AUTH (public endpoint)
- `refresh_token` - ❌ NO AUTH (public endpoint)
- `logout` - ✅ Requires auth
- `logout_all_sessions` - ✅ Requires auth

#### Profile Management (`profile_management/graphql/`)
**Queries** (3 resolvers - all require auth):
- `my_profile` - Get own profile
- `student_profile` - Get student by register number
- `student_profiles` - List students with filters

**Mutations** (4 resolvers):
- `update_student_profile` - ✅ Requires auth
- `admin_update_student_profile` - ✅ Requires auth
- `request_parent_otp` - ❌ NO AUTH (parent login flow)
- `verify_parent_otp` - ❌ NO AUTH (parent login flow)

#### Timetable Management (`timetable/graphql/`)
**Queries** (7 resolvers - all require auth):
- `current_semester` - Get active semester
- `section_timetable` - Get section's schedule
- `faculty_schedule` - Get faculty's teaching schedule
- `period_definitions` - Get period definitions
- `subjects` - List subjects
- `rooms` - List rooms
- `room_schedule` - Get room's schedule

**Mutations** (5 resolvers - all require auth):
- `create_timetable_entry` - Create new schedule entry
- `update_timetable_entry` - Update schedule entry
- `delete_timetable_entry` - Delete schedule entry
- `generate_periods` - Auto-generate periods
- `swap_timetable_slots` - Swap two schedule slots

#### Attendance System (`attendance/graphql/`)
**Queries** (8 resolvers - all require auth):
- `active_sessions_for_student` - Get student's active sessions
- `faculty_sessions_today` - Get faculty's sessions for today
- `attendance_session` - Get single session details
- `student_attendance_history` - Get attendance history
- `attendance_report` - Get attendance report
- `all_reports_for_student` - Get all reports for student
- `section_attendance_for_session` - Get all attendances for session
- `low_attendance_students` - Get students below threshold

**Mutations** (8 resolvers - all require auth):
- `open_attendance_session` - Faculty opens session
- `mark_attendance` - Student marks attendance
- `close_attendance_session` - Faculty closes session
- `block_attendance_session` - Faculty/Admin blocks session
- `reopen_blocked_session` - Reopen blocked session
- `manual_mark_attendance` - Manual attendance marking
- `bulk_mark_present` - Bulk mark students present
- `recalculate_attendance_report` - Recalculate report

## Total Coverage
- **23 Queries** - All require authentication ✅
- **21 Mutations** - 18 require authentication, 3 public (login flows) ✅

## How Authentication Works

### 1. JWT Middleware
The `JWTAuthenticationMiddleware` (in `core/middleware.py`) extracts JWT tokens from the `Authorization: Bearer <token>` header and attaches the authenticated user to `request.user`.

### 2. Authentication Check
The `@require_auth` decorator checks if `request.user.is_authenticated` before allowing resolver execution.

### 3. Error Handling
If authentication fails, users receive clear error messages:
- "Authentication required. Please login to access this resource."
- "Authentication failed: Token has expired"
- "Authentication failed: Invalid token"

## Usage Examples

### Authenticated Request
```graphql
# Header: Authorization: Bearer <access_token>

query {
  departments {
    id
    name
    code
  }
}
```

### Unauthenticated Request
```graphql
# No Authorization header

query {
  departments {
    id
    name
  }
}

# Response: Error: Authentication required. Please login to access this resource.
```

### Login (No Auth Required)
```graphql
mutation {
  login(data: {
    username: "student1@college.edu"
    password: "Test@123"
  }) {
    accessToken
    refreshToken
    user {
      email
      role {
        name
      }
    }
  }
}
```

## Security Features

1. **JWT Token Validation** - All tokens validated via middleware
2. **Token Blacklist** - Logged out tokens are blacklisted
3. **Expiry Checking** - Expired tokens are rejected
4. **Role-Based Access** - Additional role checks within resolvers
5. **Argon2 Password Hashing** - All passwords hashed with Argon2

## Testing Authentication

Run the test script:
```bash
pipenv run python test_auth.py
```

Or check schema:
```bash
pipenv run python manage.py check
```

## Public Endpoints (No Auth Required)

These endpoints are intentionally public:
1. `login` - User authentication
2. `refresh_token` - Token refresh
3. `request_parent_otp` - Parent OTP request (for guardian login)
4. `verify_parent_otp` - Parent OTP verification (for guardian login)

All other endpoints require valid JWT authentication.
