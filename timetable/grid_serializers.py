from rest_framework import serializers
from django.utils.dateparse import parse_time
from datetime import timedelta, datetime
from timetable.models import TimetableGrid, PeriodSlot
from core.models import Department

class PeriodSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodSlot
        fields = ['id', 'slot_number', 'slot_type', 'start_time', 'end_time', 'label']

class TimetableGridSerializer(serializers.ModelSerializer):
    slots = PeriodSlotSerializer(many=True)
    day_start = serializers.TimeField(write_only=True)
    day_end = serializers.TimeField(write_only=True)

    class Meta:
        model = TimetableGrid
        fields = ['id', 'department', 'academic_year', 'effective_from', 'is_active', 'created_by', 'created_at', 'updated_at', 'slots', 'day_start', 'day_end']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        slots_data = attrs.get('slots', [])
        day_start = attrs.get('day_start')
        day_end = attrs.get('day_end')

        if not slots_data:
            raise serializers.ValidationError({"slots": "At least one slot is required."})

        # Ensure slots are ordered by slot_number
        slots_data.sort(key=lambda x: x['slot_number'])

        # Business rules
        lunch_count = 0
        class_count = 0

        # Create dummy date for time math
        dummy_date = datetime(2000, 1, 1)

        total_day_duration = (datetime.combine(dummy_date, day_end) - datetime.combine(dummy_date, day_start)).total_seconds()
        total_slots_duration = 0

        for i, slot in enumerate(slots_data):
            if slot['slot_type'] == 'lunch':
                lunch_count += 1
            if slot['slot_type'] == 'class':
                class_count += 1

            if slot['slot_number'] != i + 1:
                raise serializers.ValidationError({"slots": "Slot numbers must be sequential starting from 1."})

            start_dt = datetime.combine(dummy_date, slot['start_time'])
            end_dt = datetime.combine(dummy_date, slot['end_time'])
            
            if start_dt >= end_dt:
                raise serializers.ValidationError({"slots": f"Slot {slot['slot_number']} start time must be before end time."})

            total_slots_duration += (end_dt - start_dt).total_seconds()

            if i > 0:
                prev_end = datetime.combine(dummy_date, slots_data[i-1]['end_time'])
                if start_dt != prev_end:
                    raise serializers.ValidationError({"slots": "Slots must be contiguous with no gaps."})

        if lunch_count > 1:
            raise serializers.ValidationError({"slots": "Only one lunch slot allowed per grid."})

        if class_count < 4:
            raise serializers.ValidationError({"slots": "At least 4 class periods are required per day."})

        if total_slots_duration > total_day_duration:
            raise serializers.ValidationError({"slots": "Total slot duration must not exceed day start and end time difference."})

        if slots_data[0]['start_time'] != day_start:
            raise serializers.ValidationError({"slots": "First slot start time must match day_start."})
            
        if slots_data[-1]['end_time'] != day_end:
            raise serializers.ValidationError({"slots": "Last slot end time must match day_end."})

        return attrs

    def create(self, validated_data):
        slots_data = validated_data.pop('slots')
        validated_data.pop('day_start')
        validated_data.pop('day_end')
        
        grid = TimetableGrid.objects.create(**validated_data)
        
        period_slots = [
            PeriodSlot(grid=grid, **slot_data)
            for slot_data in slots_data
        ]
        PeriodSlot.objects.bulk_create(period_slots)
        
        return grid

    def update(self, instance, validated_data):
        slots_data = validated_data.pop('slots', None)
        validated_data.pop('day_start', None)
        validated_data.pop('day_end', None)

        # Update Grid fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Recreate slots
        if slots_data is not None:
            instance.slots.all().delete()
            period_slots = [
                PeriodSlot(grid=instance, **slot_data)
                for slot_data in slots_data
            ]
            PeriodSlot.objects.bulk_create(period_slots)

        return instance
