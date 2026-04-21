# Timetable Assignment System

## Faculty Assignment Flexibility
The system supports a many-to-many relationship between Faculty, Subjects, and Sections. A single faculty member can:
- Teach the **same subject** to multiple different sections (e.g., Mathematics for Section A and Section B).
- Teach **different subjects** in the same department (e.g., Data Structures and Operating Systems).
- Teach across **different academic years** (e.g., 1st Year "Advanced Calculus" and 4th Year "Digital Electronics").

### Data Models Supporting This
- **`SectionSubjectRequirement`**: The primary planning model where HODs define which faculty teaches which subject to a specific section.
- **`TimetableSlot`**: The interactive grid used for manual assignment.
- **`TimetableEntry`**: The final scheduled record which links a faculty member to a specific section, subject, and time period.

### Scheduling Constraints
While assignments are flexible, the **`TimetableConflictValidator`** enforces strict logical constraints:
- **No Faculty Overlap**: A faculty member cannot be scheduled for two different classes at the same time period.
- **No Section Overlap**: A class section cannot have two different subjects at the same time.
- **No Room Overlap**: Two different classes cannot occupy the same room at the same time.

## Example Use Case: Dr. Suresh Babu
- **Assignment 1**: B.Tech Year 1 | Advanced Calculus | 4 Periods/Week
- **Assignment 2**: B.Tech Year 4 | Digital Electronics | 3 Periods/Week
- **Assignment 3**: B.Tech Year 3 | Data Structures | 5 Periods/Week

The system will allow all the above assignments and help the HOD schedule them across the 60 available slots (6 days × 10 periods) without overlaps.

## Section In-Charge (Class Teacher)
The system allows HODs to designate a specific faculty member as the **Section In-Charge** (Class Teacher) for each section in their department.

### Model: `SectionIncharge`
- **Fields**: `section`, `semester`, `faculty`.
- **Purpose**: Tracks the primary faculty member responsible for a class section's oversight, attendance verification, and student welfare for a specific academic cycle.

### Inheritance & Persistence (Auto-Carry-Over)
To reduce administrative overhead, the system implements an **intelligent inheritance mechanism**:
1. **Explicit Assignment**: If an HOD manually assigns a faculty member to a section for the *Current Semester*, that assignment is used.
2. **Auto-Carry-Over**: If no assignment exists for the current semester, the system automatically retrieves the **latest assignment** from previous semesters.
3. **Effective In-Charge**: This ensures that a Class Teacher remains responsible for their students as they progress through semesters unless the HOD explicitly makes a change in the management dashboard.
