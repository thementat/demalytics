from django.contrib.gis.db import models

# Create your models here.

class DABoundary(models.Model):
    dauid = models.CharField(max_length=8)
    dguid = models.CharField(max_length=21)
    landarea = models.DecimalField(max_digits=12, decimal_places=4)
    pruid = models.CharField(max_length=2)
    geom = models.MultiPolygonField(srid=3347)


class Boundary(models.Model):
    code = models.CharField(max_length=100, unique=True)
    area = models.FloatField()
    geom = models.MultiPolygonField(srid=3347)

    def __str__(self):
        return self.name

class Field(models.Model):
    code = models.CharField(max_length=100)
    boundary = models.ManyToManyField(Boundary, through='BoundaryData')

    def __str__(self):
        return self.name

class BoundaryData(models.Model):
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    data = models.DecimalField(decimal_places=4, max_digits=30) #TODO: find field scale