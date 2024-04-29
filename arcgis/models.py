from django.db import models

class end(models.Model):
    # contains the various perimeters used for each perimset (ie 10min ,20min...)
    perimset = models.ForeignKey(PerimSet, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    store = models.ManyToManyField(Store, through='StorePerim')
