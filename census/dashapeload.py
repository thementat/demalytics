from pathlib import Path
from django.contrib.gis.utils import LayerMapping
from .models import DABoundary

da_mapping = {
    'dauid' : 'DAUID',
    'dguid' : 'DGUID',
    'landarea' : 'LANDAREA',
    'pruid' : 'PRUID',
    'geom' : 'MULTIPOLYGON',
}

da_shp = '/home/ubuntu/Downloads/lda_000b21a_e.shp'

def run(verbose=True):
    lm = LayerMapping(DABoundary, da_shp, da_mapping, transform=False)
    lm.save(strict=True, verbose=verbose)