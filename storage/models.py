from django.db import models

# Create your models here.
class Store(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    instrument = models.CharField(max_length=100)

class Album(models.Model):
    artist = models.ForeignKey(Musician, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    release_date = models.DateField()
    num_stars = models.IntegerField()