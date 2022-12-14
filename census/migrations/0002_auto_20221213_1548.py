# Generated by Django 3.2.16 on 2022-12-13 15:48

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('census', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='boundary',
            name='area',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='boundary',
            name='code',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='boundary',
            name='geom',
            field=django.contrib.gis.db.models.fields.MultiPolygonField(srid=4269),
        ),
    ]
