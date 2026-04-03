from django.db import models
from django.core.exceptions import ValidationError

class Building(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    floor_number = models.IntegerField()

    def __str__(self):
        return f"{self.building.code} - Floor {self.floor_number}"

class Venue(models.Model):
    name = models.CharField(max_length=100)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='venues')
    venue_type = models.CharField(max_length=50) # e.g., CLASSROOM, LAB
    capacity = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.venue_type})"

class Facility(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class VenueFacility(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='venue_facilities')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='venue_facilities')

    class Meta:
        unique_together = ('venue', 'facility')

    def __str__(self):
        return f"{self.venue.name} - {self.facility.name}"

class Resource(models.Model):
    RESOURCE_TYPES = [
        ('ROOM', 'Room'),
    ]
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES, default='ROOM')
    reference_id = models.IntegerField() # Store Venue ID or other Resource ID
    is_active = models.BooleanField(default=True)

    @property
    def venue(self):
        if self.resource_type == 'ROOM':
            return Venue.objects.filter(id=self.reference_id).first()
        return None

    def __str__(self):
        return f"{self.resource_type} - {self.reference_id}"

class ResourceAllocation(models.Model):
    ALLOCATION_TYPES = [
        ('CLASS', 'Class'),
        ('EXAM', 'Exam'),
        ('EVENT', 'Event'),
        ('MAINTENANCE', 'Maintenance'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='allocations')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    allocation_type = models.CharField(max_length=50, choices=ALLOCATION_TYPES)
    source_app = models.CharField(max_length=50) # e.g., timetable, exams
    source_id = models.IntegerField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='ACTIVE')

    class Meta:
        # SQLite doesn't support complex range constraints, so check is on application side and simple valid range
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F('end_time')),
                name='campus_management_valid_allocation_range'
            )
        ]

    def __str__(self):
        return f"{self.allocation_type} on {self.resource} ({self.start_time} - {self.end_time})"

    def clean(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time.")
            
            # Application-level check for overlapping allocations
            overlapping = ResourceAllocation.objects.filter(
                resource=self.resource,
                status='ACTIVE',
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(id=self.id)
            
            if overlapping.exists():
                raise ValidationError("Overlapping allocation exists for this resource.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
