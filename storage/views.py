import json
import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.contrib.gis.db.models.functions import Transform
from main.models import Customer, Characteristic
from .models import StorageStudy, DemandModel, SupplyModel, BoundaryAnalysis, Store


def index(request):
    """Render the main start page."""
    return render(request, 'index.html')


@require_http_methods(["GET"])
def get_config(request):
    """Return configuration including MapBox public token."""
    # MB_PUBLIC_KEY is for frontend map display (must start with pk.)
    # MB_KEY is the secret key for server-side API calls (starts with sk.)
    mapbox_token = os.getenv('MB_PUBLIC_KEY', '')

    return JsonResponse({
        'mapbox_token': mapbox_token,
    })


@require_http_methods(["GET"])
def customers_list(request):
    """Return list of all customers."""
    customers = Customer.objects.all().values('id', 'name')
    return JsonResponse({'customers': list(customers)})


@require_http_methods(["GET"])
def characteristics_list(request):
    """Return list of available characteristics for analysis."""
    # Get the characteristics used by the CSSVS demand model
    # These are the default characteristics for storage analysis
    cssvs_characteristic_ids = [1, 113, 42, 43, 44, 45, 46, 47, 48, 49]

    characteristics = Characteristic.objects.filter(
        id__in=cssvs_characteristic_ids
    ).values('id', 'name', 'country')

    return JsonResponse({'characteristics': list(characteristics)})


@require_http_methods(["GET"])
def demand_models_list(request):
    """Return list of available demand models."""
    models = DemandModel.objects.all().values('id', 'name')
    return JsonResponse({'demand_models': list(models)})


@require_http_methods(["GET"])
def supply_models_list(request):
    """Return list of available supply models."""
    models = SupplyModel.objects.all().values('id', 'name')
    return JsonResponse({'supply_models': list(models)})


