from django.contrib.gis.db import models
from django.contrib.gis.db.models import Collect
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.contrib.gis.db.models.functions import Transform, Area, AsGeoJSON
from django.db.models import F, Q, Sum, Prefetch
import requests, json, os
from main.models import Boundary, BoundaryData, Study
from mapbox.utils import Source, Tileset
from cacensus.models import DABoundary
from collections import defaultdict

from django.core import serializers
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.
class Store(models.Model):
    masterid = models.IntegerField(primary_key=True)
    storeid = models.IntegerField()
    storename = models.CharField(max_length=100)
    url = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    zipcode = models.CharField(max_length=10, null=True, blank=True)
    geom = models.PointField(srid=3857)
    yearbuilt = models.IntegerField(null=True, blank=True)
    totalsqft = models.IntegerField(null=True, blank=True)
    rentablesqft = models.IntegerField(null=True, blank=True)
    storetype = models.CharField(max_length=50, null=True, blank=True)
    companytype = models.CharField(max_length=50, null=True, blank=True)
    classtype = models.CharField(max_length=1, null=True, blank=True)


    def __str__(self):
        return self.storename

    def updateStorePerims(self):
        #delete old perims
        StorePerim.objects.filter(store=self).delete()

        key = os.getenv('MB_KEY')
        url = 'https://api.mapbox.com/isochrone/v1/'
        profile = 'mapbox/driving'
        coord = self.geom.transform(4326, clone=True)
        polygons = True
        #denoise = float(1.0)

        # get the times we need for models
        times = Perim.objects.filter(perimset__name='ISO').order_by('name')
        timestr = ''
        isos = []
        for i, t in enumerate(times, start=1):
            timestr = timestr + ',' + str(t.name)


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
            m.transform(3857)

            StorePerim(store=self, perim=times.get(name=iso['properties']['contour']), geom=m).save()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_rentablesqft = self.rentablesqft
        self._original_geom = self.geom

    def save(self, *args, **kwargs):
        if self.pk is None:  # If this is a new instance
            self.updateStorePerims()
        else:                # If this is an existing instance
            if self.geom != self._original_geom:
                self.updateStorePerims()
            if self.rentablesqft != self._original_rentablesqft:
                self.updateStorePerims()


        super().save(*args, **kwargs)
        # After saving, update the original geometry so that subsequent saves won't trigger updateStorePerims
        # unless the geometry is changed again.
        self._original_geom = self.geom


class PerimSet(models.Model):
    # contains the sets of perimeters (ie. distance radius, drive-time isochrone etc.)
    name = models.CharField(max_length=50)

