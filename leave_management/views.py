from rest_framework import status, views, permissions, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from .models import LeaveType, FacultyLeaveBalance, FacultyLeaveRequest, LeaveApprovalAction, WeekendSetting
from .serializers import (
    LeaveTypeSerializer, FacultyLeaveBalanceSerializer, FacultyLeaveRequestSerializer, 
    LeaveApplicationSerializer, WeekendSettingSerializer, LeavePolicySerializer, ResolvedPolicySerializer
)
from rest_framework import viewsets
from rest_framework.decorators import action
from .services import LeaveService
from profile_management.models import FacultyProfile

class IsFaculty(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'faculty_profile') or (request.user.role and request.user.role.code in ['FACULTY', 'HOD'])

class IsHOD(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role and request.user.role.code == 'HOD'

class IsHODOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return request.user.role and request.user.role.code == 'HOD'

class LeaveTypeListView(generics.ListAPIView):
    queryset = LeaveType.objects.filter(is_active=True)
    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsFaculty]

class FacultyLeaveBalanceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsFaculty]

    def get(self, request):
        try:
            faculty = request.user.faculty_profile
        except FacultyProfile.DoesNotExist:
             return Response({"error": "Faculty profile not found."}, status=status.HTTP_404_NOT_FOUND)
             
        balances = FacultyLeaveBalance.objects.filter(faculty=faculty)
        serializer = FacultyLeaveBalanceSerializer(balances, many=True)
        return Response(serializer.data)

