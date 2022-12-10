from django.contrib.gis.db import models

# Create your models here.

class Geometry(models.Model):
    code = models.CharField(max_length=100)
    geom = models.MultiPolygonField()

    def __str__(self):
        return self.name

class Field(models.Model):
    code = models.CharField(max_length=100)
    geometry = models.ManyToManyField(Geometry, through='Data')

    def __str__(self):
        return self.name

class GeometryData(models.Model):
    geometry = models.ForeignKey(Geometry, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    data = models.DecimalField() #TODO: find field scale