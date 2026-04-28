import os
import subprocess

commands = [
    # Core Base
    "seed_vels_data",
    "seed_courses",
    "seed_leave_system",
    "seed_profiles",
    "seed_vels_students",
    # Configuration
    "seed_institution_config",
    # Attendance
    "seed_attendance",
    "seed_hod_demo",
    # Grades
    "seed_grades",
    # Profile Management
    "seed_hod_data",
    # Timetable
    "seed_faculty_subjects",
    "seed_timetable_grid",
    "seed_timetable_subjects",
    "seed_timetable",
]

def run_seeding():
    for cmd in commands:
        print(f"--- Running: {cmd} ---")
        try:
            # Use tenant_command to run the command for the 'vels' schema
            subprocess.run([
                "pipenv", "run", "python", "manage.py", "tenant_command", 
                cmd, "--schema=vels"
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running {cmd}: {e}")

if __name__ == "__main__":
    run_seeding()
