# 🎓 College Management System — Feature Tracker

> **Last Updated:** 2026-02-25  
> **Status Legend:** ✅ Implemented | 🔨 In Progress | 📋 Planned | 💡 Proposed

---

## Current System Overview

| Module | Models | GraphQL Queries | GraphQL Mutations | Status |
|---|---|---|---|---|
| **Core** | Department, Course, Section, Role, User, TokenBlacklist | departments, courses, sections, roles, users, me | login, refreshToken, logout, logoutAllSessions, createUser | ✅ |
| **Profile Management** | AcademicYear, Semester, StudentProfile, ParentProfile, ParentLoginOTP | ✅ | ✅ | ✅ |
| **Timetable** | TimetableConfiguration, Subject, PeriodDefinition, Room, TimetableEntry | ✅ | ✅ | ✅ |
| **Attendance** | AttendanceSession, StudentAttendance, AttendanceReport | ✅ | ✅ | ✅ |
| **Assignment** | Assignment, AssignmentSubmission, AssignmentGrade | ✅ | ✅ | ✅ |
| **Grades** | CourseGrade, SemesterGPA, StudentCGPA | ✅ | ✅ | ✅ |
| **Notifications** | Notification, NotificationPreference | ✅ (queries + SSE) | ✅ (mutations) | ✅ |
| **Exams** | Exam, ExamSchedule, ExamSeatingArrangement, ExamResult, HallTicket | ✅ (queries) | ✅ (mutations) | ✅ |

---

## 📋 Planned Features

### 1. Faculty Profile Module
**Priority:** 🔴 High  
**Status:** 📋 Planned  
**Description:** Create a dedicated `FacultyProfile` model with qualifications, specialization, office hours, and teaching load tracking. Currently faculty are just `User` records with a FACULTY role — no dedicated profile.

**Tasks:**
- [ ] Create `FacultyProfile` model (qualifications, designation, specialization, joining_date, office_hours, teaching_load)
- [ ] Create GraphQL types, queries, mutations
- [ ] Link faculty to subjects they teach
- [ ] Add faculty availability/office hours query
- [ ] Add admin mutations for faculty management

---

### 2. Exam Management Module
**Priority:** 🔴 High  
**Status:** ✅ Implemented  
**Description:** Complete exam lifecycle — scheduling, seating arrangement, hall ticket generation, marks entry, and result publication.

**Tasks:**
- [x] Create `Exam` model (type: internal/semester/supplementary, date, time, duration)
- [x] Create `ExamSchedule` model (subject, exam, room, date_time)
- [x] Create `ExamSeatingArrangement` model (exam, room, student, seat_number)
- [x] Create `ExamResult` model (student, exam, subject, marks, grade)
- [x] Hall ticket generation endpoint (GraphQL mutation)
- [x] Marks entry mutation (faculty/HOD only)
- [x] Result publication mutation (with verify → publish workflow)
- [x] Student exam history query
- [x] Semester result analytics query
- [x] Service layer (ExamService, ExamScheduleService, SeatingService, ResultService, HallTicketService)
- [x] Admin configuration with inlines
- [x] Room & invigilator conflict detection
- [x] Bulk seating assignment
- [x] Bulk marks entry
- [x] Bulk hall ticket generation (per section)
- [x] Hall ticket revocation

---

### 3. Leave Management Module
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** Student and faculty leave requests with approval workflows.