@csrf_exempt
@require_http_methods(["POST"])
def create_study(request):
    """Create a new study from the provided geometry."""
    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ['customer_id', 'name', 'country', 'geometry']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

        # Get customer
        try:
            customer = Customer.objects.get(id=data['customer_id'])
        except Customer.DoesNotExist:
            return JsonResponse({'error': 'Customer not found'}, status=404)

        # Parse geometry (GeoJSON format from MapBox Draw)
        geojson = data['geometry']

        # Handle both Feature and raw geometry
        if geojson.get('type') == 'Feature':
            geom_data = geojson.get('geometry')
        else:
            geom_data = geojson

        # Create GEOS geometry from GeoJSON
        geom = GEOSGeometry(json.dumps(geom_data))

        # Ensure it's a MultiPolygon
        if geom.geom_type == 'Polygon':
            geom = MultiPolygon(geom)
        elif geom.geom_type != 'MultiPolygon':
            return JsonResponse({'error': 'Geometry must be a Polygon or MultiPolygon'}, status=400)

        # Set SRID (GeoJSON is always WGS84 / 4326)
        geom.srid = 4326

        # Transform to Web Mercator (SRID 3857) as expected by the model
        geom.transform(3857)

        # Create the study
        study = StorageStudy(
            customer=customer,
            name=data['name'],
            description=data.get('description', ''),
            country=data['country'],
            type='ST',  # Storage study type
            geom=geom
        )
        study.save()

        # Add characteristics (use CSSVS defaults)
        cssvs_characteristic_ids = [1, 113, 42, 43, 44, 45, 46, 47, 48, 49]
        characteristics = Characteristic.objects.filter(id__in=cssvs_characteristic_ids)
        study.characteristics.set(characteristics)

        return JsonResponse({
            'success': True,
            'study_id': study.id,
            'name': study.name,
            'message': 'Study created successfully. Boundaries have been populated.'
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def process_study(request, study_id):
    """Run processStudy() to calculate demand and supply."""
    try:
        # Get the study
        try:
            study = StorageStudy.objects.get(id=study_id)
        except StorageStudy.DoesNotExist:
            return JsonResponse({'error': 'Study not found'}, status=404)

        # Run the analysis pipeline
        # This includes: addPerims, addBoundaries, popdata, calcDemand, calcSPBSupply
        study.processStudy()

        return JsonResponse({
            'success': True,
            'study_id': study.id,
            'message': 'Study processing complete. Demand and supply calculated.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def run_analysis(request, study_id):
    """Run calcAnalysis() to compute final results (no Mapbox upload)."""
    try:
        # Get the study
        try:
            study = StorageStudy.objects.get(id=study_id)
        except StorageStudy.DoesNotExist:
            return JsonResponse({'error': 'Study not found'}, status=404)

        # Get demand and supply models (use defaults)
        try:
            demand_model = DemandModel.objects.get(name='CSSVS')
        except DemandModel.DoesNotExist:
            return JsonResponse({
                'error': 'CSSVS demand model not found. Please run init_data command first.'
            }, status=400)

        try:
            supply_model = SupplyModel.objects.get(name='CSSVS10')
        except SupplyModel.DoesNotExist:
            return JsonResponse({
                'error': 'CSSVS10 supply model not found. Please run init_data command first.'
            }, status=400)

        # Calculate final analysis (stores results in BoundaryAnalysis table)
        study.calcAnalysis()

        return JsonResponse({
            'success': True,
            'study_id': study.id,
            'message': 'Analysis complete. Use the GeoJSON endpoints to view results.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def study_boundaries_geojson(request, study_id):
    """Return study boundary analysis as GeoJSON for direct map rendering."""
    try:
        # Get the study
        try:
            study = StorageStudy.objects.get(id=study_id)
        except StorageStudy.DoesNotExist:
            return JsonResponse({'error': 'Study not found'}, status=404)

        # Get boundary analysis data (already has geom in SRID 4326)
        boundaries = BoundaryAnalysis.objects.filter(study=study)

        if not boundaries.exists():
            return JsonResponse({'error': 'No analysis data found. Run analysis first.'}, status=400)

        # Calculate max absolute residual for color scaling
        residuals = [b.residual for b in boundaries]
        max_residual = max(abs(r) for r in residuals) if residuals else 1

        # Build GeoJSON FeatureCollection
        features = []
        for b in boundaries:
            # Convert geometry to GeoJSON
            geom_json = json.loads(b.geom.geojson)

            feature = {
                'type': 'Feature',
                'geometry': geom_json,
                'properties': {
                    'boundary_id': b.boundary_id,
                    'demand': b.demand,
                    'supply': b.supply,
                    'residual': b.residual,
                    'residualgraphic': b.residualgraphic,
                }
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'study_id': study.id,
                'study_name': study.name,
                'max_residual': max_residual,
                'feature_count': len(features)
            }
        }

        return JsonResponse(geojson)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def study_stores_geojson(request, study_id):
    """Return stores within study area as GeoJSON for direct map rendering."""
    try:
        # Get the study
        try:
            study = StorageStudy.objects.get(id=study_id)
        except StorageStudy.DoesNotExist:
            return JsonResponse({'error': 'Study not found'}, status=404)

        # Get stores within study geometry, transform to WGS84
        stores = Store.objects.filter(
            geom__intersects=study.geom
        ).annotate(
            geom_4326=Transform('geom', 4326)
        )

        if not stores.exists():
            # Return empty FeatureCollection if no stores
            return JsonResponse({
                'type': 'FeatureCollection',
                'features': [],
                'metadata': {
                    'study_id': study.id,
                    'study_name': study.name,
                    'feature_count': 0
                }
            })

        # Calculate min/max rentablesqft for circle sizing
        sqft_values = [s.rentablesqft for s in stores if s.rentablesqft]
        min_sqft = min(sqft_values) if sqft_values else 0
        max_sqft = max(sqft_values) if sqft_values else 1

        # Build GeoJSON FeatureCollection
        features = []
        for s in stores:
            # Convert geometry to GeoJSON
            geom_json = json.loads(s.geom_4326.geojson)

            feature = {
                'type': 'Feature',
                'geometry': geom_json,
                'properties': {
                    'masterid': s.masterid,
                    'storeid': s.storeid,
                    'storename': s.storename,
                    'address': s.address,
                    'city': s.city,
                    'rentablesqft': s.rentablesqft,
                    'totalsqft': s.totalsqft,
                    'storetype': s.storetype,
                }
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'study_id': study.id,
                'study_name': study.name,
                'min_sqft': min_sqft,
                'max_sqft': max_sqft,
                'feature_count': len(features)
            }
        }

        return JsonResponse(geojson)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
