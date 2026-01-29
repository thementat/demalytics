# Demalytics User Guide

Complete step-by-step reference for using the Demalytics storage facility market analytics platform.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Loading Data](#loading-data)
3. [Creating a Study](#creating-a-study)
4. [Running Analysis](#running-analysis)
5. [Viewing Results](#viewing-results)
6. [Uploading to Mapbox](#uploading-to-mapbox)
7. [Common Workflows](#common-workflows)

---

## Initial Setup

### 1. Start the Application

```bash
# Start Docker containers
docker compose up -d

# Run migrations (first time only)
docker compose exec web python manage.py migrate

# Initialize baseline data
docker compose exec web python manage.py init_data

# Create a superuser (if not already done)
docker compose exec web python manage.py createsuperuser
```

### 2. Access the Admin Interface

- URL: http://localhost:8000/admin
- Log in with your superuser credentials

### 3. Verify Initial Data

After running `init_data`, you should have:
- ✅ PerimSet: "ISO" with perimeters (5, 10, 15, 20, 30 minutes)
- ✅ DemandModel: "CSSVS"
- ✅ SupplyModel: "CSSVS10" with model weights
- ✅ Customer: "Default Customer"

---

## Loading Data

Before creating a Study, you need to load the required reference data.

### Step 1: Load Census Boundaries (DABoundary)

Census boundaries are required for Canadian studies. You can download and import them automatically.

**Option A: Automatic Download (Recommended)**

The easiest way is to use the initialization command with the `--download-boundaries` flag:

```bash
docker compose exec web python manage.py init_data --download-boundaries
```

This will:
- Download the DA boundary zip file from Statistics Canada (~200MB)
- Extract it automatically
- Import all boundaries into the database
- Take several minutes to complete

**Option B: Manual Import via Django Shell**

If you already have the shapefile downloaded:

```bash
docker compose exec web python manage.py shell
```

```python
from cacensus.models import DABoundary

# Import shapefile (adjust path as needed)
# The shapefile should be accessible from within the container
# You may need to copy it into the container or mount it as a volume
DABoundary.shp_import('/path/to/lda_000b21f_e')
```

**Option C: Using Django Admin**

1. Go to http://localhost:8000/admin
2. Navigate to "Cacensus" → "DA boundaries"
3. Use a custom admin action (if implemented) or use shell method above

**Note:** For manual import, the shapefile path must be accessible from within the Docker container. You may need to:
- Copy the file into the container
- Mount it as a volume in `docker-compose.yml`
- Place it in a shared directory

**Download URL:** https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lda_000b21f_e.zip

### Step 2: Load Characteristics Data

Characteristics define the census metrics used in demand calculations. The CSSVS model uses specific characteristic IDs: [1, 113, 42, 43, 44, 45, 46, 47, 48, 49].

**Using Django Shell:**

```bash
docker compose exec web python manage.py shell
```

```python
from main.models import Characteristic

# Example: Load characteristics from a data source
# The commented code in models.py shows the structure:
# data = [{'id': 1, 'name': 'Total Population', 'parent': None}, ...]

# For each characteristic:
Characteristic.objects.get_or_create(
    id=1,
    defaults={
        'country': 'CA',
        'name': 'Total Population',
        'parent': None
    }
)

# For characteristics with parents:
parent = Characteristic.objects.get(id=1)
Characteristic.objects.get_or_create(
    id=42,
    defaults={
        'country': 'CA',
        'name': 'Single Detached Houses',
        'parent': parent
    }
)

# Continue for all required characteristics (1, 113, 42-49)
```

**Note:** You'll need to obtain the actual characteristics data from Statistics Canada or your data source.

### Step 3: Load Store Data

Stores represent storage facilities in your analysis area.

**Option A: Import from CSV**

The `Store` model has an `importCSV` method. Your CSV should have these columns:
- `MasterID` (with BOM character - `\ufeffMasterID`)
- `StoreID`
- `StoreName`
- `Longitude`
- `Latitude`
- `Address`
- `City`
- `State`
- `ZipCode`
- `Store Phone Number`
- `Store Email Address`
- `Year Built`
- `Total Square Footage`
- `Total Rent-able Square Footage`
- `Storage Type`
- `CompanyType`
- `url`

**Using Django Shell:**

```bash
docker compose exec web python manage.py shell
```

```python
from storage.models import Store

# Import CSV (file must be accessible from container)
Store.importCSV('/path/to/stores.csv')
```

**Option B: Add Stores Manually via Admin**

1. Go to http://localhost:8000/admin
2. Navigate to "Storage" → "Stores"
3. Click "Add Store"
4. Fill in the required fields:
   - Master ID, Store ID, Store Name
   - Location (Longitude/Latitude or use map picker if available)
   - Square footage data
   - Other details

**Important:** After adding/updating stores, isochrones are automatically generated via the `save()` method, which calls `updateStorePerims()`.

---

## Creating a Study

A Study defines the geographic area and parameters for your market analysis.

### Step 1: Create a Study via Django Shell

```bash
docker compose exec web python manage.py shell
```

```python
from main.models import Customer, Characteristic, Study
from storage.models import StorageStudy
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.contrib.gis.geos import Point

# Get or create a customer
customer = Customer.objects.get(name='Default Customer')

# Get the characteristics you need for the CSSVS model
# These are the IDs used by the demand model: [1, 113, 42, 43, 44, 45, 46, 47, 48, 49]
characteristics = Characteristic.objects.filter(id__in=[1, 113, 42, 43, 44, 45, 46, 47, 48, 49])

# Create a study area geometry (example: bounding box around Toronto)
# Coordinates in WGS84 (longitude, latitude)
# You can use a tool like QGIS or geojson.io to create the polygon
min_lon, min_lat = -79.5, 43.6  # Southwest corner
max_lon, max_lat = -79.2, 43.8  # Northeast corner

# Create a simple bounding box polygon
polygon = Polygon((
    (min_lon, min_lat),
    (max_lon, min_lat),
    (max_lon, max_lat),
    (min_lon, max_lat),
    (min_lon, min_lat)
), srid=4326)

# Transform to Web Mercator (SRID 3857) - required by the model
polygon.transform(3857)
multipolygon = MultiPolygon(polygon)

# Create a StorageStudy (extends Study with storage-specific methods)
study = StorageStudy.objects.create(
    customer=customer,
    name='Toronto Market Analysis',
    description='Storage facility market analysis for Toronto area',
    country='CA',  # 'CA' for Canada, 'US' for United States
    type='ST',     # Study type code
    geom=multipolygon
)

# Add characteristics to the study
study.characteristics.set(characteristics)

# Save to trigger boundary population
study.save()

print(f"Study created: {study.name} (ID: {study.id})")
print(f"Boundaries created: {study.boundary_set.count()}")
```

**Note:** When you save a Study, it automatically:
- Finds intersecting census boundaries (DABoundary for CA)
- Creates Boundary objects for those areas
- This happens in the `popboundary()` method

### Step 2: Verify Study Creation

```python
# Check the study
study = StorageStudy.objects.get(name='Toronto Market Analysis')
print(f"Study: {study.name}")
print(f"Country: {study.country}")
print(f"Boundaries: {study.boundary_set.count()}")
print(f"Characteristics: {study.characteristics.count()}")
```

---

## Running Analysis

The analysis calculates demand and supply for each boundary in your study area.

### Step 1: Process the Study

The `processStudy()` method runs the complete analysis pipeline:

```python
from storage.models import StorageStudy

# Get your study
study = StorageStudy.objects.get(name='Toronto Market Analysis')

# Run the complete analysis
# This may take several minutes depending on:
# - Number of boundaries
# - Number of stores
# - Census data API calls
study.processStudy()

print("Analysis complete!")
```

**What `processStudy()` does:**

1. **Adds additional boundaries** (`addBoundaries()`)
   - Finds boundaries within store isochrones
   - Finds boundaries within boundary isochrones
   - Expands the study area to include all relevant boundaries

2. **Populates census data** (`popdata()`)
   - Fetches data from Statistics Canada API
   - Creates BoundaryData records for each boundary/characteristic combination
   - This step requires internet access and may take time

3. **Calculates demand** (`calcDemand()`)
   - Uses the CSSVS demand model
   - Calculates demand for each boundary based on:
     - Housing types (single family, multi-family, etc.)
     - Retail sales proxy
   - Creates DemandAnalysis records

4. **Calculates supply** (`calcSPBSupply()`)
   - Allocates store square footage to boundaries
   - Uses weighted isochrones (5min=0.4, 10min=0.3, etc.)
   - Creates StorePerimBoundary and SupplyAnalysis records

### Step 2: Monitor Progress

For large studies, you can check progress:

```python
# Check how many boundaries have data
study = StorageStudy.objects.get(name='Toronto Market Analysis')
total_boundaries = study.boundary_set.count()
boundaries_with_data = study.boundarydata_set.values('boundary').distinct().count()

print(f"Boundaries: {boundaries_with_data}/{total_boundaries} have census data")

# Check demand analysis
demand_count = study.demandanalysis_set.count()
print(f"Demand analyses: {demand_count}")

# Check supply analysis
supply_count = study.supplyanalysis_set.count()
print(f"Supply analyses: {supply_count}")
```

---

## Viewing Results

### Option 1: Django Admin Interface

1. Go to http://localhost:8000/admin
2. Navigate to "Main" → "Studies"
3. Click on your study
4. View related objects:
   - Boundaries
   - Boundary Data
   - Demand Analysis
   - Supply Analysis

### Option 2: Django Shell Queries

```python
from storage.models import StorageStudy, DemandAnalysis, SupplyAnalysis
from django.db.models import F

study = StorageStudy.objects.get(name='Toronto Market Analysis')

# Get boundaries with demand and supply
results = study.boundary_set.annotate(
    demand=F('demandanalysis__demand'),
    supply=F('supplyanalysis__supply')
).filter(
    demandanalysis__isnull=False,
    supplyanalysis__isnull=False
).values('ext_id', 'demand', 'supply')

# Calculate residual (demand - supply)
for result in results:
    residual = result['demand'] - result['supply']
    print(f"Boundary {result['ext_id']}: Demand={result['demand']:.2f}, "
          f"Supply={result['supply']:.2f}, Residual={residual:.2f}")

# Get summary statistics
from django.db.models import Sum, Avg, Max, Min

summary = study.boundary_set.aggregate(
    total_demand=Sum('demandanalysis__demand'),
    total_supply=Sum('supplyanalysis__supply'),
    avg_demand=Avg('demandanalysis__demand'),
    avg_supply=Avg('supplyanalysis__supply')
)

total_residual = summary['total_demand'] - summary['total_supply']
print(f"\nSummary:")
print(f"Total Demand: {summary['total_demand']:.2f}")
print(f"Total Supply: {summary['total_supply']:.2f}")
print(f"Total Residual: {total_residual:.2f}")
print(f"Average Demand: {summary['avg_demand']:.2f}")
print(f"Average Supply: {summary['avg_supply']:.2f}")
```

### Option 3: Export to GeoJSON

```python
from django.core import serializers

study = StorageStudy.objects.get(name='Toronto Market Analysis')

# Export boundaries with analysis data
boundaries = study.boundary_set.filter(
    demandanalysis__isnull=False,
    supplyanalysis__isnull=False
).select_related()

# Serialize to GeoJSON
geojson = serializers.serialize('geojson', boundaries, 
    fields=('ext_id', 'geom'),
    use_natural_foreign_keys=False)

# Save to file (you'll need to handle this from within container)
# Or copy the output and save locally
print(geojson)
```

---

## Uploading to Mapbox

The system can upload analysis results to Mapbox as tilesets for visualization.

### Prerequisites

1. **Mapbox API Key**: Set the `MB_KEY` environment variable
   - Add to `docker-compose.yml`:
     ```yaml
     environment:
       - MB_KEY=your_mapbox_api_key_here
     ```
   - Or set in `.env` file and load it

2. **Mapbox Account**: You need a Mapbox account with API access

### Step 1: Upload Demand/Supply Analysis

```python
from storage.models import StorageStudy

study = StorageStudy.objects.get(name='Toronto Market Analysis')

# Upload the analysis
# This creates a tileset named 'bounddata_{study_id}'
study.uploadDSAnalysis()

print("Upload complete! Check your Mapbox account.")
```

**What this does:**
- Exports boundaries with demand, supply, and residual values
- Uploads as GeoJSON to Mapbox
- Creates and publishes a tileset
- Tileset name: `bounddata_{study_id}`

### Step 2: Upload Boundary Analysis

For more detailed analysis with weighted perimeters:

```python
from storage.models import StorageStudy, DemandModel, SupplyModel

study = StorageStudy.objects.get(name='Toronto Market Analysis')
demand_model = DemandModel.objects.get(name='CSSVS')
supply_model = SupplyModel.objects.get(name='CSSVS10')

# First, calculate boundary analysis (if not already done)
study.calcAnalysis()

# Then upload
study.uploadBAnalysis(demand_model, supply_model)
```

**Tileset naming:**
- Format: `BA_s{study_id}_dm{demand_model_id}_sm{supply_model_id}`
- Example: `BA_s1_dm1_sm2`

### Step 3: Upload Stores

```python
study = StorageStudy.objects.get(name='Toronto Market Analysis')

# Upload stores within the study area
study.uploadStores()
```

**Tileset name:** `ST_s{study_id}`

### Step 4: Access in Mapbox

1. Log in to your Mapbox account
2. Go to "Tilesets"
3. Find your uploaded tilesets
4. Use them in Mapbox Studio or your mapping application

---

## Common Workflows

### Complete Workflow: New Study from Scratch

```python
# 1. Load prerequisites (if not already done)
from cacensus.models import DABoundary
DABoundary.shp_import('/path/to/boundaries.shp')

from storage.models import Store
Store.importCSV('/path/to/stores.csv')

# 2. Create study
from storage.models import StorageStudy
from main.models import Customer, Characteristic
from django.contrib.gis.geos import MultiPolygon, Polygon

customer = Customer.objects.first()
characteristics = Characteristic.objects.filter(id__in=[1, 113, 42, 43, 44, 45, 46, 47, 48, 49])

# Create geometry (example)
polygon = Polygon((
    (-79.5, 43.6),
    (-79.2, 43.6),
    (-79.2, 43.8),
    (-79.5, 43.8),
    (-79.5, 43.6)
), srid=4326)
polygon.transform(3857)

study = StorageStudy.objects.create(
    customer=customer,
    name='My Market Study',
    country='CA',
    type='ST',
    geom=MultiPolygon(polygon)
)
study.characteristics.set(characteristics)
study.save()

# 3. Run analysis
study.processStudy()

# 4. Upload to Mapbox (optional)
study.uploadDSAnalysis()
study.uploadStores()
```

### Workflow: Update Existing Study

```python
from storage.models import StorageStudy

study = StorageStudy.objects.get(name='My Market Study')

# Update geometry (if needed)
# This will automatically re-populate boundaries
from django.contrib.gis.geos import MultiPolygon, Polygon
new_polygon = Polygon(...)  # Your new geometry
new_polygon.transform(3857)
study.geom = MultiPolygon(new_polygon)
study.save()  # Triggers popboundary()

# Re-run analysis
study.processStudy()
```

### Workflow: Add More Stores

```python
from storage.models import Store

# Import new stores
Store.importCSV('/path/to/new_stores.csv')

# Or add manually
Store.objects.create(
    masterid=12345,
    storeid=1,
    storename='New Store',
    geom=Point(-79.4, 43.7, srid=4326),  # Will be transformed to 3857
    rentablesqft=50000,
    # ... other fields
)

# Re-run analysis for affected studies
study = StorageStudy.objects.get(name='My Market Study')
study.processStudy()
```

---

## Troubleshooting

### Issue: "No boundaries found for study"

**Solution:**
- Ensure DABoundary data is loaded
- Check that your study geometry overlaps with census boundaries
- Verify the country code matches your boundary data ('CA' vs 'US')

### Issue: "Census data not loading"

**Solution:**
- Check internet connection (census API requires external access)
- Verify Characteristics are loaded with correct IDs
- Check Statistics Canada API status
- Review API rate limits

### Issue: "Stores not generating isochrones"

**Solution:**
- Ensure Mapbox API key is set (`MB_KEY` environment variable)
- Check that stores have valid coordinates
- Verify PerimSet and Perims are initialized
- Check Mapbox API quota/limits

### Issue: "Analysis taking too long"

**Solution:**
- Large study areas with many boundaries take time
- Census API calls are rate-limited
- Consider breaking large studies into smaller regions
- Monitor progress using the queries in "Viewing Results"

---

## Tips and Best Practices

1. **Start Small**: Test with a small study area first
2. **Monitor API Limits**: Census and Mapbox APIs have rate limits
3. **Backup Data**: Export important studies before major changes
4. **Use Transactions**: Wrap analysis in database transactions for large operations
5. **Check Logs**: Monitor Docker logs for errors:
   ```bash
   docker compose logs -f web
   ```

---

## Next Steps

- Build a web interface for creating studies visually
- Add data export functionality (CSV, Excel)
- Implement background task processing (Celery) for long-running analyses
- Add user authentication and multi-tenant support
- Create reporting and visualization dashboards

---

## Additional Resources

- **Django Admin**: http://localhost:8000/admin
- **Django Shell**: `docker compose exec web python manage.py shell`
- **Database Access**: `docker compose exec db psql -U postgres -d demalytics`
- **Container Logs**: `docker compose logs -f web`
