# Generated by Django 3.2.16 on 2022-12-16 23:12

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0004_auto_20221215_1235'),
    ]

    operations = [
        migrations.AlterField(
            model_name='store',
            name='geom',
            field=django.contrib.gis.db.models.fields.PointField(srid=3347),
        ),
        migrations.AlterField(
            model_name='storeiso',
            name='geom',
            field=django.contrib.gis.db.models.fields.MultiPolygonField(srid=3347),
        ),
    ]
