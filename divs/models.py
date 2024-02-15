from django.contrib.gis.db import models

# Create your models here.
class Customer(models.Model):
    name = models.CharField(max_length=30)

class Problem(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    geom = models.MultiPolygonField(srid=4326)