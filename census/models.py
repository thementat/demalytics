from django.contrib.gis.db import models
from pathlib import Path
from django.contrib.gis.utils import LayerMapping

# Create your models here.

'''
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

'''