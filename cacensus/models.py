from django.contrib.gis.db import models
from pathlib import Path
from django.contrib.gis.utils import LayerMapping
import requests


# Create your models here.

class DABoundary(models.Model):
    dauid = models.CharField(max_length=8, primary_key=True)
    dguid = models.CharField(max_length=21)
    landarea = models.DecimalField(max_digits=12, decimal_places=4)
    pruid = models.CharField(max_length=2)
    geom = models.MultiPolygonField(srid=3347, spatial_index=True)

    def __str__(self):
        return f"{self.name}"

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

        # shapefile = '/Users/chrisbradley/Downloads/lda_000a21a_e'

        lm = LayerMapping(DABoundary, shapefile, da_mapping, transform=False)
        lm.save(strict=True, verbose=True)


def getCensusData(**kwargs):
    if 'flowref' in kwargs:
        flowref = kwargs['flowref']
    else:
        raise TypeError('getCensusCA missing flowref parameter')

    if 'frequency' in kwargs:
        frequency = kwargs['frequency']
    else:
        raise TypeError('getCensusCA missing frequency parameter')

    geography = kwargs['geography'] if 'geography' in kwargs else ''
    gender = kwargs['gender'] if 'gender' in kwargs else ''
    characteristics = kwargs['characteristics'] if 'characteristics' in kwargs else ''
    statistics = kwargs['statistics'] if 'statistics' in kwargs else ''

    if isinstance(gender, list):
        gender = '+'.join(str(i) for i in gender)

    if isinstance(characteristics, list):
        characteristics = '+'.join(str(i) for i in characteristics)

    if isinstance(statistics, list):
        statistics = '+'.join(str(i) for i in statistics)

    if isinstance(geography, str):
        geography = [geography]

    # this is explained in greater detail at https://www12.statcan.gc.ca/wds-sdw/2021profile-profil2021-eng.cfm
    headers = {
        'Accept': 'application/vnd.sdmx.data+json;version=1.0.0-wd'
    }

    wsEntryPoint = 'api.statcan.gc.ca/census-recensement/profile/sdmx/rest'
    resource = 'data'
    parameters = '?detail=dataonly'

    bd = []

    maxcodes = 100  # moaximum number of geographys to request per call
    while len(geography) > 0:
        length = min(maxcodes, len(geography))
        bound_ids_str = '+'.join(bid for bid in geography[0:length])

        key = frequency + '.' + bound_ids_str + '.' + gender + '.' + characteristics + '.' + statistics  # frequency.geography.gender.characteristic.statistic
        url = 'http://' + wsEntryPoint + '/' + resource + '/' + flowref + '/' + key + parameters

        response = requests.get(url, headers=headers)
        data = response.json()['data']['dataSets'][0]['series']
        dims = response.json()['data']['structure']['dimensions']['series']
        # Initialize a list of 5 empty lists to hold the positional numbers
        position_lists = [[] for _ in range(5)]

        # Iterate over each key
        for key in data.keys():
            # Split the key into parts and convert each part to an integer
            parts = [int(part) for part in key.split(':')]

            # Distribute the parts into their respective lists
            for i, part in enumerate(parts):
                position_lists[i].append(part)

            bd.append(dict(
                frequency=dims[0]['values'][parts[0]]['id'],
                geography=dims[1]['values'][parts[1]]['id'],
                gender=dims[2]['values'][parts[2]]['id'],
                characteristic=dims[3]['values'][parts[3]]['id'],
                statistic=dims[4]['values'][parts[4]]['id'],
                value=float(data[key]['observations']['0'][0].strip() or '0.0')
            ))

        geography[0:length] = []

    return bd


from django.db import models

# Create your models here.
