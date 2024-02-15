from django.contrib.gis.db import models
from pathlib import Path
from django.contrib.gis.utils import LayerMapping

# Create your models here.

class DABoundary(models.Model):
    dauid = models.CharField(max_length=8, primary_key=True)
    dguid = models.CharField(max_length=21)
    landarea = models.DecimalField(max_digits=12, decimal_places=4)
    pruid = models.CharField(max_length=2)
    geom = models.MultiPolygonField(srid=3347, spatial_index=True)

    @staticmethod
    def shp_import(shapefile):
        DABoundary.objects.all().delete()
        da_mapping = {
            'dauid': 'DAUID',
            'dguid': 'DGUID',
            'landarea': 'LANDAREA',
            'pruid': 'PRUID',
            'geom': 'MULTIPOLYGON',
        }

        #shapefile = '/Users/chrisbradley/Downloads/lda_000a21a_e'

        lm = LayerMapping(DABoundary, shapefile, da_mapping, transform=False)
        lm.save(strict=True, verbose=True)


class BGBoundary(models.Model):
    statefp = models.CharField(max_length=2)
    countyfp = models.CharField(max_length=3)
    tractce = models.CharField(max_length=6)
    blkgrpce = models.CharField(max_length=1)
    affgeoid = models.CharField(max_length=21)
    geoid = models.CharField(max_length=21, primary_key=True)
    name = models.CharField(max_length=100)
    namelsad = models.CharField(max_length=100)
    lsad = models.CharField(max_length=100)
    aland = models.BigIntegerField(null=True)
    awater = models.BigIntegerField(null=True)
    geom = models.MultiPolygonField(srid=4629, spatial_index = True)

    @staticmethod
    def shp_import(shapefile):
        BGBoundary.objects.all().delete()
        da_mapping = {
            'statefp' : 'STATEFP',
            'countyfp' : 'COUNTYFP',
            'tractce' : 'TRACTCE',
            'blkgrpce' : 'BLKGRPCE',
            'affgeoid' : 'AFFGEOID',
            'geoid' : 'GEOID',
            'name' : 'NAME',
            'namelsad' : 'NAMELSAD',
            'lsad' : 'LSAD',
            'aland' : 'ALAND',
            'awater' : 'AWATER',
            'geom' : 'MULTIPOLYGON'
        }

        #shapefile = '/Users/chrisbradley/Downloads/cb_2022_us_bg_500k'

        lm = LayerMapping(BGBoundary, shapefile, da_mapping, transform=False)
        lm.save(strict=True, verbose=True)

"""
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
    
"""