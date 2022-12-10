from django.contrib.gis.db import models

# Create your models here.
class Store(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    geom = models.PointField()

    def __str__(self):
        return self.name

class StoreIso(models.Model):
    time = models.IntegerField()
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    geom = models.MultiPolygonField()

    def __str__(self):
        return self.name

class StoreIsoWeighting(models.Model):
    name = models.CharField(max_length=50)
    storeiso = models.ManyToManyField(StoreIso, through='StoreIsoWeight')

    def __str__(self):
        return self.name

class StoreIsoWeight(models.Model):
    storeiso = models.ForeignKey(StoreIso, on_delete=models.CASCADE)
    storeisoweighting = models.ForeignKey(StoreIsoWeighting, on_delete=models.CASCADE)
    weight = models.FloatField()


class Model(models.Model):
    name = models.CharField(max_length=50)
    field = models.ManyToManyField('census.Field', through='Coefficient')

    def __str__(self):
        return self.name

class Coefficient(models.Model):
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    field = models.ForeignKey('census.Field', on_delete=models.CASCADE)
    value = models.FloatField()