**Tasks:**
- [ ] Create `LeaveType` model (sick, casual, academic, on-duty)
- [ ] Create `LeaveRequest` model (student/faculty, type, from_date, to_date, reason, status, approved_by)
- [ ] Create `LeaveBalance` model (user, leave_type, academic_year, total, used, remaining)
- [ ] Student leave request mutation
- [ ] Faculty leave request mutation
- [ ] HOD/admin approval mutation
- [ ] Leave calendar query (who's absent today)
- [ ] Leave balance query
- [ ] Auto-update attendance records when leave is approved
- [ ] Notification on leave approval/rejection

---

### 4. Fee Management Module
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** Fee structure, payment tracking, dues, and receipt generation.

**Tasks:**
- [ ] Create `FeeStructure` model (course, semester, category, amount)
- [ ] Create `FeePayment` model (student, amount, payment_date, mode, transaction_id, receipt_number)
- [ ] Create `FeeWaiver` model (student, waiver_type, percentage/amount, approved_by)
- [ ] Create `FeeDue` model (student, semester, total, paid, balance, due_date)
- [ ] Payment recording mutation
- [ ] Receipt generation endpoint (PDF)
- [ ] Dues query per student/section/department
- [ ] Fee defaulter list query
- [ ] Payment history query
- [ ] Notification for upcoming dues and overdue payments

---

### 5. Announcement / Notice Board Module
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** College-wide, department-wide, and section-specific announcements with targeting.

**Tasks:**
- [ ] Create `Announcement` model (title, body, type, priority, target_audience, attachments, valid_from, valid_until, created_by)
- [ ] Create `AnnouncementTarget` model (announcement, target_type: ALL/DEPARTMENT/SECTION/YEAR, target_id)
- [ ] Create `AnnouncementReadReceipt` model (announcement, user, read_at)
- [ ] Create announcement mutation (faculty/HOD/admin)
- [ ] List announcements query (filtered by role and target)
- [ ] Mark announcement as read mutation
- [ ] Pin/unpin announcement mutation
- [ ] Notification trigger on new announcement
- [ ] Search announcements query

---

### 6. Library Management Module
**Priority:** 🟢 Low  
**Status:** 📋 Planned  
**Description:** Book catalog, issue/return tracking, fine management, and reservations.

**Tasks:**
- [ ] Create `Book` model (title, author, ISBN, publisher, edition, category, total_copies, available_copies)
- [ ] Create `BookIssue` model (student, book, issued_by, issued_at, due_date, returned_at, fine_amount)
- [ ] Create `BookReservation` model (student, book, reserved_at, expires_at, fulfilled)
- [ ] Issue book mutation
- [ ] Return book mutation (auto-calculate fine)
- [ ] Reserve book mutation
- [ ] Search books query
- [ ] Student issued books query
- [ ] Overdue books query
- [ ] Notification for due date reminders and overdue books

---

### 7. Discussion Forum / Q&A Module
**Priority:** 🟢 Low  
**Status:** 📋 Planned  
**Description:** Subject-wise discussion forums where students and faculty can post questions and answers. Encourages academic collaboration.

**Tasks:**
- [ ] Create `ForumPost` model (subject, author, title, body, is_pinned, is_resolved)
- [ ] Create `ForumReply` model (post, author, body, is_accepted_answer)
- [ ] Create `ForumVote` model (user, post/reply, vote_type: UP/DOWN)
- [ ] Create/edit post mutations
- [ ] Reply to post mutation
- [ ] Upvote/downvote mutation
- [ ] Mark as resolved / accepted answer mutation
- [ ] List posts by subject query
- [ ] Search posts query
- [ ] Notification on new reply to subscribed post

---

### 8. Event / Calendar Module
**Priority:** 🟢 Low  
**Status:** 📋 Planned  
**Description:** Academic calendar with holidays, events, exam dates, and custom events.

**Tasks:**
- [ ] Create `CalendarEvent` model (title, description, event_type, start_datetime, end_datetime, location, is_holiday, target_audience)
- [ ] Create `EventRSVP` model (event, user, response: ATTENDING/NOT_ATTENDING/MAYBE)
- [ ] Create event mutation (admin/faculty)
- [ ] List events query (with date range filter)
- [ ] RSVP mutation
- [ ] Upcoming events query
- [ ] Academic holiday calendar query
- [ ] iCal export endpoint (REST)
- [ ] Notification for upcoming events and new events

---

## 💡 Proposed Enhancements (Existing Modules)

### 9. Attendance Analytics & Reports
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** Advanced analytics for attendance data — trends, predictions, department comparisons.

**Tasks:**
- [ ] Daily attendance summary query (per section, per department)
- [ ] Weekly/monthly attendance trend query
- [ ] Low attendance student list (below threshold)
- [ ] Attendance heatmap data query (day-of-week × period patterns)
- [ ] Faculty-wise attendance compliance report
- [ ] Export attendance report as Excel/PDF (REST endpoint)
- [ ] Parent notification for low attendance alerts

---

### 10. Assignment Plagiarism Check Integration
**Priority:** 🟢 Low  
**Status:** 💡 Proposed  
**Description:** Integrate a basic plagiarism detection system for assignment submissions.

**Tasks:**
- [ ] Add `plagiarism_score` field to `AssignmentSubmission`
- [ ] Implement text similarity comparison between submissions (using cosine similarity or Jaccard)
- [ ] Background Celery task for plagiarism analysis on submission
- [ ] Query to get plagiarism report per assignment
- [ ] Flag submissions above threshold
- [ ] Notification to faculty for high plagiarism scores

---

### 11. Password Management & Security
**Priority:** 🔴 High  
**Status:** 📋 Planned  
**Description:** Password reset flows, forced password change on first login, and security enhancements.

**Tasks:**
- [ ] Forgot password mutation (generate OTP/token)
- [ ] Reset password mutation (validate OTP/token + set new password)
- [ ] Force password change on first login (add `must_change_password` field to User)
- [ ] Change password mutation (requires old password)
- [ ] Password history tracking (prevent reuse of last N passwords)
- [ ] Account lockout after N failed login attempts
- [ ] Login activity log query (IP, device, timestamp)

---

### 12. Bulk Operations
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** Bulk import/export for admin operations — student enrollment, marks entry, timetable setup.

**Tasks:**
- [ ] Bulk student enrollment via Excel upload (REST)
- [ ] Bulk marks entry via Excel upload (REST)
- [ ] Bulk timetable import via Excel/CSV (REST)
- [ ] Bulk user creation mutation
- [ ] Export students list as Excel (REST)
- [ ] Export grades as Excel (REST)
- [ ] Background Celery task for large imports with progress tracking
- [ ] Notification on bulk operation completion

---

### 13. Dashboard Analytics API
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  
**Description:** Role-specific dashboard data — aggregate counts, charts, and quick stats.

**Tasks:**
- [ ] **Student Dashboard:** GPA trend, attendance %, upcoming assignments, recent grades, next class
- [ ] **Faculty Dashboard:** today's classes, pending submissions to grade, section attendance averages, upcoming assignment deadlines
- [ ] **HOD Dashboard:** department attendance %, course-wise GPA distribution, faculty workload, low-attendance student alerts
- [ ] **Admin Dashboard:** total students/faculty counts, department-wise enrollment, system health metrics
- [ ] All dashboards as single optimized GraphQL queries
- [ ] Cache dashboard data with Redis (60-second TTL)

---

### 14. Academic Feedback / Course Evaluation
**Priority:** 🟢 Low  
**Status:** 💡 Proposed  
**Description:** Anonymous course and faculty feedback system for end-of-semester evaluation.

**Tasks:**
- [ ] Create `FeedbackForm` model (semester, subject, faculty, is_active, deadline)
- [ ] Create `FeedbackQuestion` model (form, question_text, question_type: RATING/TEXT/MCQ)
- [ ] Create `FeedbackResponse` model (form, student, submitted_at — anonymous)
- [ ] Create `FeedbackAnswer` model (response, question, answer_text/rating)
- [ ] Submit feedback mutation (anonymous — no user tracking)
- [ ] Feedback results query (aggregate only — HOD/admin)
- [ ] Enable/disable feedback form mutation
- [ ] Notification to students when feedback forms are available

---

### 15. Document Management (Student Records)
**Priority:** 🟢 Low  
**Status:** 💡 Proposed  
**Description:** Upload and manage student documents — ID proofs, certificates, transcripts.

**Tasks:**
- [ ] Create `StudentDocument` model (student, document_type, file, uploaded_by, verified_by, status)
- [ ] Upload document mutation (with file upload via multipart GraphQL)
- [ ] Verify document mutation (admin only)
- [ ] Student documents query
- [ ] Download document endpoint (REST)
- [ ] Document expiry tracking (e.g., ID cards)

---

### 16. Mentor-Mentee System
**Priority:** 🟢 Low  
**Status:** 💡 Proposed  
**Description:** Assign faculty mentors to students for academic guidance and progress tracking.

**Tasks:**
- [ ] Create `MentorAssignment` model (faculty, student, academic_year, is_active)
- [ ] Create `MentorMeeting` model (mentor_assignment, date, notes, action_items, next_meeting_date)
- [ ] Assign mentor mutation (HOD/admin)
- [ ] Log meeting mutation (faculty)
- [ ] My mentees query (faculty)
- [ ] My mentor query (student)
- [ ] Meeting history query
- [ ] Notification for upcoming mentor meetings

---

### 17. Internal Communication / Messaging
**Priority:** 🟢 Low  
**Status:** 💡 Proposed  
**Description:** Direct messaging between users within the CMS — student-to-faculty, faculty-to-HOD, etc.

**Tasks:**
- [ ] Create `Conversation` model (participants, created_at, last_message_at)
- [ ] Create `Message` model (conversation, sender, body, sent_at, read_by)
- [ ] Create conversation mutation
- [ ] Send message mutation
- [ ] List conversations query
- [ ] Conversation messages query (paginated)
- [ ] Unread message count query
- [ ] SSE integration for real-time message delivery

---

## 🔧 Infrastructure / DevOps Features

### 18. API Rate Limiting
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  

- [ ] Add per-user rate limiting on GraphQL endpoint
- [ ] Add per-IP rate limiting on login mutation
- [ ] Add rate limiting on SSE connection establishment
- [ ] Redis-backed rate limit counters
- [ ] Return `429 Too Many Requests` with `Retry-After` header

---

### 19. Audit Logging
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  

- [ ] Create `AuditLog` model (user, action, resource_type, resource_id, ip_address, timestamp, changes_json)
- [ ] Auto-log all mutations (grade updates, attendance changes, user creation)
- [ ] Admin query for audit log with filters
- [ ] Retain logs for minimum 1 year

---

### 20. Health Check & Monitoring Endpoints
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  

- [ ] `GET /health/` — process liveness check
- [ ] `GET /health/ready/` — DB + Redis connectivity check
- [ ] `GET /health/metrics/` — Prometheus-compatible metrics (request count, latency, error rate)
- [ ] SSE connection count metric
- [ ] Active user count metric

---

### 21. Database Migration to PostgreSQL
**Priority:** 🔴 High  
**Status:** 📋 Planned  
**Description:** Currently using SQLite. Must migrate to PostgreSQL for production — concurrency, full-text search, JSON indexing, and proper connection pooling.

- [ ] Set up PostgreSQL database
- [ ] Update `DATABASES` setting to use `psycopg2`
- [ ] Migrate data from SQLite to PostgreSQL
- [ ] Add PostgreSQL-specific indexes (GIN for JSONField, partial indexes)
- [ ] Configure connection pooling (PgBouncer or `CONN_MAX_AGE`)
- [ ] Test all queries against PostgreSQL

---

### 22. Celery Background Tasks Setup
**Priority:** 🔴 High  
**Status:** 📋 Planned  

- [ ] Configure Celery with Redis broker
- [ ] Set up Celery Beat for periodic tasks
- [ ] Task: Clean up expired blacklisted tokens
- [ ] Task: Clean up old notifications (>90 days)
- [ ] Task: Clean up stale SSE connections
- [ ] Task: Send attendance reminder notifications
- [ ] Task: Calculate and cache dashboard analytics
- [ ] Task: Generate attendance reports

---

### 23. GraphQL Query Depth & Complexity Limiting
**Priority:** 🟡 Medium  
**Status:** 📋 Planned  

- [ ] Add `QueryDepthLimiter(max_depth=10)` to schema extensions
- [ ] Add query complexity analysis
- [ ] Disable introspection in production
- [ ] Add request body size limit (100KB)
- [ ] Log and alert on rejected queries

---

## Implementation Priority Order

| Phase | Features | Timeline |
|---|---|---|
| **Phase 1 — Critical** | #21 PostgreSQL Migration, #11 Password Management, #22 Celery Setup | Week 1-2 |
| **Phase 2 — Core Modules** | #1 Faculty Profile, #2 Exam Management, #13 Dashboard Analytics | Week 3-4 |
| **Phase 3 — Student Experience** | #3 Leave Management, #5 Announcements, #9 Attendance Analytics | Week 5-6 |
| **Phase 4 — Infrastructure** | #18 Rate Limiting, #19 Audit Logging, #23 GraphQL Security, #20 Health Checks | Week 7 |
| **Phase 5 — Extended Modules** | #4 Fee Management, #12 Bulk Operations, #8 Events/Calendar | Week 8-9 |
| **Phase 6 — Nice to Have** | #6 Library, #7 Forum, #10 Plagiarism, #14 Feedback, #15 Documents, #16 Mentor, #17 Messaging | Week 10+ |

---

## Notes

- Each feature should follow the **service layer pattern** — no business logic in resolvers or models.
- All mutations must trigger **notifications** via the existing SSE + Redis pub/sub infrastructure.
- All new models must have **proper indexes**, `Meta.constraints`, and `verbose_name`.
- All new GraphQL resolvers must have **permission checks** and **DataLoaders** for relationships.
- This file is the source of truth for feature tracking. **Update checkbox status when implementing.**
