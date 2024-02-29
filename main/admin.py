from django.contrib import admin
from .models import Customer, Characteristic, Study, Boundary, BoundaryData

# Register your models here.
admin.site.register(Customer)
admin.site.register(Characteristic)
admin.site.register(Study)
admin.site.register(Boundary)
admin.site.register(BoundaryData)
