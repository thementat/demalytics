from django.contrib import admin
from .models import (Store, PerimSet, Perim, SupplyModel,
                     ModelWeights, StorePerim, SupplyAnalysis,
                     DemandModel, DemandAnalysis, Coefficient)

# Register your models here.

admin.site.register(Store)
admin.site.register(PerimSet)
admin.site.register(Perim)
admin.site.register(SupplyModel)
admin.site.register(ModelWeights)
admin.site.register(StorePerim)
admin.site.register(SupplyAnalysis)
admin.site.register(DemandModel)
admin.site.register(DemandAnalysis)
admin.site.register(Coefficient)