class Perim(models.Model):
    # contains the various perimeters used for each perimset (ie 10min ,20min...)
    perimset = models.ForeignKey(PerimSet, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    store = models.ManyToManyField(Store, through='StorePerim')

class StorePerim(models.Model):
    # contains the perimieter geometries centered on each store
    # created by Store.updateStorePerims()
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    perim = models.ForeignKey(Perim, on_delete=models.CASCADE)
    geom = models.MultiPolygonField(srid=3857)

class SupplyModel(models.Model):
    # contains the supplymodels, which are the different methods used to  distribute the supply among the perims
    name = models.CharField(max_length=50)
    perimset = models.ForeignKey(PerimSet, on_delete=models.CASCADE)
    perimweight = models.ManyToManyField(Perim, through='ModelWeights')

    def calcSPBSupply(self, study):
        # calculate the supply for each StorePerimBoundary

        #we use a demandmodel to allocate supply... select it here
        dm = DemandModel.objects.get(name='CSSVS')

        #delete the old StorePerimBoundary instances
        StorePerimBoundary.objects.filter(supplymodel=self).delete()
        SupplyAnalysis.objects.filter(study=study).filter(supplymodel=self).delete()

        weights = ModelWeights.objects.filter(supplymodel__name='SSA')
        stores = Store.objects.filter(geom__within=study.geom)
        for s in stores:
            storeperims = StorePerim.objects.filter(store=s).order_by('perim__name')

            #create a null perimeter
            boundary = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
            previous_p = StorePerim(store=s,
                                    perim=Perim(perimset=self.perimset, name='blank'),
                                    geom=MultiPolygon(Polygon(boundary))
                                    )
            spb = []
            for p in storeperims:
                weight = weights.get(perim=p.perim_id).weight
                bounds = Boundary.objects.filter(
                    geom__intersects=p.geom).filter(~Q(
                    geom__intersects=previous_p.geom)).prefetch_related(
                        Prefetch(
                            'demandanalysis_set',
                            queryset=DemandAnalysis.objects.filter(study=study).filter(demandmodel__name=dm.name),
                            to_attr='filtered_demand_analysis'
                        ))
                agg = sum(
                        demand_analysis.demand
                        for b in bounds
                        for demand_analysis in b.filtered_demand_analysis
                )


                for b in bounds:
                    spb.append(StorePerimBoundary(storeperim=p,
                                                    boundary=b,
                                                    supplymodel=self,
                                                    sqft=s.rentablesqft * weight * b.filtered_demand_analysis[0].demand / agg
                                                    ))

                previous_p = p
            spb = StorePerimBoundary.objects.bulk_create(spb)





class ModelWeights(models.Model):
    # stores the weight assigned to each perim in this supplymodel
    supplymodel = models.ForeignKey(SupplyModel, on_delete=models.CASCADE)
    perim = models.ForeignKey(Perim, on_delete=models.CASCADE)
    weight = models.FloatField()



class StorePerimBoundary(models.Model):
    #stores the sqft of supply contributed to each boundary by each store.
    # populated by SupplyModel.calcSupply
    storeperim = models.ForeignKey(StorePerim, on_delete=models.CASCADE)
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    supplymodel = models.ForeignKey(SupplyModel, on_delete=models.CASCADE)
    sqft = models.FloatField()



class SupplyAnalysis(models.Model):
    # Stores the aggregate supply for each boundary
    # populated by SupplyModel.calcSupply
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    supplymodel = models.ForeignKey(SupplyModel, on_delete=models.CASCADE)
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    supply = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('supplymodel', 'boundary',)




class DemandModel(models.Model):
    # stores the different methods we use to calculate demand

    name = models.CharField(max_length=50)
    fields = models.ManyToManyField('main.Characteristic', through='Coefficient')

    def calcDemand(self, study):
        # the only method we use currently is hard-coded here
        #TODO: eventually maybe rewrite this to use a heierarchical model to store arithmetic operations?
        DemandAnalysis.objects.filter(study=study).filter(demandmodel=self).delete()
        if self.name=='CSSVS':

            bounds = Boundary.objects.filter(study=study)

            # Inputs
            study_id = study.id
            characteristic_ids = [1, 113, 42, 43, 44, 45, 46, 47, 48, 49]

            # Initialize a structure to hold the final results
            # This will map boundary_id to a dictionary of characteristic_id to value
            boundary_characteristics = defaultdict(lambda: {cid: None for cid in characteristic_ids})

            for cid in characteristic_ids:
                # Fetch boundary_id and values for the current characteristic
                boundary_values = BoundaryData.objects.filter(
                    study_id=study_id,
                    characteristic_id=cid
                ).select_related(
                    'boundary'
                ).values(
                    'boundary_id',  # Changed to fetch boundary_id
                    'value'
                )

                # Update our results structure with the fetched values
                for item in boundary_values:
                    boundary_characteristics[item['boundary_id']][cid] = item['value']

            # Convert the defaultdict to a regular dict for the final output if necessary
            boundary_characteristics = dict(boundary_characteristics)

            sas = []
            for b in list(boundary_characteristics):
                data = boundary_characteristics[b]
                sas.append(DemandAnalysis(boundary_id=b,
                                            demandmodel=self,
                                            study = study,
                                            demand=(1 / 20 * 100 * (data[42] + data[43]) #single family
                                                    + 1 / 20 * 75 * (data[44] + data[45] + data[48]) #ground oriented MF
                                                    + 1 / 20 * 75 * (data[46] + data[47]) #MF Units
                                                    + 1 / 20 * 75 * (data[49]) #moveable units
                                                    + data[113] / 10000 * data[1] * 0.5) # retail sales proxy
                ))

            DemandAnalysis.objects.bulk_create(sas)


    def __str__(self):
        return self.name


class DemandAnalysis(models.Model):
    # Contains the aggregate demand for each boundary

    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    demandmodel = models.ForeignKey(DemandModel, on_delete=models.CASCADE)
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    demand = models.FloatField(null=True, blank=True)

class Coefficient(models.Model):
    demandmodel = models.ForeignKey(DemandModel, on_delete=models.CASCADE)
    field = models.ForeignKey('main.Characteristic', on_delete=models.CASCADE)
    value = models.FloatField()

    def __str__(self):
        return f"{self.name}"


class StorageStudy(Study):
    class Meta:
        proxy = True

    def addBoundaries(self):
        # The Study geometry contains several Boundaries, however, our analysis also requires the Boundaries that are
        # contained by the StorePerims.  This function adds those boundaries.


        stores_within_geometry = Store.objects.filter(geom__within=self.geom)
        unioned_isos = StorePerim.objects.filter(store__in=stores_within_geometry).aggregate(unioned_geoms=Collect('geom'))
        collected_geometry = unioned_isos['unioned_geoms'].unary_union
        bounds = DABoundary.objects.filter(
            geom__intersects=Transform(collected_geometry, 3347)).annotate(
            transformed_geom=Transform('geom', 3857))

        boundaries = []
        for b in bounds:
            boundaries.append(Boundary(study=self
                                       , ext_id=b.dauid
                                       , geom=b.transformed_geom))

        boundaries = Boundary.objects.bulk_create(boundaries, ignore_conflicts=True)

    def processStudy(self):
        # This calculates the demand & supply for a Study object.

        # add the new boundaries
        self.addBoundaries()

        # populate the characteristic data
        self.popdata()

        # retrieve the required DemandModel and calculate demandanalysis
        # currently the characteristics are retrieved here
        d = DemandModel.objects.get(name='CSSVS')
        d.calcDemand(study=self)

        # calculate the StorePerimBoundary Supply
        sm = SupplyModel.objects.get(id=1)
        sm.calcSPBSupply(self)


        # Assuming StorePerimBoundary is populated, Get boundary and supplymodel pairs from StorePerimBoundary
        queryset = StorePerimBoundary.objects.values('boundary', 'supplymodel').distinct()

        supply_analysis_list = []

        # Calculate the supply for each boundary
        for obj in queryset:
            # Get total supply for current boundary and supplymodel
            total_supply = \
                StorePerimBoundary.objects.filter(boundary=obj['boundary'], supplymodel=obj['supplymodel']).aggregate(
                    supply=Sum('sqft'))['supply']

            # Create new SupplyAnalysis instance
            supply_analysis = SupplyAnalysis(boundary_id=obj['boundary'], supplymodel_id=obj['supplymodel'],
                                             study=self, supply=total_supply)
            supply_analysis_list.append(supply_analysis)

        # Bulk create SupplyAnalysis instances
        SupplyAnalysis.objects.bulk_create(supply_analysis_list)

    def uploadStudy(self, filename='output.geojson'):
        # This uploads the Study data to mapbox

        study_id = self.id

        rows = (
            Boundary.objects
            .filter(study_id=study_id,
                    demandanalysis__study_id=F('study_id'),
                    supplyanalysis__study_id=F('study_id'),
                    geom__intersects=self.geom)
            .annotate(
                demand=F('demandanalysis__demand'),
                supply=F('supplyanalysis__supply'),
                demandmodel_id=F('demandanalysis__id'),
                supplymodel_id=F('supplyanalysis__id'),
                residual=F('demandanalysis__demand') - F('supplyanalysis__supply'),
                residualgraphic=(F('demandanalysis__demand') - F('supplyanalysis__supply')) / (Area('geom') * 1000000),
                geom_as_geojson=AsGeoJSON(Transform('geom', 4326))
            )
            .values('ext_id', 'study_id', 'demandmodel_id', 'supplymodel_id', 'demand', 'supply',
                    'residual', 'residualgraphic', 'geom_as_geojson')
        )

        # Here we create NDJSON by simply joining individual JSON (GeoJSON) Lines.
        geojson_ndjson_str = "\n".join([
            json.dumps({
                "type": "Feature",
                "properties": {
                    "ext_id": row['ext_id'],
                    "study_id": row['study_id'],
                    "demandmodel_id": row['demandmodel_id'],
                    "supplymodel_id": row['supplymodel_id'],
                    "demand": row['demand'],
                    "supply": row['supply'],
                    "residual": row['residual'],
                    "residualgraphic": row['residualgraphic']
                },
                "geometry": json.loads(row['geom_as_geojson'])  # Convert GeoJSON from string
            })
            for row in rows
        ]).encode('utf-8')

        s = Source('bounddata_' + str(self.id), 'propsavant', os.getenv('MB_KEY'))
        s.upload('bounddata_' + str(self.id), geojson_ndjson_str)
        t = Tileset('bounddata_' + str(self.id), 'propsavant', os.getenv('MB_KEY'))

        recipe = {
            "version": 1,
            "layers": {
                "my_new_layer": {
                    "source": "mapbox://tileset-source/propsavant/bounddata_" + str(self.id),
                    "minzoom": 10,
                    "maxzoom": 15
                }
            }
        }

        name = 'bounddata_' + str(self.id)

        t.create(recipe, name)
        t.publish()

