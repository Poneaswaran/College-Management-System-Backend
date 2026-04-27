from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from timetable.models import TimetableGrid
from timetable.grid_serializers import TimetableGridSerializer

class TimetableGridViewSet(viewsets.ModelViewSet):
    queryset = TimetableGrid.objects.all()
    serializer_class = TimetableGridSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    @action(detail=False, methods=['post'], url_path='from-ai')
    def from_ai(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        grid = self.get_object()
        slots = grid.slots.all().order_by('slot_number')
        
        # Calculate total duration in seconds for rendering proportions
        if slots.exists():
            first_slot = slots.first()
            last_slot = slots.last()
            from datetime import datetime
            dummy_date = datetime(2000, 1, 1)
            start_dt = datetime.combine(dummy_date, first_slot.start_time)
            end_dt = datetime.combine(dummy_date, last_slot.end_time)
            total_duration = (end_dt - start_dt).total_seconds()
            
            preview_data = []
            for slot in slots:
                s_dt = datetime.combine(dummy_date, slot.start_time)
                e_dt = datetime.combine(dummy_date, slot.end_time)
                duration = (e_dt - s_dt).total_seconds()
                
                preview_data.append({
                    "id": slot.id,
                    "slot_number": slot.slot_number,
                    "slot_type": slot.slot_type,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "label": slot.label,
                    "duration_mins": duration / 60,
                    "percentage": round((duration / total_duration) * 100, 2) if total_duration > 0 else 0
                })
                
            return Response(preview_data)
        return Response([])
