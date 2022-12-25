from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
import requests, json

# Create your models here.
class Store(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    geom = models.PointField(srid=3347)

    def __str__(self):
        return self.name

    def update_isos(self):
        key = 'sk.eyJ1IjoicHJvcHNhdmFudCIsImEiOiJjbGJyejdhb3oxMWZlM3Ntd3VzZG9rN2VoIn0.FI9TYJ6qGTmc4SVwWd7F_w'
        url = 'https://api.mapbox.com/isochrone/v1/'
        profile = 'mapbox/driving'
        coord = self.geom.transform(4326, clone=True)
        polygons = True
        #denoise = float(1.0)

        # get the times we need for models
        times = IsoTime.objects.all()
        timestr = ''
        isos = []
        for i, t in enumerate(times, start=1):
            timestr = timestr + ',' + str(t.time)


            if i % 4 == 0 or i == len(times):
                timestr = timestr[1:]
                api_url = url \
                          + profile + '/'\
                          + str(coord.x) + ',' + str(coord.y) + '?' \
                          + 'contours_minutes=' + timestr \
                          + '&polygons=true&access_token=' \
                          + key
                response = requests.get(api_url)
                j = response.json()

                isos = isos + j['features']
                timestr = ''

        for i, iso in enumerate(isos):
            g = GEOSGeometry(json.dumps(iso['geometry']))
            m = MultiPolygon(g)
            m.srid = g.srid
            m.transform(3347)

            StoreIso(store=self, time=times[i], geom=m).save()







class IsoTime(models.Model):
    time = models.IntegerField(primary_key=True)

class StoreIso(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    time = models.ForeignKey(IsoTime, on_delete=models.RESTRICT)
    geom = models.MultiPolygonField(srid=3347)

    def __str__(self):
        return self.name


class StoreIsoWeighting(models.Model):
    name = models.CharField(max_length=50)
    weights = models.ManyToManyField(IsoTime, through='StoreIsoWeight')

    def __str__(self):
        return self.name

class StoreIsoWeight(models.Model):
    storeisoweighting = models.ForeignKey(StoreIsoWeighting, on_delete=models.CASCADE)
    time = models.ForeignKey(IsoTime, on_delete=models.RESTRICT)
    weight = models.FloatField()


class DemandModel(models.Model):
    name = models.CharField(max_length=50)
    fields = models.ManyToManyField('census.Field', through='Coefficient')

    def __str__(self):
        return self.name

class Coefficient(models.Model):
    demandmodel = models.ForeignKey(DemandModel, on_delete=models.CASCADE)
    field = models.ForeignKey('census.Field', on_delete=models.CASCADE)
    value = models.FloatField()