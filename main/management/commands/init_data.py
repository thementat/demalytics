"""
Management command to initialize the database with baseline data.

Usage:
    python manage.py init_data
"""
from django.core.management.base import BaseCommand
from main.models import Characteristic, Customer
from storage.models import PerimSet, Perim, DemandModel, SupplyModel, ModelWeights


class Command(BaseCommand):
    help = 'Initialize database with baseline data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-initialization (delete existing data)',
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
