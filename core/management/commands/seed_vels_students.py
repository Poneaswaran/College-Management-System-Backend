
import random
import string
from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import tenant_context
from django.utils import timezone
from datetime import date, timedelta, time
from decimal import Decimal

from tenants.models import Client
from core.models import School, Department, Course, Section, Role, User
from profile_management.models import StudentProfile, FacultyProfile, SectionIncharge, AcademicYear, Semester
from campus_management.models import Building, Floor, Venue
from timetable.models import Subject, Room, TimetableGrid, PeriodSlot, PeriodDefinition, TimetableEntry
from exams.models import Exam, ExamSchedule, ExamSeatingArrangement, ExamResult
from attendance.models import AttendanceReport

class Command(BaseCommand):
    help = "Seeds a complete ecosystem for Vels tenant including Timetable Entries and Period Definitions."

    def handle(self, *args, **options):
        schema_name = "vels"
        total_students_target = 1000
        students_per_section = 40
        
        raw_names = "Arun, Karthik, Vijay, Ajith, Suresh, Ramesh, Ganesh, Dinesh, Senthil, Prabhu, Saravanan, Manikandan, Vignesh, Naveen, Harish, Lokesh, Bharath, Ashwin, Kishore, Nithin, Rahul, Aravind, Gokul, Santhosh, Jagadeesh, Kumar, Mohan, Murugan, Rajesh, Prasanth, Venkatesh, Balaji, Siva, Anand, Deepak, Raghavan, Sathish, Kannan, Vinoth, Yuvaraj, Adithya, Abishek, Jeeva, Naren, Surya, Tamilselvan, Chandru, Elango, Sakthivel, Madhan, Priya, Divya, Kavya, Nandhini, Gayathri, Meena, Revathi, Sindhu, Anitha, Subashini, Yazhini, Abirami, Janani, Hema, Shanthi, Keerthana, Pavithra, Mahalakshmi, Vaishnavi, Harini, Ramya, Deepika, Aishwarya, Swathi, Ranjani, Sowmya, Bhavani, Dharani, Lavanya, Akshaya, Pooja, Sangeetha, Malathi, Rekha, Chitra, Kalpana, Bhuvana, Usha, Preethi, Monisha, Anu, Thenmozhi, Aparna, Madhumitha, Rohith, Varun, Pradeep, Sanjay, Akash, Naveenkumar, Hariharan, Kavin, Koushik, Mithun, Prithvi, Roshan, Sharath, Tarun, Udhay, Vishal, Yoganand, Arunmozhi, Boopathy, Charan, Dev, Ezhil, Farook, Guhan, Hari, Ilango, Jagan, Kabilan, Lenin, Muthu, Nandakumar, Omprakash, Pandian, Raja, Selvam, Tharun, Umesh, Velmurugan, Vikram, Wilson, Yashwanth, Zubair, Aadhavan, Bharani, Chockalingam, Devaraj, Eswar, Francis, Gopinath, Hariom, Iniyan, Johnson, Karthikeyan, Lingesh, Mahesh, Narayanan, Parthiban, Rajkumar, Sekar, Thiyagu, Ulaganathan, Varadharajan, Vivek, Ashok, Balamurugan, Chidambaram, Durai, Eshwar, Ganesan, Hemachandran, Ilavarasan, Jeyaraj, Kumaran, Logesh, Maran, Nirmal, Pandiyarajan, Ragul, Shankar, Thamizharasan, Vasanth, Abdul, Benny, Christopher, Daniel, Edwin, Felix, Gerald, Immanuel, Joseph, Kingston, Lawrence, Martin, Nelson, Peter, Richard, Stephen, Thomas, Victor, Antony, Aaron, Benjamin, Calvin, Dominic, Emmanuel, Franklin, George, Isaac, Joel, Kevin, Leon, Matthew, Noel, Paul, Quentin, Raymond, Samuel, Timothy, Uma, Aarthi, Bhanu, Charumathi, Devi, Ezhilarasi, Fathima, Geetha, Hemalatha, Indhu, Jothika, Kalaivani, Lalitha, Manimegalai, Nivetha, Oviya, Poornima, Queenie, Radhika, Suganya, Tamilarasi, Umamaheswari, Vidhya, Wincy, Yamuna, Zarina, Abarna, Banupriya, Chandra, Dhanalakshmi, Elakkiya, Fousiya, Gomathi, Hamsaveni, Ishwarya, Jeyanthi, Karpagam, Leelavathi, Malarvizhi, Nalini, Pavana, Rajeswari, Selvi, Thilagavathi, Udhaya, Vennila, Viji, Akila, Bhagyalakshmi, Chithra, Durgadevi, Esther, Florence, Gracy, Hemavathi, Inba, Jenifer, Kokila, Latha, Mohana, Nirmala, Priyadharshini, Roja, Sathya, Thenral, Ushaarani, Vasuki, Anbarasi, Banumathi, Chenthur, Devika, Eashwari, Haripriya, Ilamathi, Jayashree, Kowsalya, Logambal, Maheswari, Nithya, Poongodi, Ramani, Saroja, Tharani, Umadevi, Vasanthi, Aadhira, Akshara, Amudha, Anjana, Arthi, Aswini, Bairavi, Bhavana, Chandhini, Darshini, Deepa, Dhiya, Elavarasi, Haritha, Janisha, Kanimozhi, Kaviya, Kiruthika, Madhavi, Nila, Oormila, Padmini, Reshma, Shalini, Trisha, Varsha, Aarav, Advaith, Akilan, Arjun, Bhuvan, Chetan, Darshan, Eesan, Faizal, Gautham, Hemanth, Iqbal, Jai, Krishna, Lalith, Mithran, Niranjan, Pranav, Rakshan, Sai, Tejas, Uday, Vasanthkumar, Wasim, Yuvin, Zayan, Adarsh, Barathkumar, Chezhian, Dharshan, Ebin, Feroz, Giri, Hitesh, Imran, Jishnu, Kamesh, Leninraj, Magesh, Navinraj, Praveen, Rithik, Shyam, Tamilanban, Vetrivel, Vimal, Aandal, Amritha, Bhuvaneswari, Chindhuja, Deepshika, Eshika, Femi, Gajalakshmi, Hansika, Ishana, Jeevitha, Kanishka, Laya, Mithila, Niharika, Oorja, Pragathi, Rithanya, Sanjana, Tanushree, Ujwala, Varunika, Wafiya, Yashika, Zoya, Aadhya, Brindha, Charvi, Diya, Eesha, Falguni, Grishma, Hridya, Inika, Joshna, Kashmira, Lekha, Manya, Navya, Oviyal, Parnika, Riya, Shruthi, Tanvi, Urmika, Vedhika, Aarthi, Binesh, Cholan, Dileep, Ezhilan, Fawas, Gokulan, Harikrishnan, Inbaraj, Jaganathan, Kousikan, Lokanath, Muthukumar, Nandakishore, Prakash, Rajan, Sarvesh, Thiru, Udhayan, Viknesh, Vishnu, Yatharth, Ameer, Balasubramanian, Chandrasekar, Dhanush, Ezhumalai, Gajendran, Haran, Iyyappan, Jeyakarthik, Kuberan, Madhesh, Narenkumar, Paramesh, Rajadurai, Subramani, Thangavel, Ulagappan, Vairavan, Viswanath, Yamir, Aadhil, Bhaskar, Cibi, Deenadayalan, Elanchezhian, Guhanraj, Hariprasath, Iniyavan, Jabez, Karthiban, Lingadurai, Murali, Nesan, Pugazh, Ranjith, Sivakumar, Thinesh, Vetrimaran, Vishwa, Yazhvendan"
        name_pool = [n.strip() for n in raw_names.split(',')]
        
        try:
            tenant = Client.objects.get(schema_name=schema_name)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant '{schema_name}' does not exist."))
            return

        with tenant_context(tenant):
            self.stdout.write(self.style.MIGRATE_HEADING(f"--- Full Seeding for {schema_name} including Timetable Entities ---"))
            
            with transaction.atomic():
                # 1. Roles & Admin
                student_role, _ = Role.objects.get_or_create(code="STUDENT", defaults={'name': 'Student', 'is_global': True})
                faculty_role, _ = Role.objects.get_or_create(code="FACULTY", defaults={'name': 'Faculty', 'is_global': True})
                hod_role, _ = Role.objects.get_or_create(code="HOD", defaults={'name': 'Head of Department', 'is_global': True})
                admin_role, _ = Role.objects.get_or_create(code="ADMIN", defaults={'name': 'System Administrator', 'is_global': True})
                
                admin_user, _ = User.objects.get_or_create(email="admin@vels.edu", defaults={'role': admin_role, 'is_staff': True, 'is_superuser': True, 'is_active': True})
                admin_user.set_password("Test@123")
                admin_user.save()

                # 2. Academic Timeline
                ay_code = "2024-25"
                ay, _ = AcademicYear.objects.get_or_create(year_code=ay_code, defaults={'start_date': date(2024, 6, 1), 'end_date': date(2025, 5, 31), 'is_current': True})
                semesters = {}
                for num in range(1, 9):
                    sem, _ = Semester.objects.update_or_create(
                        academic_year=ay, number=num, 
                        defaults={
                            'start_date': date(2024, 6, 1) if num % 2 != 0 else date(2024, 12, 1), 
                            'end_date': date(2024, 11, 30) if num % 2 != 0 else date(2025, 5, 31),
                            'is_current': (num == 2)
                        }
                    )
                    semesters[num] = sem
                active_sem = semesters[2]

                # 3. Period Definitions (Core Timetable Entity)
                self.stdout.write("Seeding Period Definitions...")
                period_defs = []
                for day_idx in range(1, 6): # Mon to Fri
                    for p_num in range(1, 6): # 5 periods
                        pd, _ = PeriodDefinition.objects.get_or_create(
                            semester=active_sem, period_number=p_num, day_of_week=day_idx,
                            defaults={'start_time': time(9+p_num-1, 0), 'end_time': time(10+p_num-1, 0), 'duration_minutes': 60}
                        )
                        period_defs.append(pd)

                # 4. Infrastructure & Faculty
                school, _ = School.objects.get_or_create(code="SOE", defaults={'name': 'School of Engineering'})
                dept_configs = [("Computer Science", "CSE"), ("Electronics", "ECE"), ("Mechanical", "MECH"), ("Information Tech", "IT"), ("Civil Engineering", "CIVIL")]
                building, _ = Building.objects.get_or_create(code="MAIN-BLOCK", defaults={'name': 'Main Academic Block'})
                
                dept_faculty = {}
                dept_subjects = {}
                name_idx = 0
                
                for i, (name, code) in enumerate(dept_configs):
                    dept, _ = Department.objects.get_or_create(code=code, defaults={'name': name, 'school': school})
                    dept_faculty[code] = []
                    
                    # Staff
                    for f_idx in range(4): # 4 per dept
                        role = hod_role if f_idx == 0 else faculty_role
                        email = f"{'hod' if f_idx == 0 else 'f'+str(f_idx)}.{code.lower()}@vels.edu"
                        f_user, _ = User.objects.get_or_create(email=email, defaults={'role': role, 'department': dept, 'is_staff': True})
                        f_user.set_password("Test@123")
                        f_user.save()
                        FacultyProfile.objects.get_or_create(user=f_user, defaults={'first_name': name_pool[name_idx % len(name_pool)], 'last_name': 'Staff', 'department': dept, 'joining_date': date(2022, 1, 1)})
                        name_idx += 1
                        dept_faculty[code].append(f_user)

                    # Subjects
                    dept_subjects[code] = {}
                    for sem_num in range(1, 9):
                        sub, _ = Subject.objects.update_or_create(code=f"{code}{sem_num}01", defaults={'name': f"{name} Sem {sem_num}", 'department': dept, 'semester_number': sem_num, 'credits': 4.0})
                        dept_subjects[code][sem_num] = sub

                    # Timetable Grid
                    grid, _ = TimetableGrid.objects.get_or_create(department=dept, academic_year=ay_code, defaults={'effective_from': ay.start_date, 'is_active': True})
                    PeriodSlot.objects.get_or_create(grid=grid, slot_number=1, defaults={'slot_type': 'class', 'start_time': time(9,0), 'end_time': time(10,0), 'label': 'P1'})

                    # Sections & Timetable Entries
                    course, _ = Course.objects.get_or_create(code=f"BE-{code}", department=dept, defaults={'name': f"BE {name}", 'duration_years': 4})
                    for s_idx in range(5):
                        year = (s_idx % 4) + 1
                        section, _ = Section.objects.update_or_create(course=course, code=chr(65+s_idx), year=year, defaults={'name': f"{code} Y{year} {chr(65+s_idx)}", 'priority': 2})
                        
                        room_name = f"Room {code}-{year}{chr(65+s_idx)}"
                        room, _ = Room.objects.get_or_create(room_number=room_name, defaults={'building': building.name, 'capacity': 60, 'department': dept})
                        
                        # Timetable Entry (Core Timetable Entity)
                        # Assign Mon-Fri P1 for each section
                        for d_idx in range(1, 6):
                            pd = PeriodDefinition.objects.get(semester=active_sem, day_of_week=d_idx, period_number=1)
                            TimetableEntry.objects.get_or_create(
                                section=section, period_definition=pd, semester=active_sem,
                                defaults={
                                    'subject': dept_subjects[code][year*2],
                                    'faculty': random.choice(dept_faculty[code]),
                                    'room': room,
                                    'allocation_id': 9999 # Placeholder for required field
                                }
                            )

                # 5. Students & Exams
                self.stdout.write("Seeding Students and Exam Results...")
                current_count = StudentProfile.objects.count()
                if current_count >= total_students_target:
                    self.stdout.write(self.style.SUCCESS(f"Found {current_count} students. Target of {total_students_target} already met or exceeded. Skipping student generation."))
                else:
                    students_to_create = total_students_target - current_count
                    self.stdout.write(f"Creating {students_to_create} more students to reach target of {total_students_target}...")
                    sections = list(Section.objects.all())
                    if not sections:
                        self.stdout.write(self.style.ERROR("No sections found to assign students to!"))
                    else:
                        for _ in range(students_to_create):
                            section = random.choice(sections)
                            reg_no = f"VST24{random.randint(100000, 999999)}"
                            while User.objects.filter(register_number=reg_no).exists(): reg_no = f"VST24{random.randint(100000, 999999)}"
                            user = User.objects.create(email=f"s.{reg_no.lower()}@vels.edu", register_number=reg_no, role=student_role, department=section.course.department, is_active=True)
                            user.set_password("Test@123")
                            user.save()
                            StudentProfile.objects.create(
                                user=user, 
                                first_name=name_pool[name_idx % len(name_pool)], 
                                last_name='Student', 
                                register_number=reg_no, 
                                department=section.course.department, 
                                course=section.course, 
                                section=section, 
                                year=section.year, 
                                semester=section.year*2, 
                                profile_completed=True
                            )
                            name_idx += 1

            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully seeded Timetable Entities for Vels!"))
            self.stdout.write(f"Entities: PeriodDefinitions (Mon-Fri) and TimetableEntries (Daily P1) created for all sections.")
