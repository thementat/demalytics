import googlemaps
import json
from django.shortcuts import render
from django.conf import settings

# Create your views here.
def geocode(request):
    gmaps = googlemaps.Client(key= settings.GOOGLE_API_KEY)
    result = json.dumps(gmaps.geocode(str('Stadionstraat 5, 4815 NC Breda')))
    result2 = json.loads(result)
    adressComponents = result2[0]['geometry']

    context = {
        'result':result,
        'adressComponents': adressComponents

    }
    return render(request, 'google/geocode.html', context)

def map(request):
    key = settings.GOOGLE_API_KEY
    context = {
        'key':key,
    }
    return render(request, 'google/map.html',context)