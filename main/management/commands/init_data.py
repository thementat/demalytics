"""
Management command to initialize the database with baseline data.

Usage:
    python manage.py init_data
    python manage.py init_data --download-boundaries
"""
from django.core.management.base import BaseCommand
from main.models import Characteristic, Customer
from storage.models import PerimSet, Perim, DemandModel, SupplyModel, ModelWeights
import os
import tempfile
import zipfile
import requests
from pathlib import Path


class Command(BaseCommand):
    help = 'Initialize database with baseline data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-initialization (delete existing data)',
        )
        parser.add_argument(
            '--download-boundaries',
            action='store_true',
            help='Download and import DA boundaries from Statistics Canada',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('Starting database initialization...'))
        
        # Check if migrations have been run
        from django.db import connection
        from django.core.management import call_command
        
        try:
            # Try to access a table to see if migrations are needed
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM storage_perimset LIMIT 1")
        except Exception:
            self.stdout.write(self.style.WARNING(
                'Database tables not found. Running migrations first...'
            ))
            call_command('migrate', verbosity=0)
            self.stdout.write(self.style.SUCCESS('Migrations complete.'))
        
        # Initialize PerimSet and Perims (for isochrones)
        self.init_perimsets(force)
        
        # Initialize DemandModel
        self.init_demand_models(force)
        
        # Initialize SupplyModel
        self.init_supply_models(force)
        
        # Initialize sample Customer
        self.init_customers(force)
        
        # Download and import DA boundaries if requested
        if options.get('download_boundaries'):
            self.download_and_import_boundaries(force)
        
        # Initialize Characteristics (if you have the data)
        # self.init_characteristics(force)
        
        self.stdout.write(self.style.SUCCESS('Database initialization complete!'))

    def init_perimsets(self, force=False):
        """Initialize PerimSet and Perim data for isochrones"""
        self.stdout.write('  Initializing PerimSets and Perims...')
        
        if force:
            Perim.objects.all().delete()
            PerimSet.objects.all().delete()
        
        # Create ISO PerimSet (for isochrones)
        iso_perimset, created = PerimSet.objects.get_or_create(name='ISO')
        if created:
            self.stdout.write(f'    Created PerimSet: {iso_perimset.name}')
        
        # Create standard isochrone perimeters (5, 10, 15, 20, 30 minutes)
        iso_times = [5, 10, 15, 20, 30]
        for time in iso_times:
            perim, created = Perim.objects.get_or_create(
                perimset=iso_perimset,
                name=str(time),
                defaults={'perimset': iso_perimset}
            )
            if created:
                self.stdout.write(f'    Created Perim: {time} minutes')
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ PerimSets initialized'))

    def init_demand_models(self, force=False):
        """Initialize DemandModel (CSSVS)"""
        self.stdout.write('  Initializing DemandModels...')
        
        if force:
            DemandModel.objects.all().delete()
        
        # Create CSSVS demand model (referenced in code)
        cssvs, created = DemandModel.objects.get_or_create(
            name='CSSVS',
            defaults={'name': 'CSSVS'}
        )
        if created:
            self.stdout.write(f'    Created DemandModel: {cssvs.name}')
        else:
            self.stdout.write(f'    DemandModel already exists: {cssvs.name}')
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ DemandModels initialized'))

    def init_supply_models(self, force=False):
        """Initialize SupplyModel and ModelWeights"""
        self.stdout.write('  Initializing SupplyModels...')
        
        if force:
            ModelWeights.objects.all().delete()
            SupplyModel.objects.all().delete()
        
        # Get ISO PerimSet
        iso_perimset = PerimSet.objects.get(name='ISO')
        
        # Create SupplyModel (id=2 is referenced in code)
        # This appears to be "CSSVS10" based on the code
        supply_model, created = SupplyModel.objects.get_or_create(
            name='CSSVS10',
            defaults={
                'name': 'CSSVS10',
                'perimset': iso_perimset
            }
        )
        if created:
            self.stdout.write(f'    Created SupplyModel: {supply_model.name}')
        
        # Get or create perims for weights
        perims = Perim.objects.filter(perimset=iso_perimset, name__in=['5', '10', '15', '20'])
        
        # Create ModelWeights (example weights - adjust as needed)
        # Weight distribution: 5min=0.4, 10min=0.3, 15min=0.2, 20min=0.1
        weights_map = {
            '5': 0.4,
            '10': 0.3,
            '15': 0.2,
            '20': 0.1,
        }
        
        for perim in perims:
            weight_obj, created = ModelWeights.objects.get_or_create(
                supplymodel=supply_model,
                perim=perim,
                defaults={'weight': weights_map.get(perim.name, 0.1)}
            )
            if created:
                self.stdout.write(f'    Created ModelWeight: {perim.name}min = {weight_obj.weight}')
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ SupplyModels initialized'))

    def init_customers(self, force=False):
        """Initialize sample customers"""
        self.stdout.write('  Initializing Customers...')
        
        if force:
            Customer.objects.all().delete()
        
        # Create a default customer
        customer, created = Customer.objects.get_or_create(
            name='Default Customer',
            defaults={'name': 'Default Customer'}
        )
        if created:
            self.stdout.write(f'    Created Customer: {customer.name}')
        else:
            self.stdout.write(f'    Customer already exists: {customer.name}')
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Customers initialized'))

    def init_characteristics(self, force=False):
        """
        Initialize Characteristics data.
        
        Note: This requires the actual characteristics data from Statistics Canada.
        Uncomment and modify this method when you have the data source.
        """
        self.stdout.write('  Initializing Characteristics...')
        
        if force:
            Characteristic.objects.all().delete()
        
        # Example structure - you'll need to load actual data
        # The commented code in models.py shows the structure:
        # data = [{'id': 1, 'name': '...', 'parent': None}, ...]
        
        # For now, create a placeholder
        self.stdout.write(self.style.WARNING(
            '    Characteristics initialization skipped - '
            'implement when you have the data source'
        ))

    def download_and_import_boundaries(self, force=False):
        """Download and import DA boundaries from Statistics Canada"""
        self.stdout.write('  Downloading and importing DA boundaries...')
        
        if force:
            from cacensus.models import DABoundary
            DABoundary.objects.all().delete()
            self.stdout.write('    Deleted existing boundaries')
        
        # Check if boundaries already exist
        from cacensus.models import DABoundary
        if DABoundary.objects.exists():
            self.stdout.write(self.style.WARNING(
                '    DA boundaries already exist. Use --force to re-download.'
            ))
            return
        
        # URL for the DA boundary zip file
        url = 'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lda_000a21a_e.zip'
        
        # Create temporary directory for download and extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'lda_000a21a_e.zip')
            extract_dir = os.path.join(temp_dir, 'extracted')
            
            try:
                # Download the file
                self.stdout.write(f'    Downloading from {url}...')
                self.stdout.write('    This may take several minutes (file is ~200MB)...')
                
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                if downloaded % (10 * 1024 * 1024) == 0:  # Print every 10MB
                                    self.stdout.write(f'    Downloaded: {percent:.1f}%')
                
                self.stdout.write('    Download complete')
                
                # Extract the zip file
                self.stdout.write('    Extracting zip file...')
                os.makedirs(extract_dir, exist_ok=True)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Find the .shp file (search recursively)
                shp_files = list(Path(extract_dir).rglob('*.shp'))
                if not shp_files:
                    # List what we did find for debugging
                    all_files = list(Path(extract_dir).rglob('*'))
                    file_list = [str(f.relative_to(extract_dir)) for f in all_files[:20] if f.is_file()]
                    self.stdout.write(self.style.WARNING(
                        f'    Files found in archive (first 20): {file_list}'
                    ))
                    raise FileNotFoundError('No .shp file found in the zip archive')
                
                # Use the first .shp file found (should be lda_000a21a_e.shp)
                shp_file_path = shp_files[0]
                # LayerMapping expects the full path to the .shp file
                shp_file = str(shp_file_path)
                self.stdout.write(f'    Found shapefile: {shp_file_path.name}')
                self.stdout.write(f'    Using path: {shp_file}')
                
                # Verify the .shp file exists
                if not shp_file_path.exists():
                    raise FileNotFoundError(f'Shapefile not found: {shp_file_path}')
                
                # Import the shapefile
                self.stdout.write('    Importing boundaries into database...')
                self.stdout.write('    This may take several minutes...')
                
                DABoundary.shp_import(shp_file)
                
                count = DABoundary.objects.count()
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Imported {count} DA boundaries'
                ))
                
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(
                    f'    ✗ Download failed: {str(e)}'
                ))
                self.stdout.write(self.style.WARNING(
                    '    You can manually download and import boundaries later'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'    ✗ Import failed: {str(e)}'
                ))
                raise