class LeaveApplicationView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsFaculty]

    def get(self, request):
        # List own requests
        try:
            faculty = request.user.faculty_profile
        except FacultyProfile.DoesNotExist:
             return Response({"error": "Faculty profile not found."}, status=status.HTTP_404_NOT_FOUND)
             
        requests = FacultyLeaveRequest.objects.filter(faculty=faculty).order_by('-created_at')
        serializer = FacultyLeaveRequestSerializer(requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        try:
            faculty = request.user.faculty_profile
        except FacultyProfile.DoesNotExist:
             return Response({"error": "Faculty profile not found."}, status=status.HTTP_404_NOT_FOUND)
             
        serializer = LeaveApplicationSerializer(data=request.data)
        if serializer.is_valid():
            leave_type = serializer.validated_data['leave_type']
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']
            duration_type = serializer.validated_data['duration_type']

            # Validate
            is_valid, error_msg = LeaveService.validate_request(faculty, leave_type, start_date, end_date, duration_type)
            if not is_valid:
                return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Calculate days
                days = LeaveService.calculate_leave_days(faculty, start_date, end_date, duration_type)
                
                # Create request
                leave_request = serializer.save(faculty=faculty, status='SUBMITTED')
                
                # Update balance (move to pending)
                balance, created = FacultyLeaveBalance.objects.get_or_create(
                    faculty=faculty, 
                    leave_type=leave_type,
                    defaults={'total_granted': leave_type.annual_quota}
                )
                balance.pending = float(balance.pending) + float(days)
                balance.save()

            # Optional: Trigger AI summary in a background thread or synchronously for now
            try:
                import threading
                def get_ai_summary(req_id):
                    from .models import FacultyLeaveRequest
                    import requests
                    req = FacultyLeaveRequest.objects.get(id=req_id)
                    try:
                        resp = requests.post(
                            "http://localhost:8000/leave/summarize",
                            json={
                                "reason": req.reason,
                                "faculty_name": req.faculty.full_name,
                                "leave_type": req.leave_type.name,
                                "start_date": str(req.start_date),
                                "end_date": str(req.end_date)
                            },
                            timeout=10
                        )
                        if resp.status_code == 200:
                            req.ai_summary = resp.json().get("summary")
                            req.save()
                    except:
                        pass
                
                threading.Thread(target=get_ai_summary, args=(leave_request.id,)).start()
            except:
                pass

            return Response(FacultyLeaveRequestSerializer(leave_request).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HODLeaveApprovalView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        # List pending requests for HOD's department
        department = request.user.department
        if not department:
            return Response({"error": "HOD must be assigned to a department."}, status=status.HTTP_400_BAD_REQUEST)
        
        all_dept_requests = FacultyLeaveRequest.objects.filter(faculty__department=department)
        pending_requests = all_dept_requests.filter(status='SUBMITTED').order_by('created_at')
        
        from django.db.models import Count, Sum, Avg
        stats = all_dept_requests.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='SUBMITTED')),
            approved=Count('id', filter=Q(status='APPROVED')),
            rejected=Count('id', filter=Q(status='REJECTED')),
        )
        
        # Calculate total days for approved leaves
        total_days = 0
        for req in all_dept_requests.filter(status='APPROVED'):
            total_days += LeaveService.calculate_leave_days(req.faculty, req.start_date, req.end_date, req.duration_type)

        data = {
            "departmentName": department.name,
            "academicYear": "2025-2026", # Mock or fetch from config
            "summaryStats": {
                "totalRequests": stats['total'],
                "pendingCount": stats['pending'],
                "approvedCount": stats['approved'],
                "rejectedCount": stats['rejected'],
                "totalDaysRequested": total_days,
                "avgDaysPerRequest": total_days / stats['approved'] if stats['approved'] > 0 else 0
            },
            "leaveRequests": FacultyLeaveRequestSerializer(all_dept_requests.order_by('-created_at'), many=True).data
        }
        return Response(data)

    def post(self, request):
        request_id = request.data.get('request_id')
        action = request.data.get('action') # APPROVE or REJECT
        remarks = request.data.get('remarks', '')

        leave_request = get_object_or_404(FacultyLeaveRequest, id=request_id)
        if leave_request.status != 'SUBMITTED':
            return Response({"error": "Request is not in SUBMITTED state."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            days = LeaveService.calculate_leave_days(leave_request.faculty, leave_request.start_date, leave_request.end_date, leave_request.duration_type)
            balance = FacultyLeaveBalance.objects.get(faculty=leave_request.faculty, leave_type=leave_request.leave_type)
            
            prev_status = leave_request.status
            if action == 'APPROVE':
                leave_request.status = 'APPROVED'
                balance.pending = float(balance.pending) - float(days)
                balance.used = float(balance.used) + float(days)
            elif action == 'REJECT':
                leave_request.status = 'REJECTED'
                balance.pending = float(balance.pending) - float(days)
            else:
                return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

            balance.save()
            leave_request.hod_remarks = remarks
            leave_request.approved_by = request.user
            leave_request.save()

            # Audit trail
            LeaveApprovalAction.objects.create(
                request=leave_request,
                action_by=request.user,
                previous_status=prev_status,
                new_status=leave_request.status,
                remarks=remarks
            )

        return Response(FacultyLeaveRequestSerializer(leave_request).data)

class WeekendSettingsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        department = request.user.department
        settings = WeekendSetting.objects.filter(Q(department=department) | Q(department__isnull=True))
        serializer = WeekendSettingSerializer(settings, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Bulk update weekends for department
        department = request.user.department
        if not department:
            return Response({"error": "HOD must be assigned to a department."}, status=status.HTTP_400_BAD_REQUEST)
        
        days = request.data.get('weekends', []) # List of day integers [5, 6]
        
        with transaction.atomic():
            # Reset existing for dept
            WeekendSetting.objects.filter(department=department).delete()
            # Create new
            for day in days:
                WeekendSetting.objects.create(department=department, day=day, is_weekend=True)
        
        return Response({"status": "success"})

class LeavePolicyViewSet(viewsets.ModelViewSet):
    serializer_class   = LeavePolicySerializer
    permission_classes = [permissions.IsAuthenticated, IsHODOrAdmin]

    def get_queryset(self):
        from .models import LeavePolicy
        qs = LeavePolicy.objects.select_related(
            'tenant', 'school', 'department', 'leave_type', 'created_by'
        )
        scope = self.request.query_params.get('scope')
        school_id = self.request.query_params.get('school')
        dept_id = self.request.query_params.get('department')
        if scope:
            qs = qs.filter(scope=scope)
        if school_id:
            qs = qs.filter(school_id=school_id)
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='resolve')
    def resolve(self, request):
        """
        GET /api/leave/policies/resolve/?faculty_id=&leave_type_id=&as_of=YYYY-MM-DD
        Returns the effective resolved policy for a specific faculty + leave type combo.
        Useful for the frontend to show correct rules on the apply form.
        """
        from .policy_resolver import resolve_policy
        from profile_management.models import FacultyProfile

        faculty_id    = request.query_params.get('faculty_id')
        leave_type_id = request.query_params.get('leave_type_id')
        as_of_str     = request.query_params.get('as_of')

        if not faculty_id or not leave_type_id:
            return Response({"error": "faculty_id and leave_type_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        faculty    = get_object_or_404(FacultyProfile, pk=faculty_id)
        leave_type = get_object_or_404(LeaveType, pk=leave_type_id)

        as_of = None
        if as_of_str:
            from datetime import date
            try:
                as_of = date.fromisoformat(as_of_str)
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        resolved = resolve_policy(faculty, leave_type, as_of)
        return Response(ResolvedPolicySerializer(resolved).data)
