# Database Initialization

This project includes a management command to initialize the database with baseline data.

## Quick Start

After setting up Docker and running migrations, initialize the database:

```bash
# Run migrations (if not already done)
docker compose exec web python manage.py migrate

# Initialize baseline data
docker compose exec web python manage.py init_data

# Or include downloading DA boundaries (recommended for Canadian studies)
docker compose exec web python manage.py init_data --download-boundaries
```

Or use the convenience script:

```bash
docker compose exec web bash scripts/init_db.sh
```

## What Gets Initialized

The `init_data` command creates:

1. **PerimSets and Perims**
   - Creates an "ISO" PerimSet for isochrones
   - Creates perimeters for 5, 10, 15, 20, and 30 minutes

2. **DemandModels**
   - Creates "CSSVS" demand model (used by the application)

3. **SupplyModels**
   - Creates "CSSVS10" supply model
   - Sets up ModelWeights with default distribution:
     - 5min: 0.4
     - 10min: 0.3
     - 15min: 0.2
     - 20min: 0.1

4. **Customers**
   - Creates a "Default Customer" for testing

## Options

### Download DA Boundaries

Automatically download and import Canadian census boundaries from Statistics Canada:

```bash
docker compose exec web python manage.py init_data --download-boundaries
```

**Note:** 
- This downloads a ~200MB file and may take several minutes
- Requires internet connection
- Only downloads if boundaries don't already exist (use `--force` to re-download)
- The file is downloaded temporarily and extracted automatically

### Force Re-initialization

To delete existing data and re-initialize:

```bash
docker compose exec web python manage.py init_data --force
```

**Warning:** This will delete all existing PerimSets, Perims, DemandModels, SupplyModels, and Customers!

To force re-download boundaries:

```bash
docker compose exec web python manage.py init_data --force --download-boundaries
```

## Customization

Edit `main/management/commands/init_data.py` to:
- Add more initial data
- Change default values
- Add Characteristics data (when you have the source)
- Add sample Stores
- Add more Customers

## Automatic Initialization

To automatically run initialization when the container starts, you can:

1. **Modify docker-compose.yml** to add an entrypoint script
2. **Use a startup script** that checks if data exists before initializing
3. **Run manually** when needed (recommended for development)

## Next Steps

After initialization:
1. Create a superuser: `docker compose exec web python manage.py createsuperuser`
2. Access admin: http://localhost:8000/admin
3. Load census boundary data (DABoundary) if needed
4. Load Characteristics data from Statistics Canada
5. Import Store data via CSV (see `Store.importCSV()` method)
