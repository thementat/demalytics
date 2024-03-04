from django.contrib.gis.db import models
from cacensus.models import DABoundary, getCensusData
from django.contrib.gis.db.models.functions import Transform


# Create your models here.

class Customer(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.name}"

class Characteristic(models.Model):
    id = models.IntegerField(primary_key=True)
    country = models.CharField(max_length=2)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('Characteristic', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

    '''
    sorted_chr = sorted(data, key=lambda x: int(x['id']))
    Characteristic.objects.all().delete()
    for s in sorted_chr:
        if 'parent' in s:
            Characteristic(id = int(s['id']), country='CA', name = s['name'], parent = Characteristic.objects.get(id=s['parent'])).save()
        else:
            Characteristic(id=int(s['id']), country='CA', name=s['name'], parent=None).save()
    '''
class Study(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    description = models.TextField(null=True)
    country = models.CharField(max_length=2)
    type = models.CharField(max_length=2)
    characteristics = models.ManyToManyField(Characteristic)
    geom = models.MultiPolygonField(srid=3857)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_geom = self.geom

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.popboundary()


        elif self.geom != self._original_geom:
            # The 'geom' field has been updated
            self.popboundary()

        super().save(*args, **kwargs)

    def popboundary(self):
        # Delete existing boundaries
        Boundary.objects.filter(study=self.id).delete()
        boundaries = []

        if self.country=="CA":

            bounds = DABoundary.objects.filter(geom__intersects=Transform(self.geom, 3347)).annotate(transformed_geom=Transform('geom', 3857))

            for b in bounds:
                boundaries.append(Boundary(study = self
                                          , ext_id = b.dauid
                                          , geom = b.transformed_geom))

        elif self.country=="US":
            bounds = BGBoundary.objects.filter(geom__intersects=Transform(self.geom, 4629))
            for b in bounds:
                boundaries.append(Boundary(study = self
                                          , ext_id = b.dauid
                                          , geom = b.transformed_geom))
        boundaries = Boundary.objects.bulk_create(boundaries)

    def popdata(self):

        self.boundarydata_set.all().delete()

        if self.country == "CA":

            flowref = 'STC_CP,DF_DA'
            frequency = 'A5'
            gender = '1'
            statistics = '1'
            characteristics = list(self.characteristics.values_list('id', flat=True))
            geography = list('2021S0512'+ bid for bid in Boundary.objects.filter(study=self).values_list('ext_id', flat=True))

            cd = getCensusData(flowref=flowref,
                             frequency=frequency,
                             gender=gender,
                             statistics=statistics,
                             characteristics=characteristics,
                             geography=geography)

            bd = []
            for k in cd:
                bd.append(BoundaryData(study=self,
                                       boundary=Boundary.objects.get(ext_id=k['geography'][9:]),
                                       characteristic=Characteristic.objects.get(id=k['characteristic']),
                                       value=k['value']))

            BoundaryData.objects.bulk_create(bd)

    def runStudy(self):
        self.popdata()

    def __str__(self):
        return f"{self.name}"



class Boundary(models.Model):
    #TODO: make this a manytoMany with Study
    #TODO: make the ext_id refer to dguid and eliminate the prefix
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    ext_id = models.CharField(max_length=30)
    geom = models.MultiPolygonField(srid=3857)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['study', 'ext_id'], name='unique_constraint')
        ]

#

class BoundaryData(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    characteristic = models.ForeignKey(Characteristic, on_delete=models.CASCADE)
    value = models.FloatField()




