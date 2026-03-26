from profile_management.models import AcademicYear, Semester


class AcademicService:
    @staticmethod
    def academic_years():
        return AcademicYear.objects.all()

    @staticmethod
    def current_academic_year():
        return AcademicYear.objects.filter(is_current=True).first()

    @staticmethod
    def academic_year_by_id(academic_year_id):
        return AcademicYear.objects.filter(id=academic_year_id).first()

    @staticmethod
    def semesters(academic_year_id=None):
        qs = Semester.objects.select_related("academic_year")
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs

    @staticmethod
    def current_semester():
        return Semester.objects.select_related("academic_year").filter(is_current=True).first()

    @staticmethod
    def semester_by_id(semester_id):
        return Semester.objects.select_related("academic_year").filter(id=semester_id).first()
