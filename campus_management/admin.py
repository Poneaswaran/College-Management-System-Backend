from django.contrib import admin
from .models import Building, Floor, Venue, Facility, VenueFacility, Resource, ResourceAllocation

admin.site.register(Building)
admin.site.register(Floor)
admin.site.register(Venue)
admin.site.register(Facility)
admin.site.register(VenueFacility)
admin.site.register(Resource)
admin.site.register(ResourceAllocation)
