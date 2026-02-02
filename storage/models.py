from django.contrib.gis.db import models
from django.contrib.gis.db.models import Collect
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon, Point
from django.contrib.gis.db.models.functions import Transform, Area, AsGeoJSON, Centroid, Union
from django.db.models import F, Q, Sum, Prefetch
import requests, json, os
import time
from main.models import Boundary, BoundaryData, Study
from mapbox.utils import Source, Tileset
from cacensus.models import DABoundary
from collections import defaultdict
import pandas as pd
import csv

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
    geom = models.PointField(srid=3857, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.CharField(max_length=50, null=True, blank=True)
    yearbuilt = models.IntegerField(null=True, blank=True)
    totalsqft = models.IntegerField(null=True, blank=True)
    rentablesqft = models.IntegerField(null=True, blank=True)
    storetype = models.CharField(max_length=50, null=True, blank=True)
    companytype = models.CharField(max_length=50, null=True, blank=True)



    def __str__(self):
        return self.storename

    def updateStorePerims(self):
        #delete old perims
        StorePerim.objects.filter(store=self).delete()

        key = os.getenv('MB_KEY')
        if not key:
            raise ValueError(
                "MB_KEY environment variable is not set. "
                "Isochrone generation requires a Mapbox API key. "
                "Please set MB_KEY in your docker-compose.yml environment section. "
                "Get your API key from https://account.mapbox.com/access-tokens/"
            )

        url = 'https://api.mapbox.com/isochrone/v1/'
        profile = 'mapbox/driving'
        coord = self.geom.transform(4326, clone=True)
        polygons = True
        #denoise = float(1.0)

        # get the times we need for models
        times = Perim.objects.filter(perimset__name='ISO').order_by('name')
        if not times.exists():
            raise ValueError(
                "No Perim objects found with perimset name 'ISO'. "
                "Please initialize perimeter data using the init_data management command: "
                "python manage.py init_data"
            )

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
                
                # Retry logic with exponential backoff for rate limiting
                max_retries = 5
                retry_delay = 1  # Start with 1 second
                response = None
                
                for attempt in range(max_retries):
                    response = requests.get(api_url)
                    
                    # If successful, break out of retry loop
                    if response.status_code == 200:
                        break
                    
                    # If rate limited (429), wait and retry
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            time.sleep(wait_time)
                            continue
                        else:
                            # Last attempt failed
                            error_msg = "Rate limit exceeded. Please wait and try again later."
                            try:
                                error_data = response.json()
                                if 'message' in error_data:
                                    error_msg = error_data['message']
                            except:
                                pass
                            raise ValueError(
                                f"Failed to generate isochrones for store '{self.storename}'. {error_msg}"
                            )
                    
                    # For other HTTP errors, raise immediately
                    error_msg = f"Mapbox API returned status {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_msg += f": {error_data['message']}"
                    except:
                        error_msg += f": {response.text[:200]}"
                    raise ValueError(
                        f"Failed to generate isochrones for store '{self.storename}'. {error_msg}"
                    )
                
                j = response.json()
                
                # Check for API errors in response
                if 'error' in j:
                    raise ValueError(
                        f"Mapbox API error for store '{self.storename}': {j.get('message', j['error'])}"
                    )
                
                # Check for features in response
                if 'features' not in j:
                    raise ValueError(
                        f"Unexpected response format from Mapbox API for store '{self.storename}'. "
                        f"Expected 'features' key. Response: {j}"
                    )

                isos = isos + j['features']
                timestr = ''
                
                # Small delay between requests to avoid hitting rate limits
                if i < len(times):
                    time.sleep(0.5)

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
        # check if this instance already exists in the database
        if Store.objects.filter(pk=self.pk).exists():
            # update perims if sqft or geom change
            if self.geom != self._original_geom:
                super().save(*args, **kwargs)
                self.updateStorePerims()
            elif self.rentablesqft != self._original_rentablesqft:
                super().save(*args, **kwargs)
                self.updateStorePerims()
            else:
                super().save(*args, **kwargs)

        else:
            super().save(*args, **kwargs)
            self.updateStorePerims()







        # After saving, update the original geometry so that subsequent saves won't trigger updateStorePerims
        # unless the geometry is changed again.
        #self._original_geom = self.geom

    @staticmethod
    def importCSV(file):
        with open(file, 'r') as f:
            f = open(file, 'r')
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                data = dict(zip(header, row))

                longitude = data.get('Longitude', None)
                latitude = data.get('Latitude', None)
                if longitude is not None and latitude is not None:
                    try:
                        longitude = float(longitude)
                        latitude = float(latitude)
                        geom = Transform(Point(longitude, latitude, srid=4326), 3857)
                    except ValueError:
                        raise ValueError("Longitude and Latitude must be numeric")
                else:
                    raise KeyError("Both Longitude and Latitude needed")

                yearbuilt = data.get('Year Built')
                if not str(yearbuilt).isdigit():
                    yearbuilt = None

                s = Store(masterid=data['\ufeffMasterID'],
                          storeid=data['StoreID'],
                          storename=data['StoreName'],
                          url=data['url'],
                          address=data['Address'],
                          city=data['City'],
                          state=data['State'],
                          zipcode=data['ZipCode'],
                          geom=Point(longitude, latitude, srid=4326),
                          phone=data['Store Phone Number'],
                          email=data['Store Email Address'],
                          yearbuilt=yearbuilt,
                          totalsqft=int(data['Total Square Footage'].replace(',', '')),
                          rentablesqft=int(data['Total Rent-able Square Footage'].replace(',', '')),
                          storetype=data['Storage Type'],
                          companytype=data['CompanyType']
                          )
                s.geom.transform(3857)
                try:
                    s.save()
                except ValueError as e:
                    store_name = data.get('StoreName', 'Unknown')
                    store_id = data.get('StoreID', 'Unknown')
                    raise ValueError(
                        f"Failed to save store '{store_name}' (ID: {store_id}): {str(e)}\n"
                        "Store was not saved. Please fix the issue and try again."
                    ) from e


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

class BoundaryPerim(models.Model):
    # contains the perimieter geometries centered on each boundary
    # created by Boundary.updateStorePerims()
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
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

        weights = ModelWeights.objects.filter(supplymodel=self)
        stores = Store.objects.filter(geom__within=study.geom)
        for s in stores:

            # Get Perim IDs for the given SupplyModel based on ModelWeights
            perim_ids = ModelWeights.objects.filter(supplymodel=self).values_list('perim_id', flat=True)

            # Filter StorePerim objects based on which store we're looking at and
            # whether their perim's id is one of the ones associated with the given SupplyModel
            storeperims = StorePerim.objects.filter(store=s, perim_id__in=perim_ids).order_by('perim__name')

            #create a null perimeter
            boundary = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
            previous_p = StorePerim(store=s,
                                    perim=Perim(perimset=self.perimset, name='blank'),
                                    geom=MultiPolygon(Polygon(boundary))
                                    )
            spb = []
            for p in storeperims:
                weight = weights.get(perim=p.perim_id).weight
                bounds = (Boundary.objects.filter(
                    study=study).filter(
                    geom__intersects=p.geom).filter(~Q(
                    geom__intersects=previous_p.geom)).prefetch_related(
                        Prefetch(
                            'demandanalysis_set',
                            queryset=DemandAnalysis.objects.filter(study=study).filter(demandmodel=dm),
                            to_attr='filtered_demand_analysis'
                        )))
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
        # the only method we use currently, 'CSSVS', is hard-coded here
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

class StorageBoundary(Boundary):
    # extends the Boundary model with storage specific methods
    class Meta:
        proxy = True

    def updatePerims(self):
        #delete old perims
        BoundaryPerim.objects.filter(boundary=self).delete()

        key = os.getenv('MB_KEY')
        url = 'https://api.mapbox.com/isochrone/v1/'
        profile = 'mapbox/driving'
        result = StorageBoundary.objects.filter(id=self.id).annotate(centroid=Centroid(Transform('geom', 4326))).first()
        coord = result.centroid


        # get the times we need for models
        times = Perim.objects.filter(perimset__name='ISO').order_by('name')
        timestr = ''
        isos = []
        for i, t in enumerate(times, start=1):
            timestr = timestr + ',' + str(t.name)

            # only permits 4 isos per request
            if i % 4 == 0 or i == len(times):
                timestr = timestr[1:]
                api_url = url \
                          + profile + '/'\
                          + str(coord.x) + ',' + str(coord.y) + '?' \
                          + 'contours_minutes=' + timestr \
                          + '&polygons=true&access_token=' \
                          + key
                
                # Retry logic with exponential backoff for rate limiting
                max_retries = 5
                retry_delay = 1  # Start with 1 second
                response = None
                
                for attempt in range(max_retries):
                    response = requests.get(api_url)
                    
                    # If successful, break out of retry loop
                    if response.status_code == 200:
                        break
                    
                    # If rate limited (429), wait and retry
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            time.sleep(wait_time)
                            continue
                        else:
                            # Last attempt failed
                            error_msg = "Rate limit exceeded. Please wait and try again later."
                            try:
                                error_data = response.json()
                                if 'message' in error_data:
                                    error_msg = error_data['message']
                            except:
                                pass
                            raise ValueError(
                                f"Failed to generate isochrones for boundary '{self.name}'. {error_msg}"
                            )
                    
                    # For other HTTP errors, raise immediately
                    error_msg = f"Mapbox API returned status {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_msg += f": {error_data['message']}"
                    except:
                        error_msg += f": {response.text[:200]}"
                    raise ValueError(
                        f"Failed to generate isochrones for boundary '{self.name}'. {error_msg}"
                    )
                
                j = response.json()
                
                # Check for API errors in response
                if 'error' in j:
                    raise ValueError(
                        f"Mapbox API error for boundary '{self.name}': {j.get('message', j['error'])}"
                    )
                
                # Check for features in response
                if 'features' not in j:
                    raise ValueError(
                        f"Unexpected response format from Mapbox API for boundary '{self.name}'. "
                        f"Expected 'features' key. Response: {j}"
                    )

                isos = isos + j['features']
                timestr = ''
                
                # Small delay between requests to avoid hitting rate limits
                if i < len(times):
                    time.sleep(0.5)

        for i, iso in enumerate(isos):
            g = GEOSGeometry(json.dumps(iso['geometry']))
            m = MultiPolygon(g)
            m.srid = g.srid
            m.transform(3857)

            BoundaryPerim(boundary=self, perim=times.get(name=iso['properties']['contour']), geom=m).save()




class StorageStudy(Study):

    #extends the Study model with storage specific methods
    class Meta:
        proxy = True

    def addPerims(self):
        #TODO: do we add this to a save() functin?
        p = StorageBoundary.objects.filter(study=self)
        for i in p:
            if len(i.boundaryperim_set.all()) == 0:
                i.updatePerims()


    def addBoundaries(self):
        # The Study geometry contains several Boundaries, however, our analysis also requires the Boundaries that are
        # contained by the StorePerims and BoundaryPerims.  This function adds those boundaries.

        # TODO: add other boundaries extending from the perimeters from the existing boundaries and other Stores
        stores_within_geometry = Store.objects.filter(geom__within=self.geom)
        boundarys_within_geometry = Boundary.objects.filter(geom__within=self.geom)
        s_unioned_isos = (StorePerim.objects
                            .filter(store__in=stores_within_geometry)
                            .aggregate(unioned_geoms=Collect('geom')
                            )['unioned_geoms']
                            )
        b_unioned_isos = (BoundaryPerim.objects
                            .filter(boundary__in=boundarys_within_geometry)
                            .aggregate(unioned_geoms=Collect('geom')
                            )['unioned_geoms']
                            )
        collected_geometry = Union(s_unioned_isos.unary_union, b_unioned_isos.unary_union)

        # exclude boundaries that are already in the Boundary table
        ext_ids_to_exclude = Boundary.objects.all().values_list('ext_id', flat=True)
        bounds = (DABoundary.objects
                .filter(geom__intersects=Transform(collected_geometry, 3347))
                .exclude(dauid__in=ext_ids_to_exclude)
                .annotate(transformed_geom=Transform('geom', 3857))
                )

        for b in bounds:
            sb = StorageBoundary(study=self, ext_id=b.dauid, geom=b.transformed_geom)
            sb.save()
            sb.updatePerims()



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
        sm = SupplyModel.objects.get(id=2)
        sm.calcSPBSupply(self)


        # Assuming StorePerimBoundary is populated, Get boundary and supplymodel pairs from StorePerimBoundary
        # firsst retrieve the boundaries associates with the study
        study_boundaries = Boundary.objects.filter(study=self).values_list('id', flat=True)
        # then get the distinct boundary/supplymodel combinations
        queryset = StorePerimBoundary.objects.filter(
            boundary__in=study_boundaries).values('boundary', 'supplymodel').distinct('boundary', 'supplymodel')

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
        SupplyAnalysis.objects.filter(study=self).delete()
        SupplyAnalysis.objects.bulk_create(supply_analysis_list)

    def uploadDSAnalysis(self, filename='output.geojson'):
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
                    "maxzoom": 13
                }
            }
        }

        name = 'bounddata_' + str(self.id)

        t.create(recipe, name)
        t.publish()

    def calcAnalysis(self):
        # calculates the BoundaryAnalysis instances for the study
        insert = []
        #first gather all boundaries in the study and prefetch the related perims
        allboundaries = (
            StorageBoundary.objects
            .prefetch_related('boundaryperim_set')
            .filter(study_id=self.id,
                    demandanalysis__study_id=F('study_id'),
                    supplyanalysis__study_id=F('study_id'),
                    )
            .annotate(
                demand=F('demandanalysis__demand'),
                supply=F('supplyanalysis__supply'),
                demandmodel_id=F('demandanalysis__id'),
                supplymodel_id=F('supplyanalysis__id'),
                area=Area('geom'),
                transformed_geom=Transform('geom', 4326)
                )
            )

        studyboundaries = allboundaries.filter(geom__intersects=self.geom)

        weights = ModelWeights.objects.filter(supplymodel__name='CSSVS10')


        for b in studyboundaries:

            #retrieve the perims for this Boundary
            perims = b.boundaryperim_set.filter(perim__in=weights.values_list('perim', flat=True)).order_by('perim__name')

            # create a null perimeter
            poly = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
            previous_p = BoundaryPerim(boundary=b,
                                    perim=Perim(perimset=PerimSet.objects.get(id=1), name='blank'),
                                    geom=MultiPolygon(Polygon(poly))
                                    )

            stats = []
            for i, p in enumerate(perims):

                weight = weights.get(perim=p.perim).weight
                # find the boundaries that are intersected by p, but not intersected by previous_p
                pstats = (allboundaries
                            .filter(geom__intersects=p.geom)
                            .filter(~Q(geom__intersects=previous_p.geom))
                            .filter(
                                demandanalysis__study_id=F('study_id'),
                                supplyanalysis__study_id=F('study_id')
                            ).values(
                                'study_id', 'demandanalysis__demandmodel_id', 'supplyanalysis__supplymodel_id'
                            ).annotate(
                                demand=Sum('demandanalysis__demand') * weight,
                                supply=Sum('supplyanalysis__supply') * weight
                            )
                )

                stats = stats + list(pstats)

                previous_p = p

            # use a pandas dataframe to sum and group by study, demandmodel & supplymodel
            statsdf = pd.DataFrame(stats)
            grouped = statsdf.groupby(['study_id', 'demandanalysis__demandmodel_id', 'supplyanalysis__supplymodel_id'])[
                ['demand', 'supply']].sum().reset_index()
            statsagg = grouped.to_dict(orient='records')


            for s in statsagg:
                insert.append(BoundaryAnalysis(
                    boundary = b,
                    demandmodel_id = s['demandanalysis__demandmodel_id'],
                    supplymodel_id = s['supplyanalysis__supplymodel_id'],
                    study_id = s['study_id'],
                    demand = s['demand'],
                    supply = s['supply'],
                    residual = s['demand'] - s['supply'],
                    residualgraphic = (s['demand'] - s['supply']) / b.area.sq_m,
                    geom = b.transformed_geom
                    )
                )
        BoundaryAnalysis.objects.filter(study=self).delete()
        BoundaryAnalysis.objects.bulk_create(insert)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def uploadBAnalysis(self, demandmodel, supplymodel):
        # This uploads the Study Analysis to mapbox

        codestring = ('BA'
                      + '_s' + str(self.id)
                      + '_dm' + str(demandmodel.id)
                      + '_sm' + str(supplymodel.id)
                      )

        rows = (
            BoundaryAnalysis.objects
            .filter(study_id=self.id,
                    demandmodel=demandmodel,
                    supplymodel=supplymodel)
            .annotate(
                geom_as_geojson=AsGeoJSON('geom')
            )
            .values('boundary_id', 'study_id', 'demandmodel_id', 'supplymodel_id', 'demand', 'supply',
                    'residual', 'residualgraphic', 'geom_as_geojson')
        )




        geojson_ndjson_str = "\n".join([
            json.dumps({
                "type": "Feature",
                "properties": {
                    "boundary_id": row['boundary_id'],
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




        s = Source(codestring, 'propsavant', os.getenv('MB_KEY'))
        s.upload(codestring, geojson_ndjson_str)
        t = Tileset(codestring, 'propsavant', os.getenv('MB_KEY'))

        recipe = {
            "version": 1,
            "layers": {
                codestring: {
                    "source": "mapbox://tileset-source/propsavant/" + codestring,
                    "minzoom": 10,
                    "maxzoom": 13
                }
            }
        }



        t.create(recipe, codestring)
        t.publish()

    def uploadStores(self):
        # This uploads the Study Analysis to mapbox

        codestring = ('ST'
                      + '_s' + str(self.id)
                      )

        rows = (
            Store.objects
            .filter(geom__intersects=self.geom)
            .annotate(
                geom_as_geojson=AsGeoJSON(Transform('geom', 4326))
            )
            .values('masterid', 'storeid', 'storename', 'url', 'totalsqft', 'rentablesqft', 'geom_as_geojson')
        )




        geojson_ndjson_str = "\n".join([
            json.dumps({
                "type": "Feature",
                "properties": {
                    "masterid": row['masterid'],
                    "storeid": row['storeid'],
                    "storename": row['storename'],
                    "url": row['url'],
                    "totalsqft": row['totalsqft'],
                    "rentablesqft": row['rentablesqft']
                },
                "geometry": json.loads(row['geom_as_geojson'])  # Convert GeoJSON from string
            })
            for row in rows
        ]).encode('utf-8')

        s = Source(codestring, 'propsavant', os.getenv('MB_KEY'))
        s.upload(codestring, geojson_ndjson_str)
        t = Tileset(codestring, 'propsavant', os.getenv('MB_KEY'))

        recipe = {
            "version": 1,
            "layers": {
                "stores": {
                    "source": "mapbox://tileset-source/propsavant/" + codestring,
                    "minzoom": 10,
                    "maxzoom": 13
                }
            }
        }

        t.create(recipe, codestring)
        t.publish()


    def save(self, *args, **kwargs):
        # check if this instance already exists in the database
        if StorageBoundary.objects.filter(pk=self.pk).exists():
            # update perims if geom changes
            if self.geom != self._original_geom:
                super().save(*args, **kwargs)
                self.addPerims()
            else:
                super().save(*args, **kwargs)

        else:
            super().save(*args, **kwargs)
            self.addPerims()



class BoundaryAnalysis(models.Model):
    boundary = models.ForeignKey(Boundary, on_delete=models.CASCADE)
    demandmodel = models.ForeignKey(DemandModel, on_delete=models.CASCADE)
    supplymodel = models.ForeignKey(SupplyModel, on_delete=models.CASCADE)
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    demand = models.FloatField()
    supply = models.FloatField()
    residual = models.FloatField()
    residualgraphic = models.FloatField()
    geom = models.MultiPolygonField(srid=4326)